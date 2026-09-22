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

export function historyTimelineHtml(events) {
  if (!events.length) {
    return `<p class="muted">Записей истории нет</p>`;
  }

  const items = events
    .map((event) => {
      const window = windowText(event);
      const from = event.old_status ? statusLabel(event.old_status) : "—";

      return `<li><time>${esc(formatTime(event.changed_at))}</time><strong>${esc(reasonLabel(event.reason))}</strong><span class="muted">${esc(from)} → ${esc(statusLabel(event.new_status))}${window ? ` · ${esc(window)}` : ""}</span></li>`;
    })
    .join("");

  return `<ol class="ticket-history">${items}</ol>`;
}
