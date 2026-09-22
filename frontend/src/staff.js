import { renderHtml } from './shared/render.js';
import { openReportCalendar } from './report-calendar.js';
import { dateOffset, dateValueFromOffset, formatRuDate, todayDateValue, toDailyReportView } from './staff-analytics.js';
import './shared/assets.js';
import {
  escapeHtml as esc,
  button as btn,
} from "./shared/html.js";
import { createStaffViews } from "./staff-views.js";
import { currentOperator } from './operator-accounts.js';
import { ticketApi } from './tickets/api.js';
import { historyTimelineHtml } from './staff-ticket-history.js';
import { isUuid } from './shared/ids.js';
import { departmentIdFromSession } from './shared/staff-session.js';
import { departmentApi, issuesApi, servicesApi, staffApi, windowsApi } from './staff/api.js';
import { queueRulesToMinutes, queueRulesToSeconds, readQueueRulesForm } from './staff/queue-rules.js';

const signedOperator = currentOperator();
let operatorDepartment = null;
let services = [];
let windows = [];
let staffList = [];
let issues = [];
let analyticsOffset = 0;

const root = document.querySelector("#staff");
const modal = document.querySelector("#modal");
let role =
    signedOperator?.role === "admin"
      ? "admin"
      : "operator",
  page = role === "admin" ? "Обзор" : "Рабочее место",
  opened = false,
  current = null,
  served = 0,
  windowId = null,
  loadError = "";
