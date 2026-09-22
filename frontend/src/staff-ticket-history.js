import { escapeHtml as esc } from "./shared/html.js";

const REASON_LABELS = {
  issued: "Выдан",
  called: "Вызван",
  started: "Обслуживание начато",
  completed: "Завершён",
  canceled: "Отменён",
  noshow: "Клиент не подошёл",
  requeued: "Возвращён в очередь",
  redirected: "Перенаправлен",
};

const STATUS_LABELS = {
  queued: "Ожидает",
  called: "Вызван",
  serving: "Обслуживается",
  completed: "Завершён",
  canceled: "Отменён",
};

function statusLabel(status) {
  return STATUS_LABELS[status] || status || "—";
}

function reasonLabel(reason) {
  return REASON_LABELS[reason] || reason || "—";
}

function formatTime(value) {
  const date = value instanceof Date ? value : new Date(value);

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function windowText(event) {
  if (event.window_label) return event.window_label;
  if (event.window_id) return "Окно назначено";

  return "";
}

export function demoHistoryEvents(ticket, { isCurrent = false, windowLabel = null } = {}) {
  const now = Date.now();
  const waitMs = Math.max(0, Number(ticket.wait) || 0) * 60000;
  const events = [
    {
      changed_at: new Date(now - waitMs).toISOString(),
      old_status: null,
      new_status: "queued",
      reason: "issued",
      window_label: null,
    },
  ];

  if (isCurrent) {
    events.push({
      changed_at: new Date(now - (ticket.started ? 120000 : 60000)).toISOString(),
      old_status: "queued",
      new_status: "called",
      reason: "called",
      window_label: windowLabel,
    });

    if (ticket.started) {
      events.push({
        changed_at: new Date(now - 30000).toISOString(),
        old_status: "called",
        new_status: "serving",
        reason: "started",
        window_label: windowLabel,
      });
    }
  }

  return events;
}

export function historyTimelineHtml(events, { demo = false } = {}) {
  const notice = demo
    ? '<p class="muted">Демонстрационные данные. Журнал статусов с сервера недоступен.</p>'
    : "";

  if (!events.length) {
    return `${notice}<p class="muted">Записей истории нет</p>`;
  }

  const items = events
    .map((event) => {
      const window = windowText(event);
      const from = event.old_status ? statusLabel(event.old_status) : "—";

      return `<li><time>${esc(formatTime(event.changed_at))}</time><strong>${esc(reasonLabel(event.reason))}</strong><span class="muted">${esc(from)} → ${esc(statusLabel(event.new_status))}${window ? ` · ${esc(window)}` : ""}</span></li>`;
    })
    .join("");

  return `${notice}<ol class="ticket-history">${items}</ol>`;
}
