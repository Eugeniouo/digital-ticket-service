import test from 'node:test'
import assert from 'node:assert/strict'
import { ticketApi } from '../src/tickets/api.js'
import { issuesApi, staffApi, windowsApi } from '../src/staff/api.js'

function ok(body = { status: 'queued' }) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) }
}

test('ticket HTTP adapter uses documented methods, encoded paths and no cache', async () => {
  const original = globalThis.fetch
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    return ok()
  }
  try {
    const ref = { departmentId: 'dep', ticketId: 'ticket' }
    await ticketApi.get(ref)
    await ticketApi.cancel(ref)
    await ticketApi.create('dep', { service_id: 'service', source: 'qr' })
    await ticketApi.incomplete('dep')
    assert.equal(calls[0].url, '/api/departments/dep/tickets/ticket')
    assert.equal(calls[0].options.cache, 'no-store')
    assert.equal(calls[1].url, '/api/departments/dep/tickets/ticket:cancel')
    assert.equal(calls[1].options.method, 'POST')
    assert.deepEqual(JSON.parse(calls[2].options.body), { service_id: 'service', source: 'qr' })
    assert.equal(calls[3].url, '/api/departments/dep/tickets/incomplete')
  } finally { globalThis.fetch = original }
})

test('HTTP adapter exposes 409 and does not retry POST', async () => {
  const original = globalThis.fetch
  let calls = 0
  globalThis.fetch = async () => { calls++; return { ok: false, status: 409 } }
  try {
    await assert.rejects(ticketApi.cancel({ departmentId: 'dep', ticketId: 'ticket' }), { status: 409 })
    assert.equal(calls, 1)
  } finally { globalThis.fetch = original }
})

test('staff HTTP helpers hit window, ticket, staff and issue paths', async () => {
  const original = globalThis.fetch
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push({ url, method: options.method ?? 'GET', body: options.body })
    return ok({})
  }
  try {
    const departmentId = 'dep'
    const windowId = 'win'
    await windowsApi.list(departmentId)
    await windowsApi.open(departmentId, windowId, { open_service_ids: ['svc'] })
    await windowsApi.close(departmentId, windowId)
    await windowsApi.queue(departmentId, windowId)
    await windowsApi.callNext(departmentId, windowId)
    await windowsApi.start(departmentId, windowId)
    await windowsApi.noshow(departmentId, windowId)
    await windowsApi.complete(departmentId, windowId)
    await windowsApi.requeue(departmentId, windowId)
    await windowsApi.redirect(departmentId, windowId, { service_id: 'svc' })
    await windowsApi.update(departmentId, windowId, { service_ids: ['svc'] })
    await issuesApi.list(departmentId)
    await issuesApi.create(departmentId, { message: 'broken printer' })
    await issuesApi.resolve(departmentId, 'issue')
    await staffApi.list()
    await staffApi.create({ username: 'op', display_name: 'Op', password: 'password1', role: 'operator', department_id: departmentId })
    await staffApi.changePassword('staff', 'password2')

    const byUrl = Object.fromEntries(calls.map(call => [call.url, call]))
    assert.equal(byUrl['/api/departments/dep/windows'].method, 'GET')
    assert.equal(byUrl['/api/departments/dep/windows/win:open'].method, 'POST')
    assert.equal(byUrl['/api/departments/dep/windows/win:close'].method, 'POST')
    assert.equal(byUrl['/api/departments/dep/windows/win/queue'].method, 'GET')
    assert.equal(byUrl['/api/departments/dep/windows/win:call-next'].method, 'POST')
    assert.equal(byUrl['/api/departments/dep/windows/win:start'].method, 'POST')
    assert.equal(byUrl['/api/departments/dep/windows/win:noshow'].method, 'POST')
    assert.equal(byUrl['/api/departments/dep/windows/win:complete'].method, 'POST')
    assert.equal(byUrl['/api/departments/dep/windows/win:requeue'].method, 'POST')
    assert.equal(byUrl['/api/departments/dep/windows/win:redirect'].method, 'POST')
    assert.equal(byUrl['/api/departments/dep/windows/win'].method, 'PATCH')
    assert.ok(calls.some(call => call.url === '/api/departments/dep/issues' && call.method === 'GET'))
    assert.ok(calls.some(call => call.url === '/api/departments/dep/issues' && call.method === 'POST'))
    assert.equal(byUrl['/api/departments/dep/issues/issue:resolve'].method, 'POST')
    assert.ok(calls.some(call => call.url === '/api/staff' && call.method === 'GET'))
    assert.ok(calls.some(call => call.url === '/api/staff' && call.method === 'POST'))
    assert.equal(byUrl['/api/staff/staff/password'].method, 'PATCH')
    assert.deepEqual(JSON.parse(byUrl['/api/departments/dep/windows/win:open'].body), { open_service_ids: ['svc'] })
    assert.deepEqual(JSON.parse(byUrl['/api/departments/dep/windows/win:redirect'].body), { service_id: 'svc' })
  } finally { globalThis.fetch = original }
})