let queue = [];
let enabled = [];
const options = () => services.map((s) => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join("");
let notificationTimer;
function notify(text) {
  clearTimeout(notificationTimer);
  document.querySelector("#toast").textContent = text;
  notificationTimer = setTimeout(() => {
    document.querySelector("#toast").textContent = "";
  }, 3200);
}
let queueRules = null;
let queueRulesStatus = "idle";
let queueRulesRequest = 0;
let analyticsReport = null;
let analyticsStatus = "idle";
let analyticsRequest = 0;
let analyticsAbort = null;
let actionBusy = false;
const { queueList, table, operator, windows: windowsView, overview, analytics, rulesView } =
  createStaffViews(() => ({
    operatorName: signedOperator?.display_name || "Оператор",
    analyticsOffset,
    analyticsDateValue: dateValueFromOffset(analyticsOffset),
    analyticsToday: todayDateValue(),
    analyticsLabel: formatRuDate(dateValueFromOffset(analyticsOffset)),
    analyticsReport,
    analyticsStatus,
    queue,
    current,
    opened,
    enabled,
    served,
    issues,
    rules: queueRules,
    rulesStatus: queueRulesStatus,
    services,
    windows,
    staffList,
    windowLabel: seatedWindow()?.label || "окно",
    loadError,
  }));

function seatedWindow() {
  return windows.find((window) => window.current_operator_id === signedOperator?.id) ?? null;
}

function waitMinutes(ticket) {
  if (Number.isFinite(ticket.estimated_wait_time)) return ticket.estimated_wait_time;
  const created = Date.parse(ticket.created_at);
  if (Number.isNaN(created)) return 0;
  return Math.max(0, Math.round((Date.now() - created) / 60000));
}

function ticketTime(ticket) {
  const created = new Date(ticket.created_at);
  if (Number.isNaN(created.getTime())) return "";
  return created.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

function mapTicket(ticket) {
  if (!ticket) return null;

  return {
    id: ticket.id,
    ticket_label: ticket.ticket_label,
    service_id: ticket.service_id,
    source: ticket.source,
    status: ticket.status,
    window_id: ticket.window_id,
    created_at: ticket.created_at,
    estimated_wait_time: ticket.estimated_wait_time,
    wait: waitMinutes(ticket),
    time: ticketTime(ticket),
    started: ticket.status === "serving",
  };
}

function syncWindowState() {
  const seated = seatedWindow();
  windowId = seated?.id ?? null;
  opened = Boolean(seated);
  enabled = seated?.open_service_ids ?? [];
}

function departmentId() {
  return operatorDepartment?.id || departmentIdFromSession();
}

function failMessage(error, fallback) {
  if (error?.status === 409) return "Нельзя выполнить: состояние окна или талона изменилось.";
  if (error?.status === 403) return "Недостаточно прав.";
  if (error?.status === 404) return "Объект не найден.";
  return fallback;
}

function windowChecks(window, selectedIds) {
  const selected = new Set(selectedIds ?? []);
  const catalog = services.filter((service) => (window?.service_ids ?? []).includes(service.id));

  return catalog
    .map(
      (s) =>
        `<label><input type="checkbox" name="services" value="${esc(s.id)}" ${selected.has(s.id) ? "checked" : ""}>${esc(s.name)}</label>`,
    )
    .join("");
}

function catalogChecks(window) {
  const selected = new Set(window?.service_ids ?? []);

  return services
    .map(
      (s) =>
        `<label><input type="checkbox" name="services" value="${esc(s.id)}" ${selected.has(s.id) ? "checked" : ""}>${esc(s.name)}</label>`,
    )
    .join("");
}

function bindWindowSelect() {
  const select = modal.querySelector("#window");
  const checks = modal.querySelector(".checks");
  if (!select || !checks) return;

  select.addEventListener("change", () => {
    const window = windows.find((item) => item.id === select.value);
    checks.innerHTML = windowChecks(
      window,
      window?.open_service_ids?.length ? window.open_service_ids : window?.service_ids,
    );
  });
}

function problemsPage() {
  if (loadError) return `<section class="card"><h2>Проблемы и отклонения</h2><p>${esc(loadError)}</p></section>`;
  const rows = issues.length
    ? issues
        .map((issue) => {
          const resolve =
            role === "admin" && issue.status === "open"
              ? `<button class="ghost compact" data-action="resolve-issue" data-issue-id="${esc(issue.id)}">Закрыть</button>`
              : "";
          const status = issue.status === "resolved" ? "закрыта" : "открыта";
          return `<div class="alert"><div class="row"><span>${esc(issue.message)}</span>${resolve}</div><p class="muted">${status}</p></div>`;
        })
        .join("")
    : '<p class="muted">Открытых проблем нет</p>';
  return `<section class="card"><h2>Проблемы и отклонения</h2>${rows}${btn("Сообщить о проблеме", "problem", "ghost")}</section>`;
}

function render() {
  const nav =
    role === "operator"
      ? ["Рабочее место", "История смены"]
      : [
          "Обзор",
          "Очередь",
          "Окна и услуги",
          "Правила очереди",
          "Аналитика",
          "Проблемы и журнал",
          "Аккаунты",
          "QR отделения",
        ];
  const heading =
    role === "operator"
      ? `${esc(seatedWindow()?.label || "Окно не открыто")} · ${esc(signedOperator?.display_name || "Оператор")}`
      : "Состояние отделения и управление обслуживанием";
  const body =
    page === "Аккаунты" || page === "QR отделения"
      ? `<iframe title="${page}" src="/src/${page === "Аккаунты" ? "accounts" : "qr"}.html" style="width:100%;min-height:900px;border:0;border-radius:20px"></iframe>`
      : page === "Рабочее место"
        ? operator()
        : page === "Обзор"
          ? overview()
          : page === "Очередь"
            ? `<section class="card"><h2>Все талоны</h2>${table()}</section>`
            : page === "Окна и услуги"
              ? windowsView()
              : page === "Правила очереди"
                ? rulesView()
                : page === "Аналитика"
                  ? analytics()
                  : page === "История смены"
                    ? `<section class="card"><h2>История смены</h2><p class="muted">Журнала смены в API нет. История одного талона открывается кнопкой «История».</p></section>`
                    : problemsPage();
  renderHtml(root, `<header><div><img src="/assets/logo.svg" alt="Почта России"><small>Электронная очередь · Для сотрудников</small></div><div><strong>Отделение № ${esc(operatorDepartment?.code ?? "—")}</strong><small>${esc(operatorDepartment?.address ?? "")}</small></div></header><div class="layout"><aside>${nav.map((n) => btn(n, "nav-" + n, page === n ? "active" : "")).join("")}<div class="aside-note"><a class="link" href="/">Клиентский интерфейс ↗</a></div></aside><main><div class="heading"><div><div class="demo">Рабочее пространство / ${role === "operator" ? "Оператор" : "Руководитель"}</div><h1>${page}</h1><span class="muted">${heading}</span></div><div class="row">${role === "operator" ? btn(opened ? "Закрыть окно" : "Открыть окно", opened ? "close" : "open", "ghost") : ""}</div></div>${body}</main></div>`);
}
function dialog(title, body, footer) {
  modal.innerHTML = `<div class="backdrop"><section class="dialog" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="row"><h2>${esc(title)}</h2>${btn("✕", "dismiss", "ghost compact")}</div>${body}<div class="footer">${footer || btn("Сохранить", "confirm", "primary")}</div></section></div>`;
  modal.querySelector("input,select,textarea,button")?.focus();
}
let historyRequest = 0;
function findTicket(ticketId) {
  if (ticketId) {
    return [current, ...queue].find((ticket) => ticket?.id === ticketId) || null;
  }

  return current;
}
async function openTicketHistory(ticket) {
  const title = `История ${ticket.ticket_label}`;
  const requestId = ++historyRequest;
  const panel = '<div id="ticket-history-panel"><p class="muted">Загружаем…</p></div>';

  dialog(title, panel, btn("Закрыть", "dismiss", "primary"));

  const id = departmentId();
  let events = null;
  let errorText = "";

  if (isUuid(id) && isUuid(ticket.id)) {
    try {
      const rows = await ticketApi.statusHistory({
        departmentId: id,
        ticketId: ticket.id,
      });

      if (Array.isArray(rows)) {
        events = [...rows].reverse();
      }
    } catch {
      errorText = "Не удалось загрузить историю талона.";
    }
  } else {
    errorText = "Не удалось загрузить историю талона.";
  }

  if (requestId !== historyRequest) return;

  const host = modal.querySelector("#ticket-history-panel");
  if (!host) return;

  host.innerHTML = errorText
    ? `<p class="muted">${esc(errorText)}</p>`
    : historyTimelineHtml(events || [], {});
}

async function applyQueue(department, id) {
  const dto = await windowsApi.queue(department, id);
  current = mapTicket(dto.current);
  queue = (dto.upcoming ?? []).map(mapTicket);
}

async function reloadSurface() {
  const id = departmentIdFromSession();
  if (!id) {
    loadError = "Отделение не указано в сессии";
    render();
    return;
  }

  try {
    if (role === "admin") {
      const [department, serviceRows, windowRows, ticketRows, issueRows, staffRows] = await Promise.all([
        departmentApi.get(id),
        servicesApi.list(id),
        windowsApi.list(id),
        ticketApi.incomplete(id),
        issuesApi.list(id),
        staffApi.list(),
      ]);
      operatorDepartment = department;
      services = serviceRows;
      windows = windowRows;
      staffList = staffRows;
      issues = issueRows;
      queue = (ticketRows ?? []).map(mapTicket);
      current = null;
      syncWindowState();
      loadError = "";
    } else {
      const [department, serviceRows, windowRows] = await Promise.all([
        departmentApi.get(id),
        servicesApi.active(id),
        windowsApi.list(id),
      ]);
      operatorDepartment = department;
      services = serviceRows;
      windows = windowRows;
      syncWindowState();
      if (windowId) {
        await applyQueue(id, windowId);
      } else {
        current = null;
        queue = [];
      }
      loadError = "";
    }
  } catch (error) {
    loadError = failMessage(error, "Не удалось загрузить данные отделения.");
  }

  render();
}

async function runWindowAction(fn, fallback) {
  const id = departmentId();
  if (!id || !windowId) {
    notify("Сначала откройте окно");
    return false;
  }
  if (actionBusy) return false;
  actionBusy = true;
  try {
    await fn(id, windowId);
    await reloadSurface();
    return true;
  } catch (error) {
    notify(failMessage(error, fallback));
    await reloadSurface();
    return false;
  } finally {
    actionBusy = false;
  }
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    historyRequest++;
    modal.innerHTML = "";
  }
  if (e.key === "Tab" && modal.firstChild) {
    const els = [...modal.querySelectorAll("button,input,select,textarea")];
    if (e.shiftKey && document.activeElement === els[0]) {
      e.preventDefault();
      els.at(-1).focus();
    } else if (!e.shiftKey && document.activeElement === els.at(-1)) {
      e.preventDefault();
      els[0].focus();
    }
  }
});
let pending = "";
let pendingWindowId = "";
document.addEventListener("click", (e) => {
  const trigger = e.target.closest("[data-action]");
  const a = trigger?.dataset.action;
  if (!a) return;
  void handleAction(a, trigger);
});

