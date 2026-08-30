import { cpSync, existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { basename, dirname, relative, resolve, sep } from 'node:path'
import { app, dialog } from 'electron'

export interface Live2dPackageInfo { id: string; name: string; modelPath: string; size: number; active: boolean }
interface Manifest { id: string; name: string; version: number; model: string }

const MAX_PACKAGE_FILES = 20_000
const MAX_PACKAGE_BYTES = 1024 * 1024 * 1024

const packagesDir = () => resolve(app.getPath('userData'), 'live2d-packages')
const settingsPath = () => resolve(app.getPath('userData'), 'live2d-packages.json')

function activeId(): string | null {
  try {
    const value = (JSON.parse(readFileSync(settingsPath(), 'utf8')) as { activeId?: unknown }).activeId
    return typeof value === 'string' ? value : null
  }
  catch { return null }
}

function setActiveId(id: string | null): void {
  writeFileSync(settingsPath(), JSON.stringify({ activeId: id }, null, 2), 'utf8')
}

function findModels(root: string): string[] {
  const result: string[] = []
  let visited = 0
  const visit = (dir: string): void => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (++visited > MAX_PACKAGE_FILES) throw new Error(`角色包文件过多（上限 ${MAX_PACKAGE_FILES} 个）`)
      const path = resolve(dir, entry.name)
      if (entry.isSymbolicLink()) throw new Error('角色包不能包含符号链接')
      if (entry.isDirectory()) visit(path)
      else if (entry.isFile() && entry.name.toLowerCase().endsWith('.model3.json')) result.push(path)
    }
  }
  visit(root)
  return result
}

function folderSize(root: string): number {
  let size = 0
  let visited = 0
  const visit = (dir: string): void => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (++visited > MAX_PACKAGE_FILES) throw new Error(`角色包文件过多（上限 ${MAX_PACKAGE_FILES} 个）`)
      const path = resolve(dir, entry.name)
      if (entry.isSymbolicLink()) throw new Error('角色包不能包含符号链接')
      if (entry.isDirectory()) visit(path)
      else if (entry.isFile()) {
        size += statSync(path).size
        if (size > MAX_PACKAGE_BYTES) throw new Error('角色包超过 1 GB，已取消操作')
      }
    }
  }
  visit(root)
  return size
}

function safeAssetPath(root: string, value: unknown): string | null {
  if (typeof value !== 'string' || !value.trim()) return null
  const path = resolve(root, value)
  return path.startsWith(`${root}${sep}`) ? path : null
}

function validateModel(model: string): void {
  const root = dirname(model)
  let data: any
  try { data = JSON.parse(readFileSync(model, 'utf8')) }
  catch { throw new Error('model3.json 不是有效的 JSON 文件') }
  if (data?.Version !== 3 || !data?.FileReferences) throw new Error('仅支持 Cubism 3/4 的 .model3.json 模型')

  const refs = data.FileReferences
  const required: Array<[string, unknown]> = [['Moc', refs.Moc]]
  const textures = Array.isArray(refs.Textures) ? refs.Textures : []
  if (!textures.length) throw new Error('模型没有配置纹理文件')
  textures.forEach((value: unknown, index: number) => required.push([`Textures[${index}]`, value]))
  for (const [label, value] of required) {
    const path = safeAssetPath(root, value)
    if (!path) throw new Error(`${label} 使用了无效或越界路径`)
    if (!existsSync(path) || !lstatSync(path).isFile()) throw new Error(`缺少模型必需文件：${String(value)}`)
  }

  const optional: unknown[] = [refs.Physics, refs.Pose, refs.DisplayInfo, refs.UserData, refs.MiyaActions, data.MiyaActions]
  if (Array.isArray(refs.Expressions)) optional.push(...refs.Expressions.map((item: any) => item?.File))
  if (refs.Motions && typeof refs.Motions === 'object') {
    for (const group of Object.values(refs.Motions) as any[]) {
      if (Array.isArray(group)) optional.push(...group.map(item => item?.File))
    }
  }
  for (const value of optional.filter(Boolean)) {
    const path = safeAssetPath(root, value)
    if (!path) throw new Error(`模型引用使用了无效或越界路径：${String(value)}`)
    if (!existsSync(path) || !lstatSync(path).isFile()) throw new Error(`模型引用的文件不存在：${String(value)}`)
  }
}

