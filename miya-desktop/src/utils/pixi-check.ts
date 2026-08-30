/**
 * PIXI 加载检查工具
 * 用于验证 PIXI.js 是否正确加载到全局作用域
 */

export function checkPIXI() {
  console.log('[PIXI Check] Checking PIXI availability...')

  const win = window as any

  // 检查 PIXI 是否存在
  console.log('[PIXI Check] window.PIXI:', !!win.PIXI)

  if (!win.PIXI) {
    console.error('[PIXI Check] PIXI not found on window object')
    console.log('[PIXI Check] Available globals:', Object.keys(win).filter(k => k.toLowerCase().includes('pixi')))
    return null
  }

  // 检查 PIXI.Application
  console.log('[PIXI Check] window.PIXI.Application:', !!win.PIXI.Application)

  if (!win.PIXI.Application) {
    console.error('[PIXI Check] PIXI.Application not found')
    console.log('[PIXI Check] typeof window.PIXI.Application:', typeof win.PIXI.Application)
    console.log('[PIXI Check] PIXI object keys:', Object.keys(win.PIXI))
    return null
  }

  console.log('[PIXI Check] typeof window.PIXI.Application:', typeof win.PIXI.Application)

  // 检查是否是函数/构造函数
  if (typeof win.PIXI.Application !== 'function') {
    console.error('[PIXI Check] PIXI.Application is not a function/constructor')
    console.log('[PIXI Check] Application type:', typeof win.PIXI.Application)
    console.log('[PIXI Check] PIXI object keys:', Object.keys(win.PIXI))
    return null
  }

  console.log('[PIXI Check] PIXI version:', win.PIXI.VERSION)
  console.log('[PIXI Check] PIXI loaded successfully')

  return win.PIXI
}
