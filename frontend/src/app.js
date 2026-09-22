import { renderHtml } from './shared/render.js'
import './shared/assets.js'
import { escapeHtml } from './shared/html.js'
import { departmentIdFromSearch } from './shared/ids.js'
import { request, departmentPath, ticketApi } from './tickets/api.js'
import { createTicketStorage, referenceFromTicket } from './tickets/storage.js'
import { syncStoredTicket, TERMINAL_STATUSES } from './tickets/session.js'
import { INITIAL_DATE, INITIAL_MONTH, formatDate, formatMonth, getMonthDays, getMonthOffset, shiftMonth } from './calendar.js'

const root = document.querySelector('#root')
let departments = []
let services = []
let slots = []
let busy = false
let message = ''
let uncertainIssue = false
const ticketStorage = createTicketStorage()

const state = {
  booking: window.location.pathname.startsWith('/booking'),
  step: window.location.pathname.startsWith('/booking') ? 'place' : 'service',
  serviceId: null,
  query: '',
  departmentId: departmentIdFromSearch(location.search),
  date: INITIAL_DATE,
  month: INITIAL_MONTH,
  time: null,
  calendarExpanded: false,
}

const logo = (compact = false) => `<img class="logo${compact ? ' logo--compact' : ''}" src="/assets/logo.svg" alt="Почта России" decoding="sync" fetchpriority="high">`
const button = (label, action, disabled = false) => `<footer class="screen-footer"><button class="primary-button" data-action="${action}" ${disabled ? 'disabled' : ''}>${label}</button></footer>`
const currentDepartment = () => departments.find(department => department.id === state.departmentId)
const departmentText = () => currentDepartment()
  ? `<strong>Отделение № ${escapeHtml(currentDepartment().code)}</strong>: ${escapeHtml(currentDepartment().address)}` : ''

function getTimeGroups() {
  const times = [...new Set(slots.map(slot => slot.slot_time.slice(0, 5)))].sort()
  return [{ id: 'available', label: 'Доступное время', slots: times.map(time => ({
    time,
    disabled: !slots.some(slot => slot.slot_time.slice(0, 5) === time && slot.booked_count < slot.capacity),
  })) }]
}

async function loadServices() {
  services = await request(`${departmentPath(state.departmentId)}/services/active`)
}

async function loadSlots() {
  slots = []
  if (!state.date) return
  const query = new URLSearchParams({ slot_date: state.date, service_id: state.serviceId })
  slots = await request(`${departmentPath(state.departmentId)}/slots?${query}`)
}

async function issueTicket() {
  if (uncertainIssue) return
  const payload = { service_id: state.serviceId, source: state.booking ? 'web' : 'qr' }
  if (state.booking) {
    const slot = slots.find(slot => slot.slot_time.slice(0, 5) === state.time && slot.booked_count < slot.capacity)
    if (!slot) throw new Error('Выберите доступное время')
    payload.slot_id = slot.id
  }
  let ticket
  try {
    ticket = await ticketApi.create(state.departmentId, payload)
    const ref = referenceFromTicket(ticket)
    syncStoredTicket(ticketStorage, ticket)
    uncertainIssue = true // Keep the issuing form disabled until navigation completes.
    // URL is a recovery fallback when localStorage is unavailable.
    location.assign(`/?view=ticket&${new URLSearchParams(ref)}`)
  } catch (error) {
    // POST is deliberately not retried: the server may have issued a ticket.
    if (!error.status || error.status >= 500) {
      uncertainIssue = true
      throw new Error('Не удалось подтвердить выдачу. Не создавайте повторную запись: обратитесь к сотруднику.')
    }
    throw error
  }
}

function serviceScreen() {
  return `<main class="screen service-screen">
    <header class="service-header">${logo()}<p>${departmentText()}</p></header>
    <div class="service-grid">${services.map(serviceCard).join('')}</div>
    ${button(state.booking ? 'Выбрать дату и время' : 'Записаться в очередь', 'make-ticket', !state.serviceId)}
  </main>`
}

const SERVICE_ICON = {
  parcel_receive: 'receive-selected',
  parcel_send: 'send-selected',
  letters: 'letter-selected',
  payments: 'payments-selected',
  pension: 'receipt-selected',
  other: 'services-selected',
}

function serviceCard(service) {
  const selected = state.serviceId === service.id
  const className = `service-card${selected ? ' service-card--selected' : ''}`
  const icon = SERVICE_ICON[service.kind] || SERVICE_ICON.other

  return `
    <button class="${className}" data-service="${escapeHtml(service.id)}" aria-pressed="${selected}">
      <span>${escapeHtml(service.name)}</span>
      <span class="service-icon" aria-hidden="true" style="--service-icon: url('/assets/${icon}.svg')"></span>
    </button>
  `
}

