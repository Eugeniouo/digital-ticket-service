import test from 'node:test'
import assert from 'node:assert/strict'
import { getMonthDays, localDateValue, shiftMonth } from '../src/calendar.js'
import { getTimeGroups } from '../src/mock-data.js'

test('booking calendar uses local dates and disables past days', () => {
  assert.equal(localDateValue(new Date(2027, 0, 2)), '2027-01-02')
  const days = getMonthDays('2027-01', true, '2027-01-02')
  assert.equal(days[0].disabled, true)
  assert.equal(days[1].disabled, false)
  assert.equal(getMonthDays('2026-12', false, '2027-01-02').length, 0)
  assert.equal(shiftMonth('2026-12', 1), '2027-01')
})

test('booking slots exclude elapsed time but keep future slots', () => {
  const now = new Date(2027, 0, 2, 18, 10)
  const slots = date => getTimeGroups(date, now).flatMap(group => group.slots)
  assert.equal(slots('2027-01-02').find(slot => slot.time === '18:10').disabled, true)
  assert.equal(slots('2027-01-02').find(slot => slot.time === '18:20').disabled, false)
  assert.ok(slots('2027-01-01').every(slot => slot.disabled))
  assert.equal(slots('2027-01-03').find(slot => slot.time === '9:00').disabled, false)
})
