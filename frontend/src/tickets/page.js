import { renderHtml } from '../shared/render.js'
import { escapeHtml as esc } from '../shared/html.js'
import { ticketApi } from './api.js'
import { createTicketStorage, validReference } from './storage.js'
import { createTicketSession, syncStoredTicket, TERMINAL_STATUSES } from './session.js'

const root = document.querySelector('#root')
const storage = createTicketStorage()
const params = new URLSearchParams(location.search)
const linkRef = { departmentId: params.get('departmentId'), ticketId: params.get('ticketId') }
const ref = validReference(linkRef) ? linkRef : storage.read()
const labels = {
  queued: 'Ожидайте вызова', called: 'Вас вызывают', serving: 'Идёт обслуживание',
  completed: 'Обслуживание завершено', canceled: 'Запись отменена',
}

let saved = true

function persist(ticket) {
  saved = syncStoredTicket(storage, ticket)
}

function tracked(method) {
  return async (nextRef, signal) => {
    try {
      const ticket = await ticketApi[method](nextRef, signal)
      persist(ticket)
      return ticket
    } catch (error) {
      if (error.status === 404) storage.clear()
      throw error
    }
  }
}

const api = { get: tracked('get'), cancel: tracked('cancel') }

function render({ ticket, error, canceling, stale = true }) {
  const live = ticket && !TERMINAL_STATUSES.has(ticket.status)

  renderHtml(root, `
    <main class="screen ticket-screen">
      <img class="logo" src="/assets/logo.svg" alt="Почта России">
      <section class="ticket-card" aria-label="Ваш талон">
        <div class="ticket-main">
          <h1>Ваш талон</h1>
          <strong class="ticket-number">${esc(ticket?.ticket_label || '…')}</strong>
          <p role="status">${esc(ticket ? labels[ticket.status] : 'Загружаем статус…')}</p>
          ${ticket?.status === 'queued' ? `<p>${ticket.estimated_wait_time == null
            ? 'Время ожидания уточняется'
            : `Примерное ожидание: ${esc(ticket.estimated_wait_time)} мин`}</p>` : ''}
          ${ticket?.window_id ? `<p>Окно назначено. Уточните номер на табло или у сотрудника.</p>
            <small>ID окна: ${esc(ticket.window_id)}</small>` : ''}
          ${error ? `<p role="alert">${esc(error)}</p>` : ''}
          ${live && !saved ? '<p role="alert">Браузер не разрешил сохранение. Сохраните ссылку на эту страницу.</p>' : ''}
        </div>
      </section>
      <footer class="screen-footer">
        ${ticket?.status === 'queued' ? `<button class="cancel-button" data-cancel ${canceling || stale ? 'disabled' : ''}>
          ${canceling ? 'Отменяем…' : 'Отменить запись'}
        </button>` : ''}
        <p><a href="/">На главную</a></p>
      </footer>
    </main>
  `)
}

if (!ref) {
  root.innerHTML = '<main class="screen"><h1>Нет сохранённого талона</h1><a href="/">На главную</a></main>'
} else {
  const session = createTicketSession({ api, ref, onChange: render })
  render({ ticket: null })
  root.addEventListener('click', event => {
    const button = event.target.closest('[data-cancel]')
    if (button && !button.disabled && confirm('Отменить запись?')) session.cancel()
  })
  window.addEventListener('online', () => session.refresh())
  window.addEventListener('pagehide', () => session.stop())
  window.addEventListener('pageshow', () => session.start())
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) session.refresh()
  })
  session.start()
}
