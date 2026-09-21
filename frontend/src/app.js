import { renderHtml } from './shared/render.js'
import './shared/assets.js'
import { escapeHtml } from './shared/html.js'
import { branches, getTimeGroups, mockTicket } from './mock-data.js'
import { INITIAL_DATE, INITIAL_MONTH, formatDate, formatMonth, getMonthDays, getMonthOffset, shiftMonth } from './calendar.js'

const root = document.querySelector('#root')
const services = [
  ['send', 'Отправить посылку', '/assets/send.svg'],
  ['receive', 'Получить посылку', '/assets/receive.svg'],
  ['pension', 'Пенсия и пособия', '/assets/receipt.svg'],
  ['payments', 'Платежи и переводы', '/assets/payments.svg'],
  ['letters', 'Заказные письма', '/assets/letter.svg'],
  ['other', 'Прочие услуги', '/assets/services.svg'],
]

const state = {
  booking: window.location.pathname.startsWith('/booking'),
  step: window.location.pathname.startsWith('/booking') ? 'place' : 'service',
  service: null,
  query: '',
  branch: branches.find(branch => branch.id === new URLSearchParams(location.search).get('branch'))?.id || null,
  date: INITIAL_DATE,
  month: INITIAL_MONTH,
  time: null,
  calendarExpanded: false,
}

const logo = (compact = false) => `<img class="logo${compact ? ' logo--compact' : ''}" src="/assets/logo.svg" alt="Почта России" decoding="sync" fetchpriority="high">`
const button = (label, action, disabled = false) => `<footer class="screen-footer"><button class="primary-button" data-action="${action}" ${disabled ? 'disabled' : ''}>${label}</button></footer>`
const currentBranch = () => branches.find(branch => branch.id === state.branch) || branches[1]
const branchText = () => `<strong>Отделение № ${currentBranch().id}</strong>: ${currentBranch().address}`

function serviceScreen() {
  return `<main class="screen service-screen">
    <header class="service-header">${logo()}<p>${branchText()}</p></header>
    <div class="service-grid">${services.map(([id, label, icon]) => `<button class="service-card${state.service === id ? ' service-card--selected' : ''}" data-service="${id}" aria-pressed="${state.service === id}"><span>${label}</span><span class="service-icon" aria-hidden="true" style="--service-icon: url('${icon.replace('.svg', '-selected.svg')}')"></span></button>`).join('')}</div>
    ${button(state.booking ? 'Выбрать дату и время' : 'Записаться в очередь', 'make-ticket', !state.service)}
  </main>`
}

