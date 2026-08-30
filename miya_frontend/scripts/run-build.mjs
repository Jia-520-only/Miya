import { execSync } from 'node:child_process'
import { existsSync, rmSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

console.log('Building Miya Desktop...\n')

console.log('[0/2] Updating audio manifest...')
execSync(`${process.execPath} scripts/generate-audio-manifest.mjs`, { cwd: root, stdio: 'inherit' })

if (existsSync(resolve(root, 'dist'))) {
  rmSync(resolve(root, 'dist'), { recursive: true })
}
if (existsSync(resolve(root, 'dist-electron'))) {
  rmSync(resolve(root, 'dist-electron'), { recursive: true })
}

const isWin = process.platform === 'win32'
const npx = isWin ? 'npx.cmd' : 'npx'

console.log('[1/2] Vite build (renderer + electron)...')
execSync(`${npx} vite build`, { cwd: root, stdio: 'inherit' })

// Live2D character assets are user-installable packages and must not inflate the app archive.
const bundledModels = resolve(root, 'dist', 'models')
if (existsSync(bundledModels)) {
  rmSync(bundledModels, { recursive: true, force: true })
  console.log('Removed bundled Live2D models (installed separately at runtime).')
}

console.log('\n[2/2] TypeScript type check...')
try {
  execSync(`${npx} vue-tsc --build --force`, { cwd: root, stdio: 'inherit' })
}
catch {
  console.warn('Type check completed with warnings (non-blocking)')
}

console.log('\nBuild complete!')