function placeScreen() {
  const query = state.query.trim().toLocaleLowerCase('ru')
  const matches = departments.filter(department => (department.code + ' ' + department.address).toLocaleLowerCase('ru').includes(query))
  const results = matches.length
    ? `<div class="department-list">${matches.map(department => `
        <label class="department-row">
          <input type="radio" name="department" value="${escapeHtml(department.id)}" ${state.departmentId === department.id ? 'checked' : ''}>
          <span>Отделение № ${escapeHtml(department.code)}: ${escapeHtml(department.address)}</span>
        </label>
      `).join('')}</div>`
    : '<p class="empty-results">Отделение не найдено. Попробуйте изменить поиск.</p>'
  return `<main class="screen step-screen">${logo(true)}<section class="step-content"><h1>Выберите отделение почты</h1><input class="search-input" value="${escapeHtml(state.query)}" placeholder="Адрес или индекс" aria-label="Адрес или индекс">${results}</section>${button('Продолжить', 'place-next', !state.departmentId)}</main>`
}

function dateOption({ value, day, weekday, disabled }) {
  return `<button class="calendar-day${state.date === value ? ' is-selected' : ''}"
    data-date="${value}" aria-pressed="${state.date === value}" aria-label="${formatDate(value)}" ${disabled ? 'disabled' : ''}>
    ${state.calendarExpanded ? '' : `<span>${weekday}</span>`}<strong>${day}</strong>
  </button>`
}

function timeGroup({ id, label, slots }) {
  return `<section class="time-group" aria-labelledby="${id}-title">
    <div class="time-group-heading">
      <h2 id="${id}-title">${label}</h2>
      <div class="time-scroll-controls">
        <button data-scroll-group="${id}" data-direction="-1" aria-label="${label}: раньше">‹</button>
        <button data-scroll-group="${id}" data-direction="1" aria-label="${label}: позже">›</button>
      </div>
    </div>
    <div class="choice-strip" data-scroll="${id}" tabindex="0" aria-label="${label}: время записи">
      ${slots.map(({ time, disabled }) => `<button
        class="time-slot${state.time === time ? ' is-selected' : ''}"
        data-time="${time}" aria-pressed="${state.time === time}" ${disabled ? 'disabled' : ''}>${time}</button>`).join('')}
    </div>
  </section>`
}

function calendarDates() {
  if (!state.calendarExpanded) {
    return `<div id="calendar-dates" class="choice-strip calendar-days" data-scroll="dates" tabindex="0" aria-label="Дни месяца">
      ${getMonthDays(state.month).map(dateOption).join('')}
    </div>`
  }
  return `<div id="calendar-dates" class="calendar-month" aria-label="Полный календарь">
    ${['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map(day => `<span class="weekday-label">${day}</span>`).join('')}
    ${'<span aria-hidden="true"></span>'.repeat(getMonthOffset(state.month))}
    ${getMonthDays(state.month, true).map(dateOption).join('')}
  </div>`
}

function dateScreen() {
  return `<main class="screen step-screen date-screen">
    ${logo(true)}
    <section class="step-content">
      <h1>Выберите дату и время</h1>
      <div class="calendar">
        <header class="calendar-header">
          <button data-month="-1" aria-label="Предыдущий месяц" ${state.month === INITIAL_MONTH ? 'disabled' : ''}>‹</button>
          <button class="calendar-toggle" data-action="toggle-calendar" aria-expanded="${state.calendarExpanded}" aria-controls="calendar-dates">
            ${formatMonth(state.month)} <span class="calendar-chevron" aria-hidden="true"></span>
          </button>
          <button data-month="1" aria-label="Следующий месяц">›</button>
        </header>
        ${calendarDates()}
        <div class="time-groups">${!busy && !slots.length
          ? '<p class="empty-results" role="status">Слотов еще нет</p>'
          : getTimeGroups(state.date).map(timeGroup).join('')}</div>
      </div>
    </section>
    ${button('Записаться', 'date-next', !state.date || !state.time)}
  </main>`
}


function render() {
  const scrollPositions = new Map([...root.querySelectorAll('.choice-strip')].map(strip => [strip.dataset.scroll, strip.scrollLeft]))
  const focusKey = document.activeElement?.dataset
  const focusSelector = focusKey?.date ? '[data-date="' + focusKey.date + '"]'
    : focusKey?.time ? '[data-time="' + focusKey.time + '"]'
    : focusKey?.service ? '[data-service="' + focusKey.service + '"]'
    : focusKey?.month ? '[data-month="' + focusKey.month + '"]'
    : focusKey?.action === 'toggle-calendar' ? '[data-action="toggle-calendar"]' : null
  renderHtml(root, state.step === 'place' ? placeScreen() : state.step === 'date' ? dateScreen() : serviceScreen())
  if (message) {
    const notice = document.createElement('p')
    notice.setAttribute('role', 'status')
    notice.textContent = message
    root.querySelector('main').prepend(notice)
    if (!busy && !uncertainIssue) {
      const retry = document.createElement('button')
      retry.dataset.action = 'retry-load'
      retry.textContent = 'Обновить данные'
      notice.append(document.createElement('br'), retry)
    }
  }
  if (busy || uncertainIssue) root.querySelectorAll('button, input').forEach(control => { control.disabled = true })
  root.querySelectorAll('.choice-strip').forEach(strip => { strip.scrollLeft = scrollPositions.get(strip.dataset.scroll) || 0 })
  if (focusSelector) root.querySelector(focusSelector)?.focus({ preventScroll: true })
}

