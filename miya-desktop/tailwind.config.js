/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // 弥娅主题色 - 青蓝色系
        miya: {
          50: '#f0fdfa',
          100: '#ccfbf1',
          200: '#99f6e4',
          300: '#5eead4',
          400: '#2dd4bf',
          500: '#0d9488',
          600: '#0f766e',
          700: '#115e59',
          800: '#134e4a',
          900: '#042f2e',
          950: '#021a1a',
        },
        // 天蓝色系
        sky: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
          950: '#082f49',
        },
        dark: {
          bg: '#042f2e',
          secondary: '#0d9488',
          accent: '#2dd4bf',
        }
      },
      background: {
        'gradient-miya': 'linear-gradient(135deg, #0d9488 0%, #0ea5e9 100%)',
        'gradient-soft': 'linear-gradient(135deg, #f0fdfa 0%, #e0f2fe 100%)',
      },
      boxShadow: {
        'soft': '0 4px 20px rgba(45, 212, 191, 0.15)',
        'glow': '0 0 20px rgba(45, 212, 191, 0.3)',
        'card': '0 8px 32px rgba(15, 23, 42, 0.1)',
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'pulse-soft': 'pulseSoft 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-20px)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.8' },
        },
      },
    },
  },
  plugins: [],
}
