import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'
import { createServer } from 'node:http'
import { dirname, extname, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(fileURLToPath(import.meta.url))
const port = Number(process.env.PORT || 4173)
const host = process.env.HOST || '127.0.0.1'
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml' }

export function createDevServer() {
  return createServer(async (request, response) => {
    const fail = (code, message) => {
      response.writeHead(code, { 'Content-Type': 'text/plain; charset=utf-8' })
      response.end(message)
    }
    if (!['GET', 'HEAD'].includes(request.method)) {
      response.setHeader('Allow', 'GET, HEAD')
      fail(405, 'Method not allowed')
      return
    }
    let pathname
    try {
      pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname)
    } catch {
      fail(400, 'Invalid URL')
      return
    }
    if (pathname.includes('\\') || pathname.split('/').some(part => part.startsWith('.'))) {
      fail(404, 'Not found')
      return
    }
    let relative
    if (['/', '/index.html', '/booking', '/booking/'].includes(pathname)) relative = 'index.html'
    else if (pathname.startsWith('/assets/')) relative = `public${pathname}`
    else if (pathname.startsWith('/src/')) relative = pathname.slice(1)
    else { fail(404, 'Not found'); return }
    const file = resolve(root, relative)
    if (!file.startsWith(`${root}${sep}`) || !mime[extname(file)]) {
      fail(404, 'Not found')
      return
    }
    try {
      if (!(await stat(file)).isFile()) { fail(404, 'Not found'); return }
      response.setHeader('Content-Type', mime[extname(file)])
      response.setHeader('X-Content-Type-Options', 'nosniff')
      response.setHeader('Cache-Control', 'no-cache')
      if (request.method === 'HEAD') { response.end(); return }
      const stream = createReadStream(file)
      stream.on('error', () => {
        if (response.headersSent) response.destroy()
        else fail(500, 'Unable to read file')
      })
      stream.pipe(response)
    } catch {
      fail(404, 'Not found')
    }
  })
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  createDevServer().listen(port, host, () => console.log(`Pochta Queue: http://localhost:${port}`))
}