async function handleAction(a, trigger) {
  if (a === 'open-report-calendar') {
    const input = document.querySelector('#analytics-date');
    if (!input) return;
    openReportCalendar(input.value, value => {
      const offset = dateOffset(value);
      if (offset === null) return;
      analyticsOffset = offset;
      void loadAnalytics();
    });
    return;
  }
  if (a === "analytics-previous" || a === "analytics-next" || a === "analytics-today" || a === "analytics-reload") {
    if (a !== "analytics-reload") {
      analyticsOffset = a === "analytics-today" ? 0 : Math.min(0, analyticsOffset + (a === "analytics-previous" ? -1 : 1));
    }
    void loadAnalytics();
    return;
  }
  if (a === "dismiss") {
    historyRequest++;
    modal.innerHTML = "";
    return;
  }

  if (a.startsWith("nav-")) {
    if (role !== "admin" && !["nav-Рабочее место", "nav-История смены"].includes(a)) return;
    page = a.slice(4);
    render();
    if (page === "Правила очереди") void loadQueueRules();
    if (page === "Аналитика") void loadAnalytics();
    return;
  }
  if (a === "reload-rules") {
    void loadQueueRules();
    return;
  }

  if (a === "problems") {
    page = "Проблемы и журнал";
    render();
    return;
  }

  if (a === "ticket-history") {
    const ticket = findTicket(trigger.dataset.ticketId);
    if (!ticket) {
      notify("Талон не найден");
      return;
    }
    openTicketHistory(ticket);
    return;
  }

  if (a === "call") {
    const ok = await runWindowAction(windowsApi.callNext, "Не удалось вызвать следующего клиента");
    if (ok && current) notify(`Талон ${current.ticket_label} вызван к ${seatedWindow()?.label || "окну"}`);
    return;
  }
  if (a === "start") {
    const ok = await runWindowAction(windowsApi.start, "Не удалось начать обслуживание");
    if (ok && current) notify(`Начато обслуживание ${current.ticket_label}`);
    return;
  }
  if (a === "absent") {
    const ok = await runWindowAction(windowsApi.noshow, "Не удалось отметить неявку");
    if (ok) notify("Талон закрыт: клиент не подошёл");
    return;
  }
  if (a === "finish") {
    const label = current?.ticket_label;
    const ok = await runWindowAction(async (id, idWindow) => {
      await windowsApi.complete(id, idWindow);
      served += 1;
    }, "Не удалось завершить обслуживание");
    if (ok && label) notify(`Обслуживание ${label} завершено`);
    return;
  }
  if (a === "close") {
    if (current) {
      dialog(
        "Закрыть окно?",
        "<p>Окно нельзя закрыть, пока есть вызванный или обслуживаемый талон. Верните клиента в очередь и закройте окно.</p>",
        btn("Вернуть клиента и закрыть", "close-return", "danger") + btn("Отмена", "dismiss", "ghost"),
      );
      return;
    }
    const ok = await runWindowAction(windowsApi.close, "Не удалось закрыть окно");
    if (ok) notify("Окно закрыто");
    return;
  }
  if (a === "open" || a === "services") {
    pending = a;
    const seated = seatedWindow();
    const candidates = windows.filter(
      (window) => !window.current_operator_id || window.current_operator_id === signedOperator?.id,
    );
    const selected = seated ?? candidates[0];
    if (!selected) {
      notify("Нет свободного окна");
      return;
    }
    const windowField =
      a === "open" && !seated
        ? `<label for="window">Окно</label><select id="window">${candidates.map((window) => `<option value="${esc(window.id)}" ${window.id === selected.id ? "selected" : ""}>${esc(window.label)}</option>`).join("")}</select>`
        : "";
    dialog(
      a === "open" ? "Открытие окна" : `Услуги ${selected.label}`,
      `${windowField}<p class="muted">Выберите услуги, которые может обслуживать окно.</p><div class="checks">${windowChecks(selected, selected.open_service_ids?.length ? selected.open_service_ids : selected.service_ids)}</div>`,
    );
    bindWindowSelect();
    return;
  }
  if (a === "configure-window") {
    pending = a;
    pendingWindowId = trigger.dataset.windowId;
    const window = windows.find((item) => item.id === pendingWindowId);
    if (!window) {
      notify("Окно не найдено");
      return;
    }
    dialog(
      window.label,
      `<p class="muted">Услуги каталога окна. Пустой список допустим, пока окно закрыто.</p><div class="checks">${catalogChecks(window)}</div>`,
    );
    return;
  }
  if (["add", "redirect", "return", "close-return", "problem"].includes(a)) {
    pending = a;
    const titles = {
      add: "Клиент из живой очереди",
      redirect: "Перенаправить клиента",
      return: "Вернуть в очередь",
      "close-return": "Возврат и закрытие",
      problem: "Сообщить о проблеме",
    };
    dialog(
      titles[a],
      `${["add", "redirect"].includes(a) ? `<label for="service">Услуга</label><select id="service">${options()}</select>` : ""}${a === "redirect" ? '<p class="muted">Талон вернётся в общую очередь на выбранную услугу.</p>' : ""}${a === "problem" ? '<label for="reason">Описание</label><textarea id="reason" rows="3" placeholder="Кратко опишите ситуацию"></textarea>' : ""}${a === "add" ? '<p class="muted">Источник будет указан автоматически. Сообщите номер талона клиенту.</p>' : ""}`,
    );
    return;
  }
  if (a === "confirm") {
    await confirmDialog();
    return;
  }
  if (a === "save-rules") {
    void saveQueueRules();
    return;
  }
  if (a === "resolve-issue") {
    const id = departmentId();
    const issueId = trigger.dataset.issueId;
    if (!id || !issueId || actionBusy) return;
    actionBusy = true;
    try {
      await issuesApi.resolve(id, issueId);
      notify("Проблема закрыта");
      await reloadSurface();
    } catch (error) {
      notify(failMessage(error, "Не удалось закрыть проблему"));
    } finally {
      actionBusy = false;
    }
    return;
  }
  render();
}

