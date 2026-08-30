import type { Buffer } from 'node:buffer'
import type { ChildProcess } from 'node:child_process'
import { execSync, spawn } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { app } from 'electron'
import { getMainWindow } from './window'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

let backendProcess: ChildProcess | null = null
const BACKEND_LOG_MAX_LINES = 1200
const backendLogLines: string[] = []

function appendBackendLog(line: string, stream: 'stdout' | 'stderr' | 'system' = 'system') {
  const normalized = line.replace(/\r/g, '').trimEnd()
  if (!normalized.trim())
    return

  const entry = stream === 'system' ? normalized : `[${stream}] ${normalized}`
  backendLogLines.push(entry)
  if (backendLogLines.length > BACKEND_LOG_MAX_LINES) {
    backendLogLines.splice(0, backendLogLines.length - BACKEND_LOG_MAX_LINES)
  }

  try {
    getMainWindow()?.webContents.send('backend:log', { line: entry })
  }
  catch {
    // ignore renderer delivery failures
  }
}

function getBackendInternalDir(): string {
  return app.isPackaged
    ? join(process.resourcesPath, 'backend', '_internal')
    : join(__dirname, '..', '..')
}

function createChunkForwarder(
  stream: 'stdout' | 'stderr',
  onLine: (line: string) => boolean | void,
) {
  let carry = ''

  return (text: string) => {
    const normalized = `${carry}${text.replace(/\r\n/g, '\n').replace(/\r/g, '\n')}`
    const parts = normalized.split('\n')
    carry = parts.pop() ?? ''
    for (const part of parts) {
      const line = part.trimEnd()
      if (!line.trim())
        continue
      const shouldMirror = onLine(line)
      if (shouldMirror !== false) {
        appendBackendLog(line, stream)
      }
    }
  }
}

export function getBackendLogs(): string {
  return backendLogLines.join('\n')
}

export function readPortsFromDisk(): Record<string, number> | null {
  const internalDir = getBackendInternalDir()
  const portsFile = join(internalDir, 'config', 'runtime_ports.json')
  try {
    if (existsSync(portsFile)) {
      return JSON.parse(readFileSync(portsFile, 'utf-8')) as Record<string, number>
    }
  }
  catch {
    // file may not exist yet or be invalid
  }
  return null
}

export function pushPortToWindow(ports: Record<string, number>) {
  const apiPort = ports.web_api || ports.management_api
  const managementPort = ports.management_api || 9800
  if (!apiPort && !ports.management_api) return
  const mainWindow = getMainWindow()
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.executeJavaScript(
      `window.__MIYA_API_PORT__ = ${apiPort || managementPort}; window.__MIYA_MANAGEMENT_PORT__ = ${managementPort}; console.log('[MIYA] API ports set to', { api: ${apiPort || managementPort}, management: ${managementPort} })`
    ).catch(() => {})
  }
}

let portPollTimer: ReturnType<typeof setInterval> | null = null

export function startPortPolling() {
  if (portPollTimer) return
  const poll = () => {
    const ports = readPortsFromDisk()
    if (ports) pushPortToWindow(ports)
  }
  poll()
  portPollTimer = setInterval(poll, 2000)
}

export function stopPortPolling() {
  if (portPollTimer) {
    clearInterval(portPollTimer)
    portPollTimer = null
  }
}

function resolveVenvPython(cwd: string): string {
  return process.platform === 'win32'
    ? join(cwd, '.venv', 'Scripts', 'python.exe')
    : join(cwd, '.venv', 'bin', 'python')
}

function findPythonExe(): string | null {
  try {
    if (process.platform === 'win32') {
      const result = execSync('where python 2>nul', { timeout: 5000, encoding: 'utf-8' })
      const lines = result.trim().split('\r\n').filter(Boolean)
      // Skip Windows Store stub (AppData\Local\Microsoft\WindowsApps)
      for (const p of lines) {
        if (existsSync(p) && !p.includes('WindowsApps')) return p
      }
    }
    else {
      const result = execSync('which python3 || which python', { timeout: 5000, encoding: 'utf-8', shell: '/bin/sh' })
      const lines = result.trim().split('\n').filter(Boolean)
      for (const p of lines) {
        if (existsSync(p)) return p
      }
    }
  }
  catch { /* fall through */ }

  if (process.platform === 'win32') {
    // Try py launcher (Python Launcher for Windows)
    try {
      execSync('py --version', { timeout: 5000 })
      return 'py'
    }
    catch { /* fall through */ }
  }

  return null
}

