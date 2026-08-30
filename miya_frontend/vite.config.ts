import process from 'node:process'
import { rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { get } from 'node:http'
import type { ViteDevServer } from 'vite'
import vue from '@vitejs/plugin-vue'
import unocss from 'unocss/vite'
import { defineConfig } from 'vite'
import electron from 'vite-plugin-electron/simple'
import { startup } from 'vite-plugin-electron'

const __dirname = fileURLToPath(new URL('.', import.meta.url))
const isWebOnly = !!process.env.WEB_ONLY
const isFastElectron = !!process.env.ESBUILD_ELECTRON

if (isFastElectron) {
  rmSync(resolve(__dirname, 'node_modules', '.vite'), { recursive: true, force: true })
}

function warmupVite(url: string): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, 8000)
    get(url, (res) => {
      res.resume()
      res.on('end', () => {
        clearTimeout(timer)
        setTimeout(resolve, 2000)
      })
    }).on('error', () => {
      clearTimeout(timer)
      resolve()
    })
  })
}

function fastElectronPlugin() {
  let started = false

  return {
    name: 'electron-dev-fast',
    apply: 'serve' as const,
    configureServer(server: ViteDevServer) {
      server.httpServer?.once('listening', async () => {
        const addr = server.httpServer!.address()
        const port = typeof addr === 'object' && addr ? addr.port : 5173
        const url = `http://localhost:${port}`

        process.env.VITE_DEV_SERVER_URL = url
        if (!process.env.MIYA_START_BACKEND) {
          process.env.MIYA_NO_BACKEND = '1'
        }

        // Warm up Vite to pre-bundle dependencies before Electron loads the page
        console.log('  [electron-fast] Warming up Vite...')
        await warmupVite(url)

        console.log(`  [electron-fast] Dev server → ${url}`)
        try {
          await startup()
          started = true
          console.log('  [electron-fast] Electron started')
        }
        catch (err) {
          console.error('  [electron-fast] Electron start failed:', err)
        }
      })
    },
    closeBundle() {
      if (started && (process as any).electronApp) {
        try {
          (process as any).electronApp.removeAllListeners()
          ;(process as any).electronApp.kill?.()
        }
        catch { /* ignore */ }
      }
    },
  }
}

export default defineConfig({
  base: './',
  plugins: [
    vue({
      template: {
        compilerOptions: {
          isCustomElement: (tag: string) => tag === 'webview',
        },
      },
    }),
    unocss(),
    ...(isWebOnly
      ? []
      : isFastElectron
        ? [fastElectronPlugin()]
        : [electron({
            main: {
              entry: 'electron/main.ts',
              vite: {
                build: {
                  minify: false,
                  sourcemap: false,
                  reportCompressedSize: false,
                  emptyOutDir: false,
                  rollupOptions: {
                    external: [
                      'electron',
                      'electron-updater',
                      'lodash.isequal',
                      '@lydell/node-pty',
                    ],
                  },
                },
              },
            },
            preload: {
              input: 'electron/preload.ts',
              vite: {
                build: {
                  minify: false,
                  sourcemap: false,
                  reportCompressedSize: false,
                  emptyOutDir: false,
                  rollupOptions: {
                    output: {
                      entryFileNames: 'preload.cjs',
                      format: 'cjs',
                    },
                  },
                },
              },
            },
          })]
    ),
  ],
  resolve: { alias: { '@': resolve(__dirname, 'src') } },
  build: {
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        'live2d-app': resolve(__dirname, 'src/live2d-app/index.html'),
      },
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/vue') || id.includes('/node_modules/vue-router')) {
            return 'vue-runtime'
          }
          if (id.includes('/node_modules/pixi.js') || id.includes('/node_modules/pixi-live2d-display')) {
            return 'visual-runtime'
          }
        },
      },
    },
  },
  optimizeDeps: {
    include: [
      '@vueuse/core',
    ],
  },
})