function setSelectedChoice(selector, selected) {
  root.querySelectorAll(selector).forEach(option => {
    const isSelected = option === selected
    option.classList.toggle('is-selected', isSelected)
    option.setAttribute('aria-pressed', String(isSelected))
  })
}

root.addEventListener('click', async (event) => {
  const target = event.target.closest('button, input[type="radio"]')
  if (!target || target.disabled || busy) return
  if (target.dataset.action === 'retry-load') {
    await updateAsync(state.step === 'date' ? loadSlots : initialize)
    return
  }
  if (target.dataset.scrollGroup) {
    const strip = root.querySelector(`[data-scroll="${target.dataset.scrollGroup}"]`)
    strip.scrollBy({ left: Number(target.dataset.direction) * strip.clientWidth * 0.8, behavior: 'smooth' })
    return
  }
  // A selection does not need a full screen render. This keeps the logo stable on mobile.
  if (target.dataset.time) {
    state.time = target.dataset.time
    setSelectedChoice('[data-time]', target)
    root.querySelector('[data-action="date-next"]').disabled = !state.date
    return
  }
  if (target.dataset.date) {
    state.date = target.dataset.date
    state.time = null
    await updateAsync(loadSlots)
    return
  }
  if (target.dataset.service) {
    if (state.serviceId === target.dataset.service) return
    state.serviceId = target.dataset.service
    // Keep the same icon resource and DOM nodes; only change the CSS color.
    root.querySelectorAll('[data-service]').forEach(option => {
      const selected = option === target
      option.classList.toggle('service-card--selected', selected)
      option.setAttribute('aria-pressed', String(selected))
    })
    root.querySelector('[data-action="make-ticket"]').disabled = false
    return
  }
  if (target.name === 'department') {
    state.departmentId = target.value
    root.querySelector('[data-action="place-next"]').disabled = false
    return
  }
  const previousStep = state.step
  if (target.dataset.action === 'toggle-calendar') state.calendarExpanded = !state.calendarExpanded
  if (target.dataset.month) {
    state.month = shiftMonth(state.month, Number(target.dataset.month))
    state.date = getMonthDays(state.month)[0]?.value || null
    state.time = null
    root.querySelectorAll('.choice-strip').forEach(strip => { strip.scrollLeft = 0 })
  }
  if (target.dataset.action === 'place-next' && state.departmentId) {
    await updateAsync(async () => { await loadServices(); state.step = 'service' })
    return
  }
  if (target.dataset.action === 'date-next' && state.departmentId && state.serviceId && state.date && state.time) {
    await updateAsync(issueTicket)
    return
  }
  if (target.dataset.action === 'make-ticket' && state.serviceId) {
    await updateAsync(async () => {
      if (state.booking) { await loadSlots(); state.step = 'date' }
      else await issueTicket()
    })
    return
  }
  if (target.dataset.month) { await updateAsync(loadSlots); return }
  render()
  if (target.dataset.action === 'toggle-calendar' && !state.calendarExpanded) {
    const strip = root.querySelector('[data-scroll="dates"]')
    const selected = strip?.querySelector('.is-selected')
    if (selected) strip.scrollLeft = selected.offsetLeft - strip.offsetLeft - 12
  }
  if (previousStep !== state.step) window.scrollTo(0, 0)
})

root.addEventListener('input', (event) => {
  if (!event.target.matches('.search-input')) return
  state.query = event.target.value
  state.departmentId = null
  render()
  const input = root.querySelector('.search-input')
  input.focus()
  input.setSelectionRange(input.value.length, input.value.length)
})

async function updateAsync(action) {
  busy = true
  message = 'Загрузка…'
  render()
  try {
    await action()
    message = ''
  } catch (error) {
    message = error.status === 409 ? 'Выбранное время уже занято. Выберите другое.'
      : error.status ? 'Сервис недоступен или запрос отклонён. Повторите позже.'
        : error.message === 'Failed to fetch' ? 'Нет связи с сервером. Проверьте подключение.' : error.message
  } finally {
    busy = false
    render()
  }
}

async function restoreVisitorSession() {
  const ref = ticketStorage.read()
  if (!ref) {
    uncertainIssue = false
    return false
  }

  try {
    const ticket = await ticketApi.get(ref)
    syncStoredTicket(ticketStorage, ticket)
    if (TERMINAL_STATUSES.has(ticket.status)) {
      uncertainIssue = false
      return false
    }
  } catch (error) {
    if (error.status === 404) {
      ticketStorage.clear()
      uncertainIssue = false
      return false
    }
  }

  location.replace(`/?view=ticket&${new URLSearchParams(ref)}`)
  return true
}

async function initialize() {
  departments = (await request('/departments')).filter(department => department.is_active)
  if (!state.booking || state.step === 'service') {
    if (!currentDepartment()) throw new Error('QR-код должен содержать UUID отделения.')
    await loadServices()
  }
}

window.addEventListener('pageshow', async event => {
  if (!event.persisted && !uncertainIssue) return
  if (await restoreVisitorSession()) return
  render()
})

if (!(await restoreVisitorSession())) await updateAsync(initialize)