export function startBackend(): void {
  let cmd: string
  let args: string[]
  let cwd: string

  if (app.isPackaged) {
    // 打包模式：spawn PyInstaller 编译的二进制
    const backendDir = join(process.resourcesPath, 'backend')
    const ext = process.platform === 'win32' ? '.exe' : ''
    cmd = join(backendDir, `miya-backend${ext}`)
    args = []
    // CWD 设为 _internal/ 以确保相对路径 (config/*.json 等) 正确解析
    cwd = join(backendDir, '_internal')
  }
  else {
    // 开发模式：尝试 venv Python → 系统 Python → 跳过
    cwd = join(__dirname, '..', '..')
    let pythonPath = resolveVenvPython(cwd)
    if (!existsSync(pythonPath)) {
      // Try to find Python on the system
      pythonPath = findPythonExe() || ''

      if (pythonPath) {
        console.log('[Backend] Using system Python:', pythonPath)
      }
      else {
        console.warn('[Backend] Python interpreter not found, skipping backend start')
        appendBackendLog('[Backend] Python not found, skipping backend start')
        return
      }
    }
    cmd = pythonPath
    args = ['run/daemon.py']
  }

  console.log(`[Backend] Starting from ${cwd}`)
  console.log(`[Backend] Command: ${cmd} ${args.join(' ')}`)
  appendBackendLog(`[Backend] Starting from ${cwd}`)
  appendBackendLog(`[Backend] Command: ${cmd} ${args.join(' ')}`)

  const env: Record<string, string | undefined> = { ...process.env, PYTHONUNBUFFERED: '1' }

  // Collect all output for error reporting
  const outputLines: string[] = []
  const PROGRESS_PREFIX = '##PROGRESS##'
  const MIYA_PORTS_PREFIX = '##MIYA_PORTS##'
  const consumeStdoutChunk = createChunkForwarder('stdout', (trimmed) => {
    outputLines.push(trimmed)

    if (trimmed.startsWith(MIYA_PORTS_PREFIX)) {
      try {
        const jsonStr = trimmed.slice(MIYA_PORTS_PREFIX.length).replace(/##$/, '')
        const ports = JSON.parse(jsonStr) as Record<string, number>
        console.log('[Backend] Detected ports:', ports)

        const apiPort = ports.web_api || ports.management_api || 9800
        const managementPort = ports.management_api || 9800
        const mainWindow = getMainWindow()
        if (mainWindow) {
          mainWindow.webContents.executeJavaScript(
            `window.__MIYA_API_PORT__ = ${apiPort}; window.__MIYA_MANAGEMENT_PORT__ = ${managementPort}; console.log('[MIYA] API ports set to', { api: ${apiPort}, management: ${managementPort} })`
          ).catch(() => {})
        }
      }
      catch {
        // malformed port line, ignore
      }
      return false
    }

    if (trimmed.startsWith(PROGRESS_PREFIX)) {
      try {
        const payload = JSON.parse(trimmed.slice(PROGRESS_PREFIX.length))
        getMainWindow()?.webContents.send('backend:progress', payload)
      }
      catch {
        // malformed progress line, ignore
      }
      return false
    }
    return true
  })
  const consumeStderrChunk = createChunkForwarder('stderr', (trimmed) => {
    outputLines.push(trimmed)
    return true
  })

  backendProcess = spawn(cmd, args, {
    cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
    env,
    // 创建独立进程组，关闭时用 process.kill(-pid) 杀掉所有子进程
    detached: process.platform !== 'win32',
  })

  backendProcess.stdout?.on('data', (data: Buffer) => {
    const text = data.toString()
    consumeStdoutChunk(text)
    console.log(`[Backend] ${text.trimEnd()}`)
  })

  backendProcess.stderr?.on('data', (data: Buffer) => {
    const text = data.toString()
    console.error(`[Backend] ${text.trimEnd()}`)
    consumeStderrChunk(text)
  })

  backendProcess.on('error', (err) => {
    console.error(`[Backend] Failed to start: ${err.message}`)
    appendBackendLog(`[Backend] Failed to start: ${err.message}`)
  })

  backendProcess.on('exit', (code) => {
    console.log(`[Backend] Exited with code ${code}`)
    appendBackendLog(`[Backend] Exited with code ${code}`)
    backendProcess = null

    // Notify renderer of backend crash (non-zero exit, not a manual stop)
    if (code !== null && code !== 0) {
      const logs = outputLines.slice(-200).join('\n')
      getMainWindow()?.webContents.send('backend:error', { code, logs })
    }
  })
}

export function stopBackend(): void {
  if (!backendProcess)
    return
  const pid = backendProcess.pid
  console.log('[Backend] Stopping...')
  appendBackendLog('[Backend] Stopping...')

  if (!pid) {
    backendProcess = null
    return
  }

  if (process.platform === 'win32') {
    // /T 连同子进程树一起终止
    spawn('taskkill', ['/pid', String(pid), '/f', '/t'])
  }
  else {
    // 杀整个进程组（负 PID），确保 uvicorn workers 等子进程一起退出
    try {
      process.kill(-pid, 'SIGTERM')
    }
    catch {
      // 进程组不存在，回退杀单个进程
      try {
        process.kill(pid, 'SIGTERM')
      }
      catch {
        /* already dead */
      }
    }
    // 保险：200ms 后 SIGKILL 整个进程组
    setTimeout(() => {
      try {
        process.kill(-pid, 'SIGKILL')
      }
      catch {
        try {
          process.kill(pid, 'SIGKILL')
        }
        catch {
          /* already dead */
        }
      }
    }, 200)
  }

  backendProcess = null
}
