import antfu from '@antfu/eslint-config'

export default antfu({
  vue: true,
  typescript: true,
  ignores: [
    'dist/**',
    'dist-electron/**',
    'release/**',
    'node_modules/**',
    'public/libraries/**',
    'resources/**',
    'data/**',
  ],
})
