import test from 'node:test';
import assert from 'node:assert/strict';
import { createOperator, listOperators, changePassword } from '../src/operator-accounts.js';

const departmentId = 'a3690000-0000-4000-8000-000000000000';
const otherDepartmentId = 'a3690001-0000-4000-8000-000000000000';
const staffId = 'b3690000-0000-4000-8000-000000000001';

function jsonResponse(status, body) {
  const text = body === undefined ? '' : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => text,
  };
}

test('operator create, list and password change hit /api/staff', async () => {
  const values = new Map([
    [
      'pochta-staff',
      JSON.stringify({
        id: 'b3690000-0000-4000-8000-000000000099',
        username: 'admin',
        display_name: 'Руководитель',
        department_id: departmentId,
        role: 'admin',
        is_active: true,
      }),
    ],
  ]);
  globalThis.sessionStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };

  const calls = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    if (url === '/api/staff' && (options?.method ?? 'GET') === 'GET') {
      return jsonResponse(200, [
        {
          id: staffId,
          username: 'test.operator',
          display_name: 'Демо',
          department_id: departmentId,
          role: 'operator',
          is_active: true,
        },
      ]);
    }
    if (url === '/api/staff' && options?.method === 'POST') {
      const payload = JSON.parse(options.body);
      if (payload.username === 'test.operator' && payload.department_id === departmentId) {
        return jsonResponse(409);
      }
      return jsonResponse(201, { id: staffId, ...payload, is_active: true });
    }
    if (url === `/api/staff/${staffId}/password` && options?.method === 'PATCH') {
      return jsonResponse(204);
    }
    return jsonResponse(404);
  };

  try {
    await createOperator({
      username: 'ok.user',
      display_name: 'Демо',
      department_id: departmentId,
      password: 'test-pass-1',
    });
    assert.equal(calls[0].url, '/api/staff');
    assert.equal(calls[0].options.method, 'POST');
    assert.deepEqual(JSON.parse(calls[0].options.body), {
      username: 'ok.user',
      display_name: 'Демо',
      department_id: departmentId,
      password: 'test-pass-1',
      role: 'operator',
    });

    const accounts = await listOperators();
    assert.equal(calls[1].url, '/api/staff');
    assert.equal(calls[1].options.method ?? 'GET', 'GET');
    assert.equal(accounts[0].username, 'test.operator');

    await assert.rejects(
      createOperator({
        username: 'test.operator',
        display_name: 'Демо',
        department_id: departmentId,
        password: 'test-pass-1',
      }),
    );
    await assert.rejects(
      createOperator({
        username: 'ab',
        display_name: 'Демо',
        department_id: departmentId,
        password: 'test-pass-1',
      }),
    );
    await assert.rejects(
      createOperator({
        username: 'bad user',
        display_name: 'Демо',
        department_id: departmentId,
        password: 'test-pass-1',
      }),
    );
    await assert.rejects(
      createOperator({
        username: 'ok.user',
        display_name: 'Демо',
        department_id: departmentId,
        password: 'short',
      }),
    );
    await assert.rejects(
      createOperator({
        username: 'ok.user',
        display_name: 'Демо',
        department_id: 'unknown',
        password: 'test-pass-1',
      }),
    );
    await assert.rejects(
      createOperator({
        username: 'ok.user',
        display_name: 'Демо',
        department_id: otherDepartmentId,
        password: 'test-pass-1',
      }),
    );

    await changePassword(staffId, 'test-pass-2');
    const passwordCall = calls.find((call) => call.url === `/api/staff/${staffId}/password`);
    assert.equal(passwordCall.options.method, 'PATCH');
    assert.deepEqual(JSON.parse(passwordCall.options.body), { password: 'test-pass-2' });
    assert.ok(calls.every((call) => !String(call.url).includes('pochta-demo-operators')));
  } finally {
    globalThis.fetch = original;
  }
});
