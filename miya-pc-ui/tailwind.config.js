/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 青色系 - 主色调
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
        },

        // 蓝色系 - 辅助色调
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
        },

        // 柔和的背景色
        bg: {
          primary: 'linear-gradient(135deg, #f0fdfa 0%, #e0f2fe 100%)',
          secondary: 'linear-gradient(135deg, #ccfbf1 0%, #bae6fd 100%)',
          glass: 'rgba(255, 255, 255, 0.15)',
          glassDark: 'rgba(15, 23, 42, 0.25)',
        },
      },

      backgroundImage: {
        'nature-gradient': 'linear-gradient(135deg, #e0f2fe 0%, #2dd4bf 50%, #5eead4 100%)',
        'soft-glow': 'radial-gradient(circle at center, rgba(45, 212, 191, 0.15) 0%, transparent 70%)',
        'tech-pattern': 'linear-gradient(45deg, #f0fdfa 25%, transparent 25%, transparent 75%, #f0fdfa 75%, #f0fdfa), linear-gradient(45deg, #f0fdfa 25%, transparent 25%, transparent 75%, #f0fdfa 75%, #f0fdfa)',
      },

      boxShadow: {
        'soft': '0 4px 20px rgba(45, 212, 191, 0.15)',
        'glow': '0 0 20px rgba(45, 212, 191, 0.3)',
        'card': '0 8px 32px rgba(15, 23, 42, 0.1)',
      },

      animation: {
        'float': 'float 6s ease-in-out infinite',
        'pulse-soft': 'pulseSoft 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-up': 'slideUp 0.3s ease-out',
      },

      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-20px)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.8' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },

      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}
