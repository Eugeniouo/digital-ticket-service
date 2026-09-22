// Calendar days follow the visitor's local day. Slot availability comes from the API.
export function localDateValue(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
export const FIRST_DATE = localDateValue()
export const INITIAL_DATE = FIRST_DATE
export const INITIAL_MONTH = FIRST_DATE.slice(0, 7)

const parseDate = value => new Date(`${value}T12:00:00`)
export const formatDate = value => parseDate(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
export const formatMonth = month => {
  const label = parseDate(`${month}-01`).toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
  return label[0].toUpperCase() + label.slice(1).replace(/\s*г\.$/, '')
}

export function shiftMonth(month, offset) {
  const date = parseDate(`${month}-01`)
  date.setMonth(date.getMonth() + offset)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

export function getMonthDays(month, includeUnavailable = false, today = localDateValue()) {
  const start = parseDate(`${month}-01`)
  const count = new Date(start.getFullYear(), start.getMonth() + 1, 0).getDate()
  return Array.from({ length: count }, (_, index) => {
    const day = index + 1
    const value = `${month}-${String(day).padStart(2, '0')}`
    const weekday = parseDate(value).toLocaleDateString('ru-RU', { weekday: 'short' })
    return { value, day, weekday: weekday[0].toUpperCase() + weekday.slice(1), disabled: value < today }
  }).filter(date => includeUnavailable || !date.disabled)
}

export const getMonthOffset = month => (parseDate(`${month}-01`).getDay() + 6) % 7