async function confirmDialog() {
  const id = departmentId();
  if (!id) {
    notify("Отделение не указано в сессии");
    return;
  }
  const reason = modal.querySelector("#reason")?.value.trim();
  if (modal.querySelector("#reason") && !reason) {
    notify("Укажите причину");
    return;
  }
  if (actionBusy) return;
  actionBusy = true;
  try {
    if (pending === "open" || pending === "services") {
      const values = [...modal.querySelectorAll("input:checked")].map((x) => x.value);
      if (!values.length) {
        notify("Выберите хотя бы одну услугу");
        return;
      }
      const selectedId = modal.querySelector("#window")?.value || windowId || seatedWindow()?.id;
      if (!selectedId) {
        notify("Выберите окно");
        return;
      }
      await windowsApi.open(id, selectedId, { open_service_ids: values });
      notify(pending === "open" ? "Окно открыто" : "Услуги окна сохранены");
      modal.innerHTML = "";
      await reloadSurface();
      return;
    }
    if (pending === "configure-window") {
      const values = [...modal.querySelectorAll("input:checked")].map((x) => x.value);
      await windowsApi.update(id, pendingWindowId, { service_ids: values });
      notify("Настройки окна сохранены");
      modal.innerHTML = "";
      await reloadSurface();
      return;
    }
    if (pending === "add") {
      const service = services.find((item) => item.id === modal.querySelector("#service").value);
      if (!service) {
        notify("Выберите услугу");
        return;
      }
      const ticket = await ticketApi.create(id, { service_id: service.id, source: "walk-in", slot_id: null });
      notify(`Добавлен талон ${ticket.ticket_label}`);
      modal.innerHTML = "";
      await reloadSurface();
      return;
    }
    if (pending === "problem") {
      await issuesApi.create(id, { message: reason });
      notify("Проблема зарегистрирована");
      modal.innerHTML = "";
      await reloadSurface();
      return;
    }
    if (pending === "redirect") {
      const service = services.find((item) => item.id === modal.querySelector("#service").value);
      if (!service) {
        notify("Выберите услугу");
        return;
      }
      if (!windowId) {
        notify("Сначала откройте окно");
        return;
      }
      await windowsApi.redirect(id, windowId, { service_id: service.id });
      notify(`${current?.ticket_label || "Талон"}: перенаправлен`);
      modal.innerHTML = "";
      await reloadSurface();
      return;
    }
    if (pending === "return") {
      if (!windowId) {
        notify("Сначала откройте окно");
        return;
      }
      await windowsApi.requeue(id, windowId);
      notify(`${current?.ticket_label || "Талон"}: возвращён в очередь`);
      modal.innerHTML = "";
      await reloadSurface();
      return;
    }
    if (pending === "close-return") {
      if (!windowId) {
        notify("Сначала откройте окно");
        return;
      }
      await windowsApi.requeue(id, windowId);
      await windowsApi.close(id, windowId);
      notify("Клиент возвращён в очередь, окно закрыто");
      modal.innerHTML = "";
      await reloadSurface();
      return;
    }
    modal.innerHTML = "";
  } catch (error) {
    if (pending === "close-return" && error?.status === 409) {
      notify("Клиент возвращён в очередь. Окно нельзя закрыть, пока есть активный талон.");
      modal.innerHTML = "";
      await reloadSurface();
      return;
    }
    notify(failMessage(error, "Не удалось выполнить действие"));
  } finally {
    actionBusy = false;
  }
}

