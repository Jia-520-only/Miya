import { readdirSync, writeFileSync } from 'node:fs'
import { dirname, extname, resolve } from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const voicesRoot = resolve(root, 'public', 'voices')
const outputPath = resolve(root, 'src', 'generated', 'audio-manifest.json')
const audioExtensions = new Set(['.aac', '.flac', '.m4a', '.mp3', '.ogg', '.wav', '.webm'])
const collator = new Intl.Collator('zh-CN')

function audioFiles(directory) {
  return readdirSync(directory, { withFileTypes: true })
    .filter(entry => entry.isFile() && audioExtensions.has(extname(entry.name).toLowerCase()))
    .map(entry => entry.name)
    .sort(collator.compare)
}

const startRoot = resolve(voicesRoot, 'start')
const startVoices = Object.fromEntries(
  readdirSync(startRoot, { withFileTypes: true })
    .filter(entry => entry.isDirectory())
    .sort((a, b) => collator.compare(a.name, b.name))
    .map(entry => [entry.name, audioFiles(resolve(startRoot, entry.name))]),
)

const manifest = {
  startVoices,
  effects: audioFiles(resolve(voicesRoot, 'effect')),
}

writeFileSync(outputPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')
console.log(`[audio-manifest] Updated ${outputPath.replace(`${root}\\`, '')}`)

process.exitCode = 0
