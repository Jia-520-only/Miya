let pendingLoad: Promise<void> | null = null

function hasLive2dCore(): boolean {
  return typeof window !== 'undefined' && !!(window as Window & { Live2DCubismCore?: unknown }).Live2DCubismCore
}

function resolveCandidateUrls(): string[] {
  const candidates = new Set<string>()

  if (typeof window !== 'undefined') {
    for (const relativePath of [
      '../../libraries/live2dcubismcore.min.js',
      '../libraries/live2dcubismcore.min.js',
      './libraries/live2dcubismcore.min.js',
      '/libraries/live2dcubismcore.min.js',
    ]) {
      try {
        candidates.add(new URL(relativePath, window.location.href).toString())
      }
      catch {
        candidates.add(relativePath)
      }
    }
  }

  candidates.add('../../libraries/live2dcubismcore.min.js')
  candidates.add('../libraries/live2dcubismcore.min.js')
  candidates.add('./libraries/live2dcubismcore.min.js')
  return Array.from(candidates)
}

function injectScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[data-live2d-core="1"][src="${src}"]`)
    if (existing) {
      if (hasLive2dCore()) {
        resolve()
        return
      }
      existing.remove()
    }

    const script = document.createElement('script')
    script.src = src
    script.async = false
    script.dataset.live2dCore = '1'
    script.onload = () => resolve()
    script.onerror = () => {
      script.remove()
      reject(new Error(`failed to load ${src}`))
    }
    document.head.appendChild(script)
  })
}

export async function ensureLive2dCoreLoaded(): Promise<void> {
  if (hasLive2dCore()) {
    return
  }
  if (pendingLoad) {
    return pendingLoad
  }

  pendingLoad = (async () => {
    const errors: string[] = []
    for (const src of resolveCandidateUrls()) {
      try {
        await injectScript(src)
        if (hasLive2dCore()) {
          return
        }
      }
      catch (error) {
        errors.push(error instanceof Error ? error.message : String(error))
      }
    }
    throw new Error(errors.join('; ') || 'Live2D Cubism Core unavailable')
  })()

  try {
    await pendingLoad
  }
  finally {
    if (!hasLive2dCore()) {
      pendingLoad = null
    }
  }
}