async function loadQueueRules() {
  if (queueRulesStatus === "saving") return;
  const id = departmentIdFromSession();
  const requestId = ++queueRulesRequest;
  if (!id) {
    queueRules = null;
    queueRulesStatus = "error";
    render();
    return;
  }
  queueRulesStatus = "loading";
  render();
  try {
    const dto = await departmentApi.getQueueRules(id);
    if (requestId !== queueRulesRequest) return;
    queueRules = queueRulesToMinutes(dto);
    queueRulesStatus = "ready";
  } catch {
    if (requestId !== queueRulesRequest) return;
    queueRules = null;
    queueRulesStatus = "error";
  }
  render();
}

async function saveQueueRules() {
  if (queueRulesStatus === "saving" || queueRulesStatus === "loading") return;
  const minutes = readQueueRulesForm();
  if (!minutes) {
    notify("Укажите целые значения от 0 до 1440 минут");
    return;
  }
  const id = departmentIdFromSession();
  if (!id) {
    notify("Отделение не указано в сессии");
    return;
  }
  queueRules = minutes;
  queueRulesStatus = "saving";
  render();
  try {
    const dto = await departmentApi.patchQueueRules(id, queueRulesToSeconds(minutes));
    queueRules = queueRulesToMinutes(dto);
    queueRulesStatus = "ready";
    notify("Правила очереди сохранены");
  } catch (error) {
    queueRulesStatus = "ready";
    notify(error?.status === 403 ? "Недостаточно прав для изменения правил" : "Не удалось сохранить правила");
  }
  render();
}

async function loadAnalytics() {
  const id = departmentIdFromSession();
  const requestId = ++analyticsRequest;
  analyticsAbort?.abort();
  analyticsAbort = new AbortController();
  analyticsStatus = "loading";
  analyticsReport = null;
  render();
  if (!id) {
    analyticsStatus = "error";
    render();
    return;
  }
  try {
    const dto = await departmentApi.getAnalytics(id, dateValueFromOffset(analyticsOffset), analyticsAbort.signal);
    if (requestId !== analyticsRequest) return;
    analyticsReport = toDailyReportView(dto);
    analyticsStatus = "ready";
  } catch {
    if (requestId !== analyticsRequest) return;
    analyticsReport = null;
    analyticsStatus = "error";
  }
  render();
}

render();
void reloadSurface();

root.addEventListener('change', event => {
  if (event.target.id !== 'analytics-date') return;
  const offset = dateOffset(event.target.value);
  if (offset === null) {
    notify('Выберите корректную дату не позднее сегодняшнего дня.');
    render();
    return;
  }
  analyticsOffset = offset;
  void loadAnalytics();
});
