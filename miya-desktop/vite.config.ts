import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import electron from 'vite-plugin-electron'
import electronRenderer from 'vite-plugin-electron-renderer'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    electron([
      {
        entry: 'electron/preload.ts',
        onstart(args) {
          args.reload()
        },
        vite: {
          build: {
            outDir: 'dist-electron',
            rollupOptions: {
              output: {
                entryFileNames: 'preload.js'
              },
              external: ['electron']
            },
            emptyOutDir: false  // 不清空目录
          }
        }
      },
      {
        entry: 'electron/main.ts',
        vite: {
          build: {
            outDir: 'dist-electron',
            rollupOptions: {
              output: {
                entryFileNames: 'main.js'
              },
              external: ['electron']
            },
            emptyOutDir: false  // 不清空目录，保留 preload.js
          }
        }
      }
    ]),
    electronRenderer()
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@components': resolve(__dirname, 'src/components'),
      '@views': resolve(__dirname, 'src/views'),
      '@stores': resolve(__dirname, 'src/stores'),
      '@api': resolve(__dirname, 'src/api'),
      '@utils': resolve(__dirname, 'src/utils'),
      '@assets': resolve(__dirname, 'src/assets'),
      '@composables': resolve(__dirname, 'src/composables')
    }
  },
  base: './',
  server: {
    port: 5173,
    strictPort: true,
    host: '0.0.0.0',
    watch: {
      usePolling: false,
      ignored: ['**/node_modules/**', '**/dist/**', '**/.git/**', '**/dist-electron/**']
    },
    hmr: {
      overlay: true,
      clientPort: 5173
    },
    fs: {
      strict: false
    }
  },
  optimizeDeps: {
    include: [
      'vue',
      'vue-router',
      'pinia',
      'axios',
      '@vueuse/core',
      'pixi.js',
      'pixi-live2d-display',
      'pixi-live2d-display/cubism4'
    ],
    exclude: ['monaco-editor'],
    force: true  // 强制重新构建依赖预优化
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      external: ['electron']
    },
    commonjsOptions: {
      // 处理 CommonJS 模块的动态 require
      transformMixedEsModules: true
    }
  },
  define: {
    // 定义全局变量
    'global': 'globalThis'
  }
})