function placeScreen() {
  const query = state.query.trim().toLocaleLowerCase('ru')
  const matches = branches.filter(branch => (branch.id + ' ' + branch.address).toLocaleLowerCase('ru').includes(query))
  const results = !query ? '' : matches.length
    ? `<div class="branch-list">${matches.map(branch => `<label class="branch-row"><input type="radio" name="branch" value="${branch.id}" ${state.branch === branch.id ? 'checked' : ''}><span>№ ${branch.id}: ${branch.address}</span></label>`).join('')}</div>`
    : '<p class="empty-results">Отделение не найдено. Попробуйте «Черкесск» или индекс 369001.</p>'
  return `<main class="screen step-screen">${logo(true)}<section class="step-content"><h1>Выберите отделение почты</h1><input class="search-input" value="${escapeHtml(state.query)}" placeholder="Адрес или индекс" aria-label="Адрес или индекс">${results}</section>${button('Продолжить', 'place-next', !state.branch)}</main>`
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
        <div class="time-groups">${getTimeGroups(state.date).map(timeGroup).join('')}</div>
      </div>
    </section>
    ${button('Записаться', 'date-next', !state.date || !state.time)}
  </main>`
}

function ticketScreen() {
  const time = state.booking ? `${formatDate(state.date)}, ${state.time}` : `Примерное время ожидания <b>${mockTicket.waitMinutes}&nbsp;мин</b>`
  return `<main class="screen ticket-screen">${logo()}<section class="ticket-card" aria-label="Ваш талон"><div class="ticket-main"><h1>Ваш талон</h1><strong class="ticket-number">${mockTicket.number}</strong><p class="ticket-time"><img src="/assets/clock.svg" alt=""><span>${time}</span></p></div><p class="ticket-branch">${branchText()}</p></section><footer class="screen-footer"><button class="cancel-button" data-action="cancel">Отменить запись</button></footer></main>`
}

// Native dialog keeps focus inside the confirmation and makes the ticket inert.
const cancelDialog = document.createElement('dialog')
cancelDialog.className = 'cancel-dialog'
cancelDialog.tabIndex = -1
cancelDialog.setAttribute('aria-labelledby', 'cancel-title')
cancelDialog.setAttribute('aria-describedby', 'cancel-description')
cancelDialog.innerHTML = `
  <div class="cancel-warning" aria-hidden="true"><img src="/assets/warning.svg" width="28" height="28" alt=""></div>
  <h2 id="cancel-title">Отмена записи</h2>
  <p id="cancel-description">Вы уверены, что хотите отменить свою запись и аннулировать талон?</p>
  <button class="confirm-cancel-button" type="button">Отменить запись</button>
  <button class="return-button" type="button">Вернуться обратно</button>
`
document.body.append(cancelDialog)

function openCancelDialog() {
  if (state.step !== 'ticket' || cancelDialog.open) return
  document.body.classList.add('cancellation-open')
  cancelDialog.showModal()
  cancelDialog.focus({ preventScroll: true })
}

cancelDialog.querySelector('.return-button').addEventListener('click', () => cancelDialog.close())
cancelDialog.querySelector('.confirm-cancel-button').addEventListener('click', () => {
  state.service = null
  if (state.booking) state.branch = null
  state.query = ''
  state.step = state.booking ? 'place' : 'service'
  cancelDialog.close()
  render()
  window.scrollTo(0, 0)
})
cancelDialog.addEventListener('close', () => {
  document.body.classList.remove('cancellation-open')
  root.querySelector('[data-action="cancel"]')?.focus({ preventScroll: true })
})

function render() {
  const scrollPositions = new Map([...root.querySelectorAll('.choice-strip')].map(strip => [strip.dataset.scroll, strip.scrollLeft]))
  const focusKey = document.activeElement?.dataset
  const focusSelector = focusKey?.date ? '[data-date="' + focusKey.date + '"]'
    : focusKey?.time ? '[data-time="' + focusKey.time + '"]'
    : focusKey?.service ? '[data-service="' + focusKey.service + '"]'
    : focusKey?.month ? '[data-month="' + focusKey.month + '"]'
    : focusKey?.action === 'toggle-calendar' ? '[data-action="toggle-calendar"]' : null
  renderHtml(root, state.step === 'place' ? placeScreen() : state.step === 'date' ? dateScreen() : state.step === 'ticket' ? ticketScreen() : serviceScreen())
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

root.addEventListener('click', (event) => {
  const target = event.target.closest('button, input[type="radio"]')
  if (!target || target.disabled) return
  if (target.dataset.scrollGroup) {
    const strip = root.querySelector(`[data-scroll="${target.dataset.scrollGroup}"]`)
    strip.scrollBy({ left: Number(target.dataset.direction) * strip.clientWidth * 0.8, behavior: 'smooth' })
    return
  }
  if (target.dataset.action === 'cancel') {
    openCancelDialog()
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
    render()
    return
  }
  if (target.dataset.service) {
    if (state.service === target.dataset.service) return
    state.service = target.dataset.service
    // Keep the same icon resource and DOM nodes; only change the CSS color.
    root.querySelectorAll('[data-service]').forEach(option => {
      const selected = option === target
      option.classList.toggle('service-card--selected', selected)
      option.setAttribute('aria-pressed', String(selected))
    })
    root.querySelector('[data-action="make-ticket"]').disabled = false
    return
  }
  if (target.name === 'branch') {
    state.branch = target.value
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
  if (target.dataset.action === 'place-next' && state.branch) state.step = 'service'
  if (target.dataset.action === 'date-next' && state.branch && state.service && state.date && state.time) {
    const available = getTimeGroups(state.date).some(group => group.slots.some(slot => slot.time === state.time && !slot.disabled))
    if (available) state.step = 'ticket'
    else state.time = null
  }
  if (target.dataset.action === 'make-ticket' && state.service) state.step = state.booking ? 'date' : 'ticket'
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
  state.branch = null
  render()
  const input = root.querySelector('.search-input')
  input.focus()
  input.setSelectionRange(input.value.length, input.value.length)
})

render()
