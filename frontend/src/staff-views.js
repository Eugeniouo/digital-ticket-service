import {
  escapeHtml as esc,
  button as btn,
  badge as pill,
} from "./shared/html.js";
import { ticketSourceLabel } from "./shared/ticket-source.js";
import { QUEUE_RULE_FIELDS, RULE_MINUTE_MAX, RULE_MINUTE_MIN } from "./staff/queue-rules.js";

const STATUS_LABELS = {
  queued: "Ожидает",
  called: "Вызван",
  serving: "Обслуживается",
  completed: "Завершён",
  canceled: "Отменён",
};

/** Screen templates read current state without changing it. */
export function createStaffViews(getState) {
  const serviceName = (serviceId) =>
    (getState().services ?? []).find((service) => service.id === serviceId)?.name ?? "";
  const windowName = (windowId) =>
    (getState().windows ?? []).find((window) => window.id === windowId)?.label ?? "—";
  const staffName = (staffId) =>
    (getState().staffList ?? []).find((staff) => staff.id === staffId)?.display_name ?? "Оператор на окне";
  function queueList() {
    const { queue } = getState();
    return (
      queue
        .map(
          (q) =>
            `<div class="queue-item"><div class="row"><strong>${esc(q.ticket_label)}</strong>${pill(ticketSourceLabel(q.source), q.source === "web" ? "blue" : "gray")}</div><p>${esc(serviceName(q.service_id))}</p><div class="row muted"><span>${esc(q.time)}</span><span>${q.wait} мин</span></div></div>`,
        )
        .join("") || '<p class="muted">Ожидающих клиентов нет</p>'
    );
  }
  function table() {
    const { queue, current } = getState();
    const rows = [...(current ? [current] : []), ...queue.filter((ticket) => ticket !== current && ticket?.id !== current?.id)];
    return `<div class="table-wrap"><table><thead><tr><th>Талон</th><th>Услуга</th><th>Источник</th><th>Статус</th><th>Ожидание</th><th>Окно</th></tr></thead><tbody>${rows.map((q) => `<tr data-action="ticket-history" data-ticket-id="${esc(q.id)}"><td><strong>${esc(q.ticket_label)}</strong></td><td>${esc(serviceName(q.service_id))}</td><td>${pill(ticketSourceLabel(q.source), "blue")}</td><td>${esc(STATUS_LABELS[q.status] || (q.started ? "Обслуживается" : "Ожидает"))}</td><td>${q.wait} мин</td><td>${esc(q.window_id ? windowName(q.window_id) : "—")}</td></tr>`).join("")}</tbody></table></div>`;
  }
  function operator() {
    const {
      queue,
      current,
      opened,
      enabled,
      served,
      windowLabel = "окно",
      operatorName = "Оператор",
      loadError = "",
    } = getState();
    const error = loadError ? `<div class="alert">${esc(loadError)}</div>` : "";
    const currentCard = current
      ? `<div class="number">${esc(current.ticket_label)}</div><h2>${esc(serviceName(current.service_id))}</h2><div class="muted">${esc(ticketSourceLabel(current.source))} · Ожидание ${current.wait} мин</div><p>${current.started ? "Клиент обслуживается в вашем окне" : `Пригласите клиента к ${esc(windowLabel)}`}</p><div class="actions">${btn(current.started ? "Завершить обслуживание" : "Начать обслуживание", current.started ? "finish" : "start", "primary")}<div class="row">${btn("Вернуть в очередь", "return", "")}${btn("Перенаправить", "redirect", "")}</div>${!current.started ? btn("Клиент не подошёл", "absent", "ghost") : ""}${btn("История", "ticket-history", "ghost")}</div>`
      : `<div class="empty-icon">↗</div><h2>${opened ? "Готовы к следующему клиенту" : "Окно закрыто"}</h2><p class="muted">${opened ? "Вызовите клиента из очереди.<br>Порядок вызова задаёт сервер." : "Откройте окно и выберите услуги,<br>чтобы начать обслуживание."}</p><div class="actions">${btn(opened ? "Вызвать следующего" : "Открыть окно", opened ? "call" : "open", "primary", opened && !queue.length)}</div>`;
    return `<div class="grid operator">${error}<section class="card"><div class="row"><h2>Очередь</h2>${pill(queue.length, "gray")}</div><p class="muted">Порядок вызова задаёт сервер.</p>${queueList()}<div class="section-gap">${btn("+ Добавить клиента", "add", "ghost")}</div></section><section class="card current"><div>${pill(current ? (current.started ? "Обслуживание" : "Клиент вызван") : windowLabel, "blue")}</div>${currentCard}</section><section class="card"><h2>Моё окно</h2><p class="muted">${esc(operatorName)} · Оператор</p><div class="status-line">${pill(opened ? "● Открыто" : "Закрыто", opened ? "" : "gray")}</div><h3>Доступные услуги</h3>${enabled.map((s) => `<div class="service">${esc(serviceName(s))}</div>`).join("") || '<p class="muted">Услуги появятся после открытия окна</p>'}${btn("Изменить услуги", "services", "ghost compact")}<div class="metric">${served}</div><span class="muted">обслужено за смену</span><div class="section-gap">${btn("Сообщить о проблеме", "problem", "ghost")}</div></section></div>`;
  }
  function windows() {
    const { windows: rows = [], queue = [], current, loadError = "" } = getState();
    if (loadError) return `<section class="card"><p>${esc(loadError)}</p></section>`;
    if (!rows.length) return '<section class="card"><p class="muted">Окон в отделении нет</p></section>';
    const tickets = [...(current ? [current] : []), ...queue];
    return `<div class="grid windows">${rows.map((window) => {
      const ticket = tickets.find((item) => item.window_id === window.id && (item.status === "called" || item.status === "serving" || item === current));
      const open = window.status === "open";
      const status = !open ? "Закрыто" : ticket ? (ticket.started || ticket.status === "serving" ? "Обслуживание" : "Вызван") : "Открыто";
      const operator = window.current_operator_id ? staffName(window.current_operator_id) : "Оператор не назначен";
      const names = (window.open_service_ids?.length ? window.open_service_ids : window.service_ids ?? [])
        .map(serviceName)
        .filter(Boolean)
        .join(", ");
      return `<div class="card window ${open ? "" : "closed"}"><div class="row"><h2>${esc(window.label)}</h2>${pill(status, open ? "blue" : "gray")}</div><p>${esc(operator)}</p><div class="service">${esc(names)}</div><p class="muted">${ticket ? `Талон ${esc(ticket.ticket_label)}` : open ? "Нет активного клиента" : "Окно закрыто"}</p><button class="ghost compact" data-action="configure-window" data-window-id="${esc(window.id)}">Настроить окно</button></div>`;
    }).join("")}</div>`;
  }
  function overview() {
    const { queue, windows: rows = [], issues = [] } = getState();
    const waits = queue.map((q) => Number(q.wait) || 0);
    const average = waits.length ? Math.round(waits.reduce((sum, value) => sum + value, 0) / waits.length) : 0;
    const maximum = waits.length ? Math.max(0, ...waits) : 0;
    const openCount = rows.filter((window) => window.status === "open").length;
    const openIssues = issues.filter((issue) => issue.status === "open");
    return `<div class="grid stats">${[
      [queue.length, "Ожидают сейчас"],
      [`${average} мин`, "Среднее ожидание"],
      [`${maximum} мин`, "Максимальное сейчас"],
      [`${openCount} из ${rows.length}`, "Открытые окна"],
    ]
      .map(
        ([a, b]) =>
          `<div class="card"><div class="muted">${b}</div><div class="metric">${a}</div></div>`,
      )
      .join(
        "",
      )}</div><div class="row"><h2>Работа окон</h2><span class="muted">${openCount} из ${rows.length}</span></div>${windows()}<div class="grid two section-gap"><section class="card"><h2>Очередь отделения</h2>${table()}</section><section class="card"><h2>Требует внимания</h2>${openIssues.map((issue) => `<div class="alert">${esc(issue.message)}</div>`).join("") || '<p class="muted">Открытых проблем нет</p>'}${btn("Все проблемы →", "problems", "ghost")}</section></div>`;
  }
  function minutesLabel(value) {
    return value == null ? "—" : `${value} мин`;
  }
  function analytics() {
    const {
      analyticsOffset = 0,
      analyticsDateValue = "",
      analyticsToday = analyticsDateValue,
      analyticsLabel = "",
      analyticsReport: report,
      analyticsStatus = "idle",
    } = getState();
    const label = report?.label ?? analyticsLabel;
    const dateValue = report?.dateValue ?? analyticsDateValue;
    const header = `<section class="card row section-gap" style="margin:0 0 24px"><button class="ghost" data-action="analytics-previous" aria-label="Предыдущий день">←</button><div style="text-align:center"><div class="report-date"><span>${esc(label)}</span><button class="report-date-toggle" data-action="open-report-calendar" aria-label="Открыть календарь"><span aria-hidden="true"></span></button><input id="analytics-date" class="report-date-input" type="date" aria-label="Дата отчёта" value="${esc(dateValue)}" max="${esc(analyticsToday)}"></div><div class="muted">Статистика за день</div></div><div class="row">${btn("Сегодня", "analytics-today", "ghost compact", analyticsOffset === 0)}<button class="ghost" data-action="analytics-next" aria-label="Следующий день" ${analyticsOffset === 0 ? "disabled" : ""}>→</button></div></section>`;
    if (analyticsStatus === "error") {
      return `${header}<section class="card"><p>Не удалось загрузить аналитику.</p>${btn("Повторить", "analytics-reload", "primary")}</section>`;
    }
    if (analyticsStatus !== "ready" || !report) {
      return `${header}<section class="card"><p class="muted">Загружаем статистику…</p></section>`;
    }
    const peak = Math.max(0, ...report.hourly.map((item) => item.count));
    const stats = [
      [report.total, "Обслужено"],
      [minutesLabel(report.averageWait), "Среднее ожидание"],
      [minutesLabel(report.maximumWait), "Максимальное ожидание"],
      [minutesLabel(report.averageService), "Среднее обслуживание"],
    ]
      .map(([value, caption]) => `<div class="card"><span class="muted">${caption}</span><div class="metric">${value}</div></div>`)
      .join("");
    const hours = report.hourly
      .map((item) => {
        const height = peak === 0 ? 8 : Math.max(8, Math.round((item.count / peak) * 140));
        return `<div class="bar">${item.count}<i style="height:${height}px"></i>${esc(item.label)}</div>`;
      })
      .join("");
    const sources = report.sources
      .map((item) => `<div class="queue-item row"><span>${esc(item.label)}</span><strong>${item.count}</strong></div>`)
      .join("");
    const windowsLoad = report.windows
      .map((item) => {
        const shown = item.percent == null ? "—" : `${item.percent}%`;
        const width = item.percent == null ? 0 : Math.min(100, Math.max(0, item.percent));
        return `<div class="queue-item"><div class="row"><span>${esc(item.label)}</span><strong>${shown}</strong></div><div style="height:8px;background:#eef0ff;border-radius:8px;margin-top:12px"><div style="width:${width}%;background:#1928dc;height:8px;border-radius:8px"></div></div></div>`;
      })
      .join("");
    return `${header}<div class="grid stats">${stats}</div><div class="grid two"><section class="card"><h2>Обслуженные клиенты по часам</h2><p class="muted">${esc(report.label)}</p><div class="bars">${hours}</div></section><section class="card"><h2>Источники обращений</h2>${sources}</section></div><section class="card section-gap"><h2>Загрузка окон</h2><p class="muted">Доля обслуживания от времени открытого окна</p>${windowsLoad || '<p class="muted">Окон в отделении нет</p>'}</section>`;
  }
  function rulesView() {
    const { rules, rulesStatus = "idle" } = getState();
    if (rulesStatus === "error") {
      return `<section class="card"><h2>Правила очереди</h2><p>Не удалось загрузить правила очереди.</p>${btn("Повторить", "reload-rules", "primary")}</section>`;
    }
    if (rulesStatus === "loading" || rulesStatus === "idle" || !rules) {
      return `<section class="card"><h2>Правила очереди</h2><p class="muted">Загружаем настройки…</p></section>`;
    }
    const busy = rulesStatus === "saving";
    const fields = QUEUE_RULE_FIELDS.map(
      (field) => `<div><label for="rule-${field.key}">${esc(field.label)}</label><input id="rule-${field.key}" name="${field.key}" type="number" min="${RULE_MINUTE_MIN}" max="${RULE_MINUTE_MAX}" step="1" value="${esc(rules[field.key] ?? 0)}" ${busy ? "disabled" : ""}></div>`,
    ).join("");
    return `<section class="card"><h2>Правила очереди</h2><p class="muted">Коэффициенты отделения. Изменения действуют на следующий вызов из очереди.</p><div class="form-grid">${fields}</div><div class="alert">Бонус сдвигает источник раньше в порядке вызова. Порог ожидания QR и живой очереди поднимает талон после указанного времени; для записи это срок, после которого слот снимается как неявка. Порог не гарантирует обслуживание за указанное время — ожидание зависит от нагрузки и открытых окон.</div><p class="muted">Внутри одинакового приоритета сохраняется порядок поступления. Вызванный клиент остаётся закреплённым за окном.</p>${btn("Сохранить настройки", "save-rules", "primary", busy)}</section>`;
  }
  return {
    queueList,
    table,
    operator,
    windows,
    overview,
    analytics,
    rulesView,
  };
}
