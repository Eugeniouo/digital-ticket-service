import { getDailyReport } from "./staff-analytics.js";
import {
  escapeHtml as esc,
  button as btn,
  badge as pill,
} from "./shared/html.js";
import { ticketSourceLabel } from "./shared/ticket-source.js";
/** Screen templates read current state without changing it. */
export function createStaffViews(getState) {
  const serviceName = (serviceId) =>
    (getState().services ?? []).find((service) => service.id === serviceId)?.name ?? "";
  function queueList() {
    const {
      queue,
      current,
      opened,
      closing,
      enabled,
      served,
      problems,
      rules,
    } = getState();
    return (
      queue
        .map(
          (q) =>
            `<div class="queue-item"><div class="row"><strong>${esc(q.ticket_label)}</strong>${pill(ticketSourceLabel(q.source), q.source === "web" ? "blue" : "gray")}</div><p>${esc(serviceName(q.service_id))}</p><div class="row muted"><span>${q.time}</span><span>${q.wait} мин</span></div></div>`,
        )
        .join("") || '<p class="muted">Ожидающих клиентов нет</p>'
    );
  }
  function table() {
    const {
      queue,
      current,
      opened,
      closing,
      enabled,
      served,
      problems,
      rules,
    } = getState();
    return `<div class="table-wrap"><table><thead><tr><th>Талон</th><th>Услуга</th><th>Источник</th><th>Статус</th><th>Ожидание</th><th>Окно</th></tr></thead><tbody>${[...(current ? [current] : []), ...queue].map((q) => `<tr data-action="ticket-history" data-ticket-id="${esc(q.id)}"><td><strong>${esc(q.ticket_label)}</strong></td><td>${esc(serviceName(q.service_id))}</td><td>${pill(ticketSourceLabel(q.source), "blue")}</td><td>${q === current ? (q.started ? "Обслуживается" : "Вызван") : "Ожидает"}</td><td>${q.wait} мин</td><td>${q === current ? "№ 3" : "—"}</td></tr>`).join("")}</tbody></table></div>`;
  }
  function operator() {
    const {
      queue,
      current,
      opened,
      closing,
      enabled,
      served,
      problems,
      rules,
    } = getState();
    return `<div class="grid operator"><section class="card"><div class="row"><h2>Очередь</h2>${pill(queue.length, "gray")}</div><p class="muted">Запись по времени, затем ожидающие. Демонстрационный порядок.</p>${queueList()}<div class="section-gap">${btn("+ Добавить клиента", "add", "ghost")}</div></section><section class="card current"><div>${pill(current ? (current.started ? "Обслуживание" : "Клиент вызван") : "Окно № 3", "blue")}</div>${current ? `<div class="number">${esc(current.ticket_label)}</div><h2>${esc(serviceName(current.service_id))}</h2><div class="muted">${esc(ticketSourceLabel(current.source))} · Ожидание ${current.wait} мин</div><p>${current.started ? "Клиент обслуживается в вашем окне" : "Пригласите клиента к окну № 3"}</p><div class="actions">${btn(current.started ? "Завершить обслуживание" : "Начать обслуживание", current.started ? "finish" : "start", "primary")}${!current.started ? btn("Повторить вызов", "repeat", "ghost") : ""}<div class="row">${btn("Вернуть в очередь", "return", "")}${btn("Перенаправить", "redirect", "")}</div>${!current.started ? btn("Клиент не подошёл", "absent", "ghost") : ""}${btn("История", "ticket-history", "ghost")}</div>` : `<div class="empty-icon">↗</div><h2>${opened ? "Готовы к следующему клиенту" : "Окно закрыто"}</h2><p class="muted">${opened ? "Вызовите клиента из очереди.<br>Система учтёт доступные услуги окна." : "Откройте окно и выберите услуги,<br>чтобы начать обслуживание."}</p><div class="actions">${btn(opened ? "Вызвать следующего" : "Открыть окно", opened ? "call" : "open", "primary", (opened && !queue.some((q) => enabled.includes(q.service_id))))}</div>`}${closing ? '<div class="alert">Окно закроется после обслуживания</div>' : ""}</section><section class="card"><h2>Моё окно</h2><p class="muted">${esc(getState().operatorName || "Анна Иванова")} · Оператор</p><div class="status-line">${pill(opened ? "● Открыто" : "Закрыто", opened ? "" : "gray")}</div><h3>Доступные услуги</h3>${enabled.map((s) => `<div class="service">${esc(serviceName(s))}</div>`).join("")}${btn("Изменить услуги", "services", "ghost compact")}<div class="metric">${served}</div><span class="muted">обслужено за смену</span><div class="metric">4 мин</div><span class="muted">среднее обслуживание · демо</span><div class="section-gap">${btn("Сообщить о проблеме", "problem", "ghost")}</div></section></div>`;
  }
  function windows() {
    const {
      queue,
      current,
      opened,
      closing,
      enabled,
      served,
      problems,
      rules,
      services = [],
    } = getState();
    return `<div class="grid windows">${[1, 2, 3, 4, 5, 6].map((n) => `<div class="card window ${n > 4 ? "closed" : ""}"><div class="row"><h2>Окно № ${n}</h2>${pill(n === 3 ? (opened ? "Открыто" : "Закрыто") : n > 4 ? "Закрыто" : n === 2 ? "Свободно" : "Обслуживание", n > 4 ? "gray" : "blue")}</div><p>${n === 3 ? esc(getState().operatorName || "Анна Иванова") : n > 4 ? "Оператор не назначен" : ["Елена Петрова", "Игорь Волков", "Анна Иванова", "Мария Орлова"][n - 1]}</p><div class="service">${n === 3 ? esc(enabled.map(serviceName).join(", ")) : esc(services[(n - 1) % 3]?.name ?? "")}</div><p class="muted">${n === 3 ? (current ? "Талон " + esc(current.ticket_label) : "Нет активного клиента") : n > 4 ? "Откройте окно при росте очереди" : "Демонстрационные данные"}</p>${btn("Настроить окно", "window-" + n, "ghost compact")}</div>`).join("")}</div>`;
  }
  function overview() {
    const {
      queue,
      current,
      opened,
      closing,
      enabled,
      served,
      problems,
      rules,
    } = getState();
    return `<div class="grid stats">${[
      [queue.length, "Ожидают сейчас"],
      ["11 мин", "Среднее ожидание · демо"],
      [
        Math.max(0, ...queue.map((q) => q.wait)) + " мин",
        "Максимальное сейчас",
      ],
      [served + 105, "Обслужено · демо"],
    ]
      .map(
        ([a, b]) =>
          `<div class="card"><div class="muted">${b}</div><div class="metric">${a}</div></div>`,
      )
      .join(
        "",
      )}</div><div class="row"><h2>Работа окон</h2><span class="muted">4 из 6 · демонстрация</span></div>${windows()}<div class="grid two section-gap"><section class="card"><h2>Очередь отделения</h2>${table()}</section><section class="card"><h2>Требует внимания</h2>${problems.map((p) => `<div class="alert">${esc(p)}</div>`).join("")}${btn("Все проблемы →", "problems", "ghost")}</section></div>`;
  }
  function analytics() {
    const { analyticsOffset = 0 } = getState();
    const report = getDailyReport(analyticsOffset);
    return `<section class="card row section-gap" style="margin:0 0 24px"><button class="ghost" data-action="analytics-previous" aria-label="Предыдущий день">←</button><div style="text-align:center"><div class="report-date"><span>${report.label}</span><button class="report-date-toggle" data-action="open-report-calendar" aria-label="Открыть календарь"><span aria-hidden="true"></span></button><input id="analytics-date" class="report-date-input" type="date" aria-label="Дата отчёта" value="${report.dateValue}" max="${getDailyReport().dateValue}"></div><div class="muted">Статистика за день · демонстрационные данные</div></div><div class="row">${btn("Сегодня", "analytics-today", "ghost compact", analyticsOffset === 0)}<button class="ghost" data-action="analytics-next" aria-label="Следующий день" ${analyticsOffset === 0 ? "disabled" : ""}>→</button></div></section><div class="grid stats">${[
      [report.total, "Обслужено"],
      [report.averageWait + " мин", "Среднее ожидание"],
      [report.maximumWait + " мин", "Максимальное ожидание"],
      [report.averageService + " мин", "Среднее обслуживание"],
    ]
      .map(
        ([a, b]) =>
          `<div class="card"><span class="muted">${b}</span><div class="metric">${a}</div></div>`,
      )
      .join(
        "",
      )}</div><div class="grid two"><section class="card"><h2>Обслуженные клиенты по часам</h2><p class="muted">${report.label} · иллюстративные данные</p><div class="bars">${report.hourly.map((n, i) => `<div class="bar">${n}<i style="height:${n * 4}px"></i>${9 + i}:00</div>`).join("")}</div></section><section class="card"><h2>Источники обращений</h2>${report.sources
      .map(
        ([s, n]) =>
          `<div class="queue-item row"><span>${esc(ticketSourceLabel(s))}</span><strong>${n}</strong></div>`,
      )
      .join(
        "",
      )}</section></div><section class="card section-gap"><h2>Загрузка окон</h2><p class="muted">Доля обслуживания от времени открытого окна · демонстрационные данные</p>${report.utilization.map((n, i) => `<div class="queue-item"><div class="row"><span>Окно № ${i + 1}</span><strong>${n}%</strong></div><div style="height:8px;background:#eef0ff;border-radius:8px;margin-top:12px"><div style="width:${n}%;background:#1928dc;height:8px;border-radius:8px"></div></div></div>`).join("")}</section>`;
  }
  function rulesView() {
    const {
      queue,
      current,
      opened,
      closing,
      enabled,
      served,
      problems,
      rules,
    } = getState();
    return `<section class="card"><h2>Баланс записи и живой очереди</h2><p class="muted">Пример настроек. В прототипе они сохраняются только до обновления страницы и не меняют демонстрационный порядок вызова.</p><div class="form-grid">${["Раннее прибытие, минут", "Допустимое опоздание, минут", "Повышение приоритета после, минут", "Последовательных вызовов по записи"].map((s, i) => `<div><label for="rule-${i}">${s}</label><input id="rule-${i}" type="number" min="1" max="120" value="${rules[i]}"></div>`).join("")}</div><div class="alert">Порог повышения приоритета не гарантирует обслуживание за указанное время. Ожидание зависит от нагрузки и доступных окон.</div><p class="muted">Внутри одинакового приоритета — порядок поступления. Уже вызванный клиент остаётся закреплённым за окном.</p>${btn("Сохранить настройки", "save-rules", "primary")}</section>`;
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
