import { spawn, type IPty } from '@lydell/node-pty'
import { execSync, spawn as spawnProc, type ChildProcessByStdio } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { homedir, platform } from 'node:os'
import { createServer } from 'node:net'
import { resolve } from 'node:path'
import type { Readable } from 'node:stream'

function findNodeExe(): string {
  try {
    if (platform() === 'win32') {
      const result = execSync('where node', { timeout: 5000, encoding: 'utf-8' })
      const paths = result.trim().split('\r\n')
      for (const p of paths) {
        if (existsSync(p)) return p
      }
    } else {
      const result = execSync('which node || type -p node 2>/dev/null', { timeout: 5000, encoding: 'utf-8', shell: '/bin/sh' })
      const paths = result.trim().split('\n')
      for (const p of paths) {
        if (existsSync(p)) return p
      }
    }
  }
  catch { /* fall through */ }

  const isWin = platform() === 'win32'
  const fallbacks = isWin
    ? [
        resolve(homedir(), 'AppData', 'Roaming', 'fnm', 'node-versions', 'v22', 'installation', 'node.exe'),
        'C:\\Program Files\\nodejs\\node.exe',
        'D:\\node.exe',
      ]
    : [
        resolve(homedir(), '.nvm', 'versions', 'node', 'v22', 'bin', 'node'),
        resolve(homedir(), '.local', 'share', 'fnm', 'node-versions', 'v22', 'installation', 'bin', 'node'),
        '/usr/local/bin/node',
        '/usr/bin/node',
      ]

  for (const fb of [process.env.NODE_EXE, process.env.NODE, ...fallbacks]) {
    if (fb && existsSync(fb)) return fb
  }

  return isWin ? 'node.exe' : 'node'
}

const NODE_EXE = findNodeExe()

function loadEnvVars(rootDir: string): Record<string, string> {
  const env: Record<string, string> = {}

  const candidates = [
    resolve(rootDir, 'config', '.env'),
    resolve(rootDir, 'resources', 'backend', '_internal', 'config', '.env'),
  ]

  const envPath = candidates.find(p => existsSync(p))
  if (envPath) {
    const content = readFileSync(envPath, 'utf-8')
    for (const line of content.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('#')) continue
      const eqIdx = trimmed.indexOf('=')
      if (eqIdx === -1) continue
      const key = trimmed.slice(0, eqIdx).trim()
      const value = trimmed.slice(eqIdx + 1).trim()
      if (key && value) env[key] = value
    }
  }
  return env
}

let miyaRoot = ''

export function setMiyaRoot(root: string): void {
  miyaRoot = root
}

// ─── DSH Web host（弥娅之手服务端）进程管理 ───

const DSH_PORT_START = 3199
const DSH_READY_TIMEOUT_MS = 60_000

let dshProcess: ChildProcessByStdio<null, Readable, Readable> | null = null
let dshUrl = ''

function findDshBin(rootDir: string): string | null {
  const candidates = [
    resolve(rootDir, 'deepseek-harness', 'apps', 'cli', 'lib', 'bin.js'),
    resolve(process.resourcesPath || '', 'deepseek-harness', 'apps', 'cli', 'lib', 'bin.js'),
    resolve(process.resourcesPath || '', '_internal', 'deepseek-harness', 'apps', 'cli', 'lib', 'bin.js'),
    resolve(process.resourcesPath || '', 'backend', '_internal', 'deepseek-harness', 'apps', 'cli', 'lib', 'bin.js'),
  ]
  return candidates.find(p => existsSync(p)) ?? null
}

function isPortFree(port: number): Promise<boolean> {
  return new Promise((resolveFree) => {
    const srv = createServer()
    srv.once('error', () => resolveFree(false))
    srv.once('listening', () => srv.close(() => resolveFree(true)))
    srv.listen(port, '127.0.0.1')
  })
}

async function findFreePort(start: number): Promise<number> {
  for (let port = start; port < start + 20; port++) {
    if (await isPortFree(port)) return port
  }
  throw new Error('找不到可用端口启动 DSH Web')
}

async function waitForUrl(url: string): Promise<void> {
  const deadline = Date.now() + DSH_READY_TIMEOUT_MS
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(3000) })
      if (res.status > 0) return
    }
    catch { /* not ready yet */ }
    await new Promise(r => setTimeout(r, 500))
  }
  throw new Error(`DSH Web 启动超时 (${DSH_READY_TIMEOUT_MS / 1000}s)`)
}

async function ensureDshHost(rootDir: string, env: Record<string, string>): Promise<string> {
  if (dshProcess && dshUrl) return dshUrl

  const binPath = findDshBin(rootDir)
  if (!binPath) {
    throw new Error('DSH 未找到：请先在 deepseek-harness 目录执行 pnpm install && pnpm run build')
  }
  if (!existsSync(NODE_EXE)) {
    throw new Error('Node.js 未找到。请先安装 Node.js。')
  }

  const port = await findFreePort(DSH_PORT_START)

  dshProcess = spawnProc(NODE_EXE, [binPath, 'web', '--host', '127.0.0.1', '--port', String(port)], {
    cwd: rootDir,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })

  dshProcess.on('exit', () => {
    dshProcess = null
    dshUrl = ''
  })

  dshUrl = `http://127.0.0.1:${port}`
  await waitForUrl(dshUrl)
  return dshUrl
}

