import { localDateValue } from './calendar.js'

// Demo catalog in API DTO shape. Replace with GET /api/departments and nested services.
export const departments = [
  {
    id: 'a3690000-0000-4000-8000-000000000000',
    code: '369000',
    address: 'г. Черкесск, ул. Первомайская, зд. 30.',
    open_time: '09:00:00',
    close_time: '18:00:00',
    is_active: true,
  },
  {
    id: 'a3690001-0000-4000-8000-000000000000',
    code: '369001',
    address: 'г. Черкесск, пр-кт Ленина, зд. 152',
    open_time: '09:00:00',
    close_time: '18:00:00',
    is_active: true,
  },
]

const SERVICE_SPECS = [
  { name: 'Получение посылки', duration_time: 10, kind: 'parcel_receive' },
  { name: 'Отправка посылки', duration_time: 10, kind: 'parcel_send' },
  { name: 'Заказные письма', duration_time: 10, kind: 'letters' },
  { name: 'Платежи и переводы', duration_time: 10, kind: 'payments' },
  { name: 'Пенсия и пособия', duration_time: 15, kind: 'pension' },
  { name: 'Прочие услуги', duration_time: 10, kind: 'other' },
]

export const services = departments.flatMap((department, departmentIndex) =>
  SERVICE_SPECS.map((spec, serviceIndex) => ({
    id: `a369000${departmentIndex}-0001-4000-8000-${String(serviceIndex + 1).padStart(12, '0')}`,
    department_id: department.id,
    name: spec.name,
    kind: spec.kind,
    duration_time: spec.duration_time,
    is_active: true,
  })),
)

export function servicesForDepartment(departmentId) {
  return services.filter(service => service.department_id === departmentId)
}

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
