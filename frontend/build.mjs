import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = dirname(fileURLToPath(import.meta.url))
const distDir = resolve(rootDir, 'dist')

if (dirname(distDir) !== resolve(rootDir)) {
  throw new Error('Refusing to clean a directory outside the project root')
}

rmSync(distDir, { recursive: true, force: true })
mkdirSync(distDir, { recursive: true })

for (const file of ['index.html', '_redirects']) {
  const source = join(rootDir, file)
  if (!existsSync(source)) throw new Error(`Missing required file: ${file}`)
  cpSync(source, join(distDir, file))
}

cpSync(join(rootDir, 'src'), join(distDir, 'src'), { recursive: true })
cpSync(join(rootDir, 'public', 'assets'), join(distDir, 'assets'), { recursive: true })

console.log('Static site built successfully in dist/')
