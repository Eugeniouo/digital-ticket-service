import test from 'node:test';
import assert from 'node:assert/strict';
import { escapeHtml, button, badge } from '../src/shared/html.js';
import { createStaffViews } from '../src/staff-views.js';
import { dateOffset, dateValueFromOffset } from '../src/staff-analytics.js';

const catalog = [
  { id: '11111111-1111-4111-8111-111111111111', name: 'Получение посылки' },
  { id: '22222222-2222-4222-8222-222222222222', name: 'Отправка посылки' },
];

function makeState() {
  return {
    queue: [],
    current: null,
    opened: true,
    enabled: catalog.map((service) => service.id),
    served: 0,
    issues: [],
    rules: [10, 10, 20, 2],
    services: catalog,
    windows: [],
    staffList: [],
    windowLabel: 'Окно 1',
    operatorName: 'Оператор',
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
  assert.doesNotMatch(views.operator(), /Повторить вызов/);
  state.current = {
    id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
    ticket_label: 'П-001',
    service_id: catalog[0].id,
    source: 'qr',
    wait: 5,
    status: 'called',
  };
  assert.match(views.operator(), /Начать обслуживание/);
  assert.doesNotMatch(views.operator(), /Повторить вызов/);
  state.current.started = true;
  state.current.status = 'serving';
  assert.match(views.operator(), /Завершить обслуживание/);
  state.current = null;
  state.opened = false;
  assert.match(views.operator(), /Окно закрыто/);
});

test('windows and overview use API rows instead of a hardcoded catalog', () => {
  const state = makeState();
  const views = createStaffViews(() => state);
  assert.doesNotMatch(views.windows(), /Елена Петрова/);
  assert.doesNotMatch(views.overview(), /Елена Петрова/);
  assert.doesNotMatch(views.overview(), /Обслужено · демо/);
  assert.match(views.windows(), /Окон в отделении нет/);
  state.windows = [
    {
      id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1',
      label: 'Окно 1',
      status: 'open',
      service_ids: [catalog[0].id],
      open_service_ids: [catalog[0].id],
      current_operator_id: 'cccccccc-cccc-4ccc-8ccc-ccccccccccc1',
    },
  ];
  state.staffList = [{ id: 'cccccccc-cccc-4ccc-8ccc-ccccccccccc1', display_name: 'Иван Оператор' }];
  assert.match(views.windows(), /Окно 1/);
  assert.match(views.windows(), /Иван Оператор/);
  assert.doesNotMatch(views.windows(), /Окно № 3/);
});

test('problem text cannot inject HTML into overview', () => {
  const state = makeState();
  state.issues.push({ id: '1', message: '<img src=x onerror=alert(1)>', status: 'open' });
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
