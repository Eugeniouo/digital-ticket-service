import test from 'node:test'
import assert from 'node:assert/strict'
import { ticketApi } from '../src/tickets/api.js'

test('ticket HTTP adapter uses documented methods, encoded paths and no cache', async () => {
  const original = globalThis.fetch
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    return { ok: true, json: async () => ({ status: 'queued' }) }
  }
  try {
    const ref = { departmentId: 'dep', ticketId: 'ticket' }
    await ticketApi.get(ref)
    await ticketApi.cancel(ref)
    await ticketApi.create('dep', { service_id: 'service', source: 'qr' })
    assert.equal(calls[0].url, '/api/departments/dep/tickets/ticket')
    assert.equal(calls[0].options.cache, 'no-store')
    assert.equal(calls[1].url, '/api/departments/dep/tickets/ticket:cancel')
    assert.equal(calls[1].options.method, 'POST')
    assert.deepEqual(JSON.parse(calls[2].options.body), { service_id: 'service', source: 'qr' })
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
