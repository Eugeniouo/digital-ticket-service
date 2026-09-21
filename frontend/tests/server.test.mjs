import test from 'node:test'
import assert from 'node:assert/strict'
import { createDevServer } from '../server.mjs'

test('development server restricts files and handles invalid requests', async () => {
  const server = createDevServer()
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${server.address().port}`
  try {
    for (const path of ['/', '/booking', '/src/app.js', '/assets/logo.svg']) {
      const response = await fetch(base + path)
      assert.equal(response.status, 200, path)
      await response.text()
    }
    for (const path of ['/.env', '/package.json', '/server.mjs', '/src/missing.js', '/assets/%2e%2e/package.json']) {
      const response = await fetch(base + path)
      assert.equal(response.status, 404, path)
      await response.text()
    }
    assert.equal((await fetch(base + '/%ZZ')).status, 400)
    assert.equal((await fetch(base, { method: 'POST' })).status, 405)
    assert.equal(await (await fetch(base, { method: 'HEAD' })).text(), '')
  } finally {
    server.closeAllConnections()
    await new Promise(resolve => server.close(resolve))
  }
})
