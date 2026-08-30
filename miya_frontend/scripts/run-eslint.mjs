import { execSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

const isWin = process.platform === 'win32'
const npx = isWin ? 'npx.cmd' : 'npx'
const args = process.argv.slice(2)

execSync(`${npx} eslint . ${args.join(' ')}`, { cwd: root, stdio: 'inherit' })
