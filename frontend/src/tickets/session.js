import { referenceFromTicket } from './storage.js';

export const TERMINAL_STATUSES = new Set(['completed', 'canceled']);
export const TICKET_STATUSES = new Set(['queued', 'called', 'serving', ...TERMINAL_STATUSES]);

/** Persist the visitor session only while the ticket is still live. */
export function syncStoredTicket(storage, ticket) {
  if (!ticket || TERMINAL_STATUSES.has(ticket.status)) {
    storage.clear();
    return true;
  }

  return storage.save(referenceFromTicket(ticket));
}

function errorMessage(error, cancel, retry) {
  if (error.status === 404) return 'Талон не найден. Обратитесь к сотруднику.';
  if (error.status === 409) return 'Статус изменился: отмена недоступна. Обновляем талон.';
  if ([401, 403].includes(error.status)) return 'Нет доступа к талону.';
  if (!retry) return 'Запрос отклонён сервером. Обратитесь к сотруднику.';
  if (cancel) return 'Отмена не подтверждена. Проверяем состояние; повторно не записывайтесь.';
  return 'Нет актуальных данных. Последний статус может быть устаревшим. Повторяем запрос…';
}

/** One request at a time. Old GET responses cannot overwrite a cancellation. */
export function createTicketSession({ api, ref, onChange, interval = 5000 }) {
  let ticket = null;
  let timer;
  let controller;
  let revision = 0;
  let stopped = true;
  let canceling = false;
  let loading = false;
  let stale = true;

  function publish(error = null) {
    onChange({ ticket, error, canceling, stale });
  }

  function accept(value) {
    const actual = referenceFromTicket(value);
    if (
      actual.ticketId !== ref.ticketId ||
      actual.departmentId !== ref.departmentId ||
      !TICKET_STATUSES.has(value.status) ||
      typeof value.ticket_label !== 'string' ||
      (value.estimated_wait_time != null &&
        (!Number.isFinite(value.estimated_wait_time) || value.estimated_wait_time < 0))
    ) {
      throw new Error('Invalid ticket response');
    }
    ticket = value;
  }

  async function run(cancel = false) {
    clearTimeout(timer);
    controller?.abort();
    controller = new AbortController();
    const current = ++revision;
    loading = true;
    let retry = true;
    try {
      const value = await (cancel ? api.cancel : api.get)(ref, controller.signal);
      if (current !== revision || stopped) return;
      accept(value);
      stale = false;
      canceling = false;
      publish();
    } catch (error) {
      if (current !== revision || stopped) return;
      canceling = false;
      stale = true;
      retry = ![400, 401, 403, 404, 422].includes(error.status);
      publish(errorMessage(error, cancel, retry));
    } finally {
      if (current === revision) loading = false;
      if (current === revision && !stopped && retry && !TERMINAL_STATUSES.has(ticket?.status)) {
        timer = setTimeout(() => run(), cancel ? 0 : interval);
      }
    }
  }

  return {
    start() {
      if (!stopped) return;
      stopped = false;
      run();
    },
    refresh() {
      if (!stopped && !loading && !canceling && !TERMINAL_STATUSES.has(ticket?.status)) run();
    },
    cancel() {
      if (stopped || canceling || stale || ticket?.status !== 'queued') return;
      canceling = true;
      publish();
      run(true);
    },
    stop() {
      stopped = true;
      canceling = false;
      revision++;
      clearTimeout(timer);
      controller?.abort();
    },
  };
}