// ─── 独立 DSH Web host API（Web 板块使用，不与 TUI 互杀） ───

/**
 * 启动（或复用）DSH Web host，返回 URL。
 * 已运行则直接返回当前 URL，不重启、不打断 TUI。
 */
export async function startDshHost(options: { model?: string } = {}): Promise<{ url: string }> {
  const rootDir = miyaRoot || process.cwd()
  const env = buildCommonEnv(rootDir)
  if (options.model) {
    env.DEEPSEEK_MODEL = options.model
  }
  const url = await ensureDshHost(rootDir, env)
  return { url }
}

export function stopDshHost(): void {
  if (dshProcess) {
    dshProcess.kill()
    dshProcess = null
    dshUrl = ''
  }
}

export function isDshHostRunning(): boolean {
  return dshProcess !== null
}

export function getDshHostUrl(): string {
  return dshUrl
}

// ─── DSH TUI（终端客户端）pty 管理 ───

let tuiProcess: IPty | null = null
let tuiBuffer = ''

function findDshTuiBin(rootDir: string): string | null {
  const candidates = [
    resolve(rootDir, 'tools', 'dsh-tui', 'node_modules', 'dsh-tui', 'bin', 'tui.js'),
    resolve(process.resourcesPath || '', 'dsh-tui', 'node_modules', 'dsh-tui', 'bin', 'tui.js'),
    resolve(process.resourcesPath || '', '_internal', 'tools', 'dsh-tui', 'node_modules', 'dsh-tui', 'bin', 'tui.js'),
    resolve(process.resourcesPath || '', 'backend', '_internal', 'tools', 'dsh-tui', 'node_modules', 'dsh-tui', 'bin', 'tui.js'),
  ]
  return candidates.find(p => existsSync(p)) ?? null
}

function buildCommonEnv(rootDir: string): Record<string, string> {
  const dotEnv = loadEnvVars(rootDir)
  const apiKey = dotEnv.DEEPSEEK_API_KEY || process.env.DEEPSEEK_API_KEY || ''
  const dshHome = resolve(rootDir, 'data', 'dsh')
  return {
    ...process.env,
    DSH_HOME: dshHome,
    DEEPSEEK_API_KEY: apiKey,
    DSH_PERMISSION_MODE: 'danger-full-access',
    NO_PROXY: `${process.env.NO_PROXY ?? ''},127.0.0.1,localhost`,
    FORCE_COLOR: '1',
    TERM: 'xterm-256color',
  } as Record<string, string>
}

/**
 * 启动弥娅之手：DSH Web host + （默认）dsh-tui 交互终端。
 * mode: 'tui'（默认，pty 终端）| 'web'（仅 Web UI）
 */
export async function startTerminal(
  options: { model?: string, mode?: 'tui' | 'web' } = {},
  onData: (data: string) => void,
  onExit: (code: number) => void,
): Promise<{ url: string, mode: 'tui' | 'web' }> {
  // 不杀 host：host 可能由 Web 板块启动并正在被使用，TUI 只负责自己的 pty
  if (tuiProcess) {
    tuiProcess.kill()
    tuiProcess = null
    tuiBuffer = ''
  }

  const mode = options.mode ?? 'tui'
  const rootDir = miyaRoot || process.cwd()

  const env = buildCommonEnv(rootDir)
  if (options.model) {
    env.DEEPSEEK_MODEL = options.model
  }

  const url = await ensureDshHost(rootDir, env)

  if (mode === 'tui') {
    const tuiBin = findDshTuiBin(rootDir)
    if (!tuiBin) {
      throw new Error('dsh-tui 未找到：请在 tools/dsh-tui 目录执行 npm install dsh-tui')
    }

    tuiProcess = spawn(NODE_EXE, [tuiBin], {
      name: 'xterm-256color',
      cwd: rootDir,
      env: { ...env, DSH_URL: url },
      cols: 120,
      rows: 40,
    })

    tuiBuffer = ''
    tuiProcess.onData((data: string) => {
      tuiBuffer += data
      onData(data)
    })
    tuiProcess.onExit(({ exitCode }) => {
      onExit(exitCode)
      tuiProcess = null
    })
  }

  return { url, mode }
}

export function stopTerminal(): void {
  if (tuiProcess) {
    tuiProcess.kill()
    tuiProcess = null
    tuiBuffer = ''
  }
  if (dshProcess) {
    dshProcess.kill()
    dshProcess = null
    dshUrl = ''
  }
}

export function isTerminalRunning(): boolean {
  return dshProcess !== null
}

export function isTuiRunning(): boolean {
  return tuiProcess !== null
}

export function getTerminalUrl(): string {
  return dshUrl
}

export function getTerminalBuffer(): string {
  return tuiBuffer
}

export function writeToTerminal(data: string): void {
  if (tuiProcess) {
    tuiProcess.write(data)
  }
}

export function resizeTerminal(cols: number, rows: number): void {
  if (tuiProcess) {
    tuiProcess.resize(cols, rows)
  }
}
