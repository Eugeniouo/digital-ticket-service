import test from 'node:test';
import assert from 'node:assert/strict';
import { createOperator, initializeManager, listOperators, authenticate, changePassword } from '../src/operator-accounts.js';

test('operator creation, duplicate check and password change', async () => {
  const values = new Map();
  globalThis.localStorage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
  await createOperator({ username: 'test.operator', display_name: 'Демо', department_id: '369000', password: 'test-pass-1' });
  const [account] = listOperators();
  assert.equal(await authenticate('TEST.OPERATOR', 'test-pass-1'), account.id);
  assert.equal(account.username, 'test.operator');
  assert.equal(account.display_name, 'Демо');
  assert.equal(account.department_id, '369000');
  assert.equal(account.role, 'operator');
  assert.equal(account.is_active, true);
  assert.ok(!JSON.stringify(account).includes('test-pass-1'));
  await assert.rejects(authenticate('test.operator', 'wrong'));
  await assert.rejects(createOperator({ username: 'test.operator', display_name: 'Демо', department_id: '369000', password: 'test-pass-1' }));
  await assert.rejects(createOperator({ username: 'ab', display_name: 'Демо', department_id: '369000', password: 'test-pass-1' }));
  await assert.rejects(createOperator({ username: 'bad user', display_name: 'Демо', department_id: '369000', password: 'test-pass-1' }));
  await assert.rejects(createOperator({ username: 'ok.user', display_name: 'Демо', department_id: '369000', password: 'short' }));
  await assert.rejects(createOperator({ username: 'ok.user', display_name: 'Демо', department_id: 'unknown', password: 'test-pass-1' }));
  await changePassword(account.id, 'test-pass-2');
  await assert.rejects(authenticate('test.operator', 'test-pass-1'));
  assert.equal(await authenticate('test.operator', 'test-pass-2'), account.id);
  await initializeManager({ username: 'test.manager', display_name: 'Руководитель', department_id: '369000', password: 'manager-test' });
  assert.equal(listOperators().find(item => item.username === 'test.manager').role, 'admin');
  await assert.rejects(initializeManager({ username: 'another.manager', display_name: 'Другой', department_id: '369000', password: 'manager-test' }));
});
