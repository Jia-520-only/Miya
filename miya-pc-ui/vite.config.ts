import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@shared': path.resolve(__dirname, './shared'),
      '@store': path.resolve(__dirname, './src/store'),
      '@Components': path.resolve(__dirname, './src/Components'),
      '@Modals': path.resolve(__dirname, './src/Modals'),
      '@Emotion': path.resolve(__dirname, './src/Emotion'),
      '@Live2D': path.resolve(__dirname, './src/Live2D'),
      '@FloatingBall': path.resolve(__dirname, './src/FloatingBall'),
      '@Pages': path.resolve(__dirname, './src/Pages')
    }
  },
  server: {
    port: 3000,
    host: '0.0.0.0'
  }
})
