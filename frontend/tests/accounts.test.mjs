import test from 'node:test';
import assert from 'node:assert/strict';
import { createOperator, initializeManager, listOperators, authenticate, changePassword, changeBranch } from '../src/operator-accounts.js';

test('operator creation, duplicate check, password and branch changes', async () => {
  const values = new Map();
  globalThis.localStorage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
  await createOperator({ login: 'test.operator', name: 'Демо', branch: '369000', password: 'test-pass-1' });
  const [account] = listOperators();
  assert.equal(await authenticate('TEST.OPERATOR', 'test-pass-1'), account.id);
  assert.ok(!JSON.stringify(account).includes('test-pass-1'));
  await assert.rejects(authenticate('test.operator', 'wrong'));
  await assert.rejects(createOperator({ login: 'test.operator', name: 'Демо', branch: '369000', password: 'test-pass-1' }));
  await changePassword(account.id, 'test-pass-2');
  await assert.rejects(authenticate('test.operator', 'test-pass-1'));
  assert.equal(await authenticate('test.operator', 'test-pass-2'), account.id);
  changeBranch(account.id, '369001');
  assert.equal(listOperators()[0].branch, '369001');
  assert.throws(() => changeBranch(account.id, 'unknown'));
  assert.equal(account.role, 'operator');
  await initializeManager({ login: 'test.manager', name: 'Руководитель', branch: '369000', password: 'manager-test' });
  assert.equal(listOperators().find(item => item.login === 'test.manager').role, 'manager');
  await assert.rejects(initializeManager({ login: 'another.manager', name: 'Другой', branch: '369000', password: 'manager-test' }));
});
