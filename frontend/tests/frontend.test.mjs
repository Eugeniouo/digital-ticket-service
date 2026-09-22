import test from 'node:test';
import assert from 'node:assert/strict';
import { escapeHtml, button, badge } from '../src/shared/html.js';
import { createStaffViews } from '../src/staff-views.js';
import { departments, servicesForDepartment } from '../src/mock-data.js';
import { dateOffset, dateValueFromOffset } from '../src/staff-analytics.js';

const catalog = servicesForDepartment(departments[0].id);

function makeState() {
  return {
    queue: [], current: null, opened: true,
    closing: false, enabled: catalog.map(service => service.id), served: 0, problems: [],
    rules: [10, 10, 20, 2],
    services: catalog,
  };
}

test('HTML helpers escape text and attributes', () => {
  assert.equal(escapeHtml('<script>"&'), '&lt;script&gt;&quot;&amp;');
  assert.match(button('<Click>', 'call', '', true), /disabled/);
  assert.match(button('<Click>', 'call'), /&lt;Click&gt;/);
  assert.match(badge('<tag>'), /&lt;tag&gt;/);
});

test('all staff views render without mutating state', () => {
  const state = makeState();
  const before = JSON.stringify(state);
  const views = createStaffViews(() => state);
  for (const render of Object.values(views)) {
    assert.equal(typeof render(), 'string');
  }
  assert.equal(JSON.stringify(state), before);
});

test('operator view follows current state', () => {
  const state = makeState();
  const views = createStaffViews(() => state);
  assert.match(views.operator(), /Готовы к следующему клиенту/);
  state.current = {
    id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
    ticket_label: 'П-001',
    service_id: catalog[0].id,
    source: 'qr',
    wait: 5,
  };
  assert.match(views.operator(), /Начать обслуживание/);
  state.current.started = true;
  assert.match(views.operator(), /Завершить обслуживание/);
  state.current = null;
  state.opened = false;
  assert.match(views.operator(), /Окно закрыто/);
});

test('problem text cannot inject HTML into overview', () => {
  const state = makeState();
  state.problems.push('<img src=x onerror=alert(1)>');
  assert.doesNotMatch(createStaffViews(() => state).overview(), /<img src=x/);
});

test('calendar accepts past dates and rejects invalid or future dates', () => {
  const today = new Date(2026, 8, 21);
  assert.equal(dateOffset('2026-09-21', today), 0);
  assert.equal(dateOffset('2026-09-01', today), -20);
  assert.equal(dateOffset('2026-09-22', today), null);
  assert.equal(dateOffset('2026-02-30', today), null);
  assert.equal(dateOffset('', today), null);
  assert.equal(dateValueFromOffset(-20, today), '2026-09-01');
});