function readManifest(dir: string): Manifest | null {
  try {
    const data = JSON.parse(readFileSync(resolve(dir, 'manifest.json'), 'utf8')) as Manifest
    const model = resolve(dir, data.model)
    if (!data.id || !data.name || !data.model || !model.startsWith(`${dir}${sep}`) || !existsSync(model)) return null
    return data
  }
  catch { return null }
}

export function getLive2dPackagesDir(): string { return packagesDir() }

export function listLive2dPackages(): Live2dPackageInfo[] {
  const root = packagesDir()
  mkdirSync(root, { recursive: true })
  const selected = activeId()
  return readdirSync(root, { withFileTypes: true }).filter(e => e.isDirectory()).map((entry) => {
    const dir = resolve(root, entry.name)
    const manifest = readManifest(dir)
    return manifest && { id: manifest.id, name: manifest.name, modelPath: manifest.model.replaceAll('\\', '/'), size: folderSize(dir), active: manifest.id === selected }
  }).filter((item): item is Live2dPackageInfo => !!item).sort((a, b) => Number(b.active) - Number(a.active) || a.name.localeCompare(b.name))
}

export function getActiveLive2dModelUrl(): string | null {
  const item = listLive2dPackages().find(p => p.active)
  return item ? `miya-char://${encodeURIComponent(item.id)}/${item.modelPath.split('/').map(encodeURIComponent).join('/')}` : null
}

export function importLive2dPackage(): Live2dPackageInfo | null {
  const picked = dialog.showOpenDialogSync({ title: '选择 Live2D 模型文件夹', properties: ['openDirectory'] })
  if (!picked?.[0]) return null
  const models = findModels(resolve(picked[0]))
  if (!models.length) throw new Error('所选文件夹中没有找到 .model3.json 文件')
  if (models.length > 1) throw new Error('所选文件夹包含多个模型，请选择单个模型所在的文件夹')

  const model = models[0]!
  const source = dirname(model)
  folderSize(source)
  validateModel(model)
  const name = basename(model).replace(/\.model3\.json$/i, '') || basename(source)
  const slug = name.normalize('NFKC').replace(/[^\p{L}\p{N}._-]+/gu, '-').replace(/^-+|-+$/g, '') || 'character'
  const id = `${slug}-${Date.now().toString(36)}`.toLowerCase()
  const target = resolve(packagesDir(), id)
  mkdirSync(packagesDir(), { recursive: true })
  try {
    cpSync(source, target, { recursive: true, errorOnExist: true, dereference: false })
    const manifest: Manifest = { id, name, version: 1, model: relative(source, model).replaceAll('\\', '/') }
    writeFileSync(resolve(target, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf8')
  }
  catch (error) {
    if (existsSync(target)) rmSync(target, { recursive: true, force: true })
    throw error
  }
  if (!activeId()) setActiveId(id)
  return listLive2dPackages().find(p => p.id === id) ?? null
}

export function activateLive2dPackage(id: string): void {
  if (!listLive2dPackages().some(p => p.id === id)) throw new Error('角色包不存在')
  setActiveId(id)
}

export function deleteLive2dPackage(id: string): boolean {
  const item = listLive2dPackages().find(p => p.id === id)
  if (!item) throw new Error('角色包不存在')
  const root = packagesDir()
  const target = resolve(root, id)
  if (!target.startsWith(`${root}${sep}`)) throw new Error('无效的角色包路径')
  rmSync(target, { recursive: true, force: true })
  if (item.active) setActiveId(null)
  return item.active
}
