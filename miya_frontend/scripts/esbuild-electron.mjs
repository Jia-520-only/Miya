/**
 * Fast Electron build using esbuild (milliseconds vs Rollup's 90+ seconds).
 *
 * Usage:
 *   node scripts/esbuild-electron.mjs          # one-shot build
 *   node scripts/esbuild-electron.mjs --watch  # watch mode for dev
 */

import { context } from 'esbuild'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')
const isWatch = process.argv.includes('--watch')

const nodeBuiltins = [
  'node:*', 'assert', 'buffer', 'child_process', 'cluster', 'crypto',
  'dgram', 'dns', 'domain', 'events', 'fs', 'http', 'https', 'net',
  'os', 'path', 'process', 'punycode', 'querystring', 'readline',
  'stream', 'string_decoder', 'timers', 'tls', 'tty', 'url', 'util',
  'v8', 'vm', 'zlib',
]

const external = [
  'electron',
  'electron-updater',
  'lodash.isequal',
  '@lydell/node-pty',
  ...nodeBuiltins,
]

const baseConfig = {
  bundle: true,
  platform: 'node',
  target: 'node20',
  external,
  absWorkingDir: root,
  logLevel: 'info',
  minify: false,
  sourcemap: false,
  treeShaking: true,
  legalComments: 'none',
}

/** @type {import('esbuild').BuildOptions} */
const mainConfig = {
  ...baseConfig,
  entryPoints: [resolve(root, 'electron/main.ts')],
  outfile: resolve(root, 'dist-electron/main.js'),
  format: 'esm',
}

/** @type {import('esbuild').BuildOptions} */
const preloadConfig = {
  ...baseConfig,
  entryPoints: [resolve(root, 'electron/preload.ts')],
  outfile: resolve(root, 'dist-electron/preload.cjs'),
  format: 'cjs',
}

async function build() {
  const start = performance.now()

  if (isWatch) {
    const mainCtx = await context(mainConfig)
    const preloadCtx = await context(preloadConfig)

    await Promise.all([mainCtx.watch(), preloadCtx.watch()])
    const elapsed = ((performance.now() - start) / 1000).toFixed(1)
    console.log(`[esbuild-electron] Watching for changes (initial build: ${elapsed}s)`)
  }
  else {
    const { build: esbuild } = await import('esbuild')
    await Promise.all([
      esbuild(mainConfig),
      esbuild(preloadConfig),
    ])
    const elapsed = ((performance.now() - start) / 1000).toFixed(1)
    console.log(`[esbuild-electron] Build complete (${elapsed}s)`)
  }
}

build().catch((err) => {
  console.error('[esbuild-electron] Build failed:', err)
  process.exit(1)
})
