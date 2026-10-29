import test from 'node:test';
import assert from 'node:assert/strict';
import { createTicketStorage, referenceFromTicket } from '../src/tickets/storage.js';
import { createTicketSession } from '../src/tickets/session.js';

const ref = {
  departmentId: '11111111-1111-1111-1111-111111111111',
  ticketId: '22222222-2222-2222-2222-222222222222',
};
const ticket = (status) => ({
  id: ref.ticketId,
  department_id: ref.departmentId,
  status,
  ticket_label: 'А-001',
  window_id: null,
  estimated_wait_time: 0,
});
const tick = () => new Promise((resolve) => setTimeout(resolve, 5));

test('storage restores only validated IDs, handles corrupt or unavailable storage', () => {
  let raw;
  const storage = createTicketStorage(() => ({
    getItem: () => raw,
    setItem: (_, value) => {
      raw = value;
    },
  }));
  assert.equal(storage.save(ref), true);
  assert.deepEqual(storage.read(), ref);
  assert.deepEqual(JSON.parse(raw), ref);
  raw = '{broken';
  assert.equal(storage.read(), null);
  raw = JSON.stringify({ departmentId: '369000', ticketId: 'A-037' });
  assert.equal(storage.read(), null);
  const blocked = createTicketStorage(() => {
    throw new Error('blocked');
  });
  assert.equal(blocked.read(), null);
  assert.equal(blocked.save(ref), false);
  assert.deepEqual(referenceFromTicket(ticket('queued')), ref);
});

test('restores server state and retains last status during network failure', async () => {
  const states = [];
  let fails = false;
  const session = createTicketSession({
    ref,
    interval: 10000,
    onChange: (state) => states.push(state),
    api: {
      get: async () => {
        if (fails) throw new Error('offline');
        return ticket('queued');
      },
    },
  });
  try {
    session.start();
    await tick();
    assert.equal(states.at(-1).ticket.estimated_wait_time, 0);
    fails = true;
    session.refresh();
    await tick();
    assert.equal(states.at(-1).ticket.status, 'queued');
    assert.ok(states.at(-1).error);
    assert.equal(states.at(-1).stale, true);
    fails = false;
    session.refresh();
    await tick();
    assert.equal(states.at(-1).error, null);
    assert.equal(states.at(-1).stale, false);
  } finally {
    session.stop();
  }
});

test('late GET cannot overwrite cancellation, double clicks send one POST', async () => {
  let resolveOld;
  let gets = 0;
  let cancels = 0;
  const states = [];
  const session = createTicketSession({
    ref,
    interval: 10000,
    onChange: (state) => states.push(state),
    api: {
      get: async () =>
        ++gets === 1
          ? ticket('queued')
          : new Promise((resolve) => {
              resolveOld = resolve;
            }),
      cancel: async () => {
        cancels++;
        return ticket('canceled');
      },
    },
  });
  try {
    session.start();
    await tick();
    session.refresh();
    session.cancel();
    session.cancel();
    await tick();
    resolveOld(ticket('queued'));
    await tick();
    assert.equal(cancels, 1);
    assert.equal(states.at(-1).ticket.status, 'canceled');
  } finally {
    session.stop();
  }
});

test('409 cancellation is reconciled with GET, never shown as successful', async () => {
  let called = false;
  const states = [];
  const session = createTicketSession({
    ref,
    interval: 10000,
    onChange: (state) => states.push(state),
    api: {
      get: async () => ticket(called ? 'called' : 'queued'),
      cancel: async () => {
        called = true;
        throw Object.assign(new Error(), { status: 409 });
      },
    },
  });
  try {
    session.start();
    await tick();
    session.cancel();
    await tick();
    await tick();
    assert.equal(states.at(-1).ticket.status, 'called');
    assert.ok(states.some((state) => state.error?.includes('отмена недоступна')));
  } finally {
    session.stop();
  }
});

test('404 stops polling; stop ignores an in-flight response', async () => {
  let gets = 0;
  const session = createTicketSession({
    ref,
    interval: 1,
    onChange() {},
    api: {
      get: async () => {
        gets++;
        throw Object.assign(new Error(), { status: 404 });
      },
    },
  });
  session.start();
  await tick();
  await tick();
  assert.equal(gets, 1);
  session.stop();
  let resolve;
  let updates = 0;
  const other = createTicketSession({
    ref,
    onChange: () => updates++,
    api: {
      get: () =>
        new Promise((done) => {
          resolve = done;
        }),
    },
  });
  other.start();
  other.stop();
  resolve(ticket('queued'));
  await tick();
  assert.equal(updates, 0);
});

test('polling is sequential and stops at terminal state', async () => {
  let gets = 0;
  let resolve;
  const session = createTicketSession({
    ref,
    interval: 1,
    onChange() {},
    api: {
      get: () => {
        gets++;
        return new Promise((done) => {
          resolve = done;
        });
      },
    },
  });
  try {
    session.start();
    session.refresh();
    session.refresh();
    await tick();
    assert.equal(gets, 1);
    resolve(ticket('completed'));
    await tick();
    await tick();
    assert.equal(gets, 1);
  } finally {
    session.stop();
  }
});

test('stale queued state cannot trigger cancellation after 404', async () => {
  let missing = false;
  let cancels = 0;
  const session = createTicketSession({
    ref,
    interval: 10000,
    onChange() {},
    api: {
      get: async () => {
        if (missing) throw Object.assign(new Error(), { status: 404 });
        return ticket('queued');
      },
      cancel: async () => {
        cancels++;
        return ticket('canceled');
      },
    },
  });
  try {
    session.start();
    await tick();
    missing = true;
    session.refresh();
    await tick();
    session.cancel();
    await tick();
    assert.equal(cancels, 0);
  } finally {
    session.stop();
  }
});
