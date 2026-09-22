import test from 'node:test'
import assert from 'node:assert/strict'
import { getMonthDays, localDateValue, shiftMonth } from '../src/calendar.js'

test('booking calendar uses local dates and disables past days', () => {
  assert.equal(localDateValue(new Date(2027, 0, 2)), '2027-01-02')
  const days = getMonthDays('2027-01', true, '2027-01-02')
  assert.equal(days[0].disabled, true)
  assert.equal(days[1].disabled, false)
  assert.equal(getMonthDays('2026-12', false, '2027-01-02').length, 0)
  assert.equal(shiftMonth('2026-12', 1), '2027-01')
})
