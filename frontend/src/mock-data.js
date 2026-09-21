import { localDateValue } from './calendar.js'

// Demo data only. Replace this module with the API adapter when the backend is ready.
export const branches = [
  { id: '369000', address: 'г. Черкесск, ул. Первомайская, зд. 30.' },
  { id: '369001', address: 'г. Черкесск, пр-кт Ленина, зд. 152' },
]

export const mockTicket = { number: '№А-037', waitMinutes: 12 }

function createTimes(startHour, endHour) {
  return Array.from({ length: (endHour - startHour) * 6 }, (_, index) => {
    const minutes = startHour * 60 + index * 10
    return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}`
  })
}

export function getTimeGroups(date, now = new Date()) {
  return [
    { id: 'morning', label: 'Утро', times: createTimes(9, 12) },
    { id: 'afternoon', label: 'День', times: createTimes(13, 17) },
    { id: 'evening', label: 'Вечер', times: createTimes(18, 20) },
  ].map(group => ({
    ...group,
    slots: group.times.map(time => {
      const [hours, minutes] = time.split(':').map(Number)
      const expired = date && (date < localDateValue(now) ||
        (date === localDateValue(now) && hours * 60 + minutes <= now.getHours() * 60 + now.getMinutes()))
      return { time, disabled: Boolean(expired) || ['9:20', '13:20', '13:30'].includes(time) }
    }),
  }))
}
