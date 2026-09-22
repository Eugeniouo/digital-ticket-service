import { renderHtml } from './shared/render.js';
import { openReportCalendar } from './report-calendar.js';
import { dateOffset } from './staff-analytics.js';
import './shared/assets.js';
import {
  escapeHtml as esc,
  button as btn,
  badge as pill,
} from "./shared/html.js";
import { services } from "./staff-data.js";
import { createStaffViews } from "./staff-views.js";
import { currentOperator } from './operator-accounts.js';
import { branches } from './mock-data.js';
const signedOperator = currentOperator();
const operatorBranch = branches.find(branch => branch.id === signedOperator?.department_id) || branches[1];
// Demo controller: session state, user actions and dialogs. No server calls.
let analyticsOffset = 0;

const root = document.querySelector("#staff");
const modal = document.querySelector("#modal");
let role =
    signedOperator?.role === "admin"
      ? "admin"
      : "operator",
  page = role === "admin" ? "Обзор" : "Рабочее место",
  opened = true,
  current = null,
  closing = false,
  served = 32,
  serial = 16;
let queue = [
  {
    id: "П-008",
    service: services[2],
    source: "web",
    wait: 3,
    time: "На 14:30",
  },
  {
    id: "Ж-015",
    service: services[0],
    source: "walk-in",
    wait: 29,
    time: "Повышен приоритет",
  },
  {
    id: "А-024",
    service: services[0],
    source: "qr",
    wait: 12,
    time: "В отделении",
  },
  {
    id: "А-025",
    service: services[1],
    source: "qr",
    wait: 8,
    time: "В отделении",
  },
];
let problems = [
    "Ожидание Ж-015 достигло 29 минут",
    "Нет открытого окна для услуги «Платежи и переводы»",
  ],
  enabled = [...services.slice(0, 3)];
const options = () => services.map((s) => `<option>${s}</option>`).join("");
let notificationTimer;
function notify(text) {
  clearTimeout(notificationTimer);
  document.querySelector("#toast").textContent = text;
  notificationTimer = setTimeout(() => {
    document.querySelector("#toast").textContent = "";
  }, 3200);
}
let rules = [10, 10, 20, 2];
const { queueList, table, operator, windows, overview, analytics, rulesView } =
  createStaffViews(() => ({
    operatorName: signedOperator?.display_name || "Анна Иванова",
    analyticsOffset,
    queue,
    current,
    opened,
    closing,
    enabled,
    served,
    problems,
    rules,
  }));

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
  renderHtml(root, `<header><div><img src="/assets/logo.svg" alt="Почта России"><small>Электронная очередь · Для сотрудников</small></div><div><strong>Отделение № ${esc(operatorBranch.id)}</strong><small>${esc(operatorBranch.address)}</small></div></header><div class="layout"><aside>${nav.map((n) => btn(n, "nav-" + n, page === n ? "active" : "")).join("")}<div class="aside-note">ПРОТОТИП · ДЕМО-ДАННЫЕ<br>Без подключения к серверу<br><br><a class="link" href="/">Клиентский интерфейс ↗</a></div></aside><main><div class="heading"><div><div class="demo">Рабочее пространство / ${role === "operator" ? "Оператор" : "Руководитель"}</div><h1>${page}</h1><span class="muted">${role === "operator" ? `Окно № 3 · ${esc(signedOperator?.display_name || "Анна Иванова")}` : "Состояние отделения и управление обслуживанием"}</span></div><div class="row">${role === "operator" ? btn(opened ? "Закрыть окно" : "Открыть окно", opened ? "close" : "open", "ghost") : ""}</div></div>${page === "Аккаунты" || page === "QR отделения" ? `<iframe title="${page}" src="/src/${page === "Аккаунты" ? "accounts" : "qr"}.html" style="width:100%;min-height:900px;border:0;border-radius:20px"></iframe>` : page === "Рабочее место" ? operator() : page === "Обзор" ? overview() : page === "Очередь" ? `<section class="card"><h2>Все талоны</h2>${table()}</section>` : page === "Окна и услуги" ? windows() : page === "Правила очереди" ? rulesView() : page === "Аналитика" ? analytics() : `<section class="card"><h2>Проблемы и отклонения</h2>${problems.map((p) => `<div class="alert">${esc(p)}</div>`).join("")}${btn("Сбой уведомлений: демо", "notification", "ghost")}</section>`}</main></div>`);
}
function dialog(title, body, footer) {
  modal.innerHTML = `<div class="backdrop"><section class="dialog" role="dialog" aria-modal="true" aria-label="${title}"><div class="row"><h2>${title}</h2>${btn("✕", "dismiss", "ghost compact")}</div>${body}<div class="footer ${title === "Закрыть окно?" ? "vertical" : ""}">${footer || btn("Сохранить", "confirm", "primary")}</div></section></div>`;
  modal.querySelector("input,select,textarea,button")?.focus();
}
let pending = "";
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") modal.innerHTML = "";
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
document.addEventListener("click", (e) => {
  const a = e.target.closest("[data-action]")?.dataset.action;
  if (!a) return;
  if (a === 'open-report-calendar') {
    const input = document.querySelector('#analytics-date');
    openReportCalendar(input.value, value => {
      const offset = dateOffset(value);
      if (offset === null) return;
      analyticsOffset = offset;
      render();
    });
    return;
  }
  if (a === "analytics-previous" || a === "analytics-next" || a === "analytics-today") {
    analyticsOffset = a === "analytics-today" ? 0 : Math.min(0, analyticsOffset + (a === "analytics-previous" ? -1 : 1));
    render();
    return;
  }
  if (a === "dismiss") {
    modal.innerHTML = "";
    return;
  }

  if (a.startsWith("nav-")) {
    if (role !== "admin" && !["nav-Рабочее место", "nav-История смены"].includes(a)) return;
    page = a.slice(4);
    render();
    return;
  }

  if (a === "problems") {
    page = "Проблемы и журнал";
    render();
    return;
  }

  if (a === "call" && opened && !current) {
    const i = queue.findIndex((q) => enabled.includes(q.service));
    if (i >= 0) {
      current = queue.splice(i, 1)[0];
      notify(`Талон ${current.id} вызван к окну № 3`);
    }
  }
  if (a === "start" && current) {
    current.started = true;
    notify(`Начато обслуживание ${current.id}`);
  }
  if (a === "repeat")
    notify(`Повторный вызов ${current.id} · демонстрационное уведомление`);
  if (a === "absent" && current && !current.started) {
    notify(`Талон ${current.id} закрыт: клиент не подошёл`);
    current = null;
    if (closing) {
      opened = false;
      closing = false;
    }
  }
  if (a === "finish" && current) {
    notify(`Обслуживание ${current.id} завершено`);
    current = null;
    served++;
    if (closing) {
      opened = false;
      closing = false;
    }
  }
  if (a === "close") {
    if (current) {
      dialog(
        "Закрыть окно?",
        "<p>Активный клиент останется у вас до завершения обслуживания. Или верните его в очередь с сохранением ожидания.</p>",
        btn("Закрыть после обслуживания", "close-later", "primary") +
          btn("Вернуть клиента и закрыть", "close-return", "danger"),
      );
      return;
    }
    opened = false;
    notify("Окно № 3 закрыто");
  }
  if (a === "close-later") {
    closing = true;
    modal.innerHTML = "";
    notify("Окно закроется после обслуживания");
  }
  if (["open", "services"].includes(a) || a.startsWith("window-")) {
    pending = a;
    if (a.startsWith("window-") && a !== "window-3") {
      dialog(
        "Окно № " + a.slice(7),
        "<p>Карточка демонстрационного окна. Полный интерактивный сценарий доступен для окна № 3.</p>",
        btn("Понятно", "dismiss", "primary"),
      );
      return;
    }
    dialog(
      a === "open" ? "Открытие окна" : "Услуги окна № 3",
      `<p class="muted">Выберите услуги, которые может обслуживать окно.</p><div class="checks">${services.map((s) => `<label><input type="checkbox" name="services" value="${s}" ${enabled.includes(s) ? "checked" : ""}>${s}</label>`).join("")}</div>`,
    );
    return;
  }
  if (
    ["add", "redirect", "return", "close-return", "problem"].includes(
      a,
    )
  ) {
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
      `${["add", "redirect"].includes(a) ? `<label for="service">Услуга</label><select id="service">${options()}</select>` : ""}${a === "redirect" ? '<p class="muted">Талон вернётся в общую очередь на выбранную услугу. Накопленное ожидание сохранится.</p>' : ""}${a !== "add" ? '<label for="reason">Причина</label><textarea id="reason" rows="3" placeholder="Кратко опишите ситуацию"></textarea>' : '<p class="muted">Источник будет указан автоматически. Сообщите номер талона клиенту.</p>'}`,
    );
    return;
  }
  if (a === "confirm") {
    const reason = modal.querySelector("#reason")?.value.trim();
    if (modal.querySelector("#reason") && !reason) {
      notify("Укажите причину");
      return;
    }
    if (
      pending === "open" ||
      pending === "services" ||
      pending === "window-3"
    ) {
      const values = [...modal.querySelectorAll("input:checked")].map(
        (x) => x.value,
      );
      if (!values.length) {
        notify("Выберите хотя бы одну услугу");
        return;
      }
      enabled = values;
      if (pending === "open") {
        opened = true;
        notify(`Окно № 3 открыто · ${signedOperator?.display_name || "Анна Иванова"}`);
      } else {
        notify("Настройки окна № 3 сохранены");
      }
    } else if (pending === "add") {
      const ticket = {
        id: "Ж-" + String(serial++).padStart(3, "0"),
        service: modal.querySelector("#service").value,
        source: "walk-in",
        wait: 0,
        time: "Только что",
      };
      queue.push(ticket);
      notify(`Добавлен талон ${ticket.id}`);
    } else if (pending === "problem") {
      problems.unshift(reason);
      notify(`Проблема зарегистрирована · ${reason}`);
    } else if (current) {
      if (pending === "redirect")
        current.service = modal.querySelector("#service").value;
      current.started = false;
      queue.push(current);
      notify(
        pending === "redirect"
          ? `${current.id}: перенаправлен · ${reason}`
          : `${current.id}: возвращён в очередь · ${reason}`,
      );
      current = null;
      if (pending === "close-return" || closing) {
        opened = false;
        closing = false;
      }
    }
    modal.innerHTML = "";
  }
  if (a === "save-rules") {
    const values = [0, 1, 2, 3].map((i) =>
      Number(document.querySelector("#rule-" + i).value),
    );
    if (values.some((n) => !Number.isInteger(n) || n < 1 || n > 120)) {
      notify("Укажите целые значения от 1 до 120");
      return;
    }
    rules = values;
    notify("Демонстрационные настройки сохранены");
  }
  if (a === "notification") {
    problems.unshift(
      "Адаптер уведомлений недоступен · повторная доставка ожидается (демо)",
    );
    notify("Показан сценарий сбоя уведомлений; очередь продолжает работу");
  }
  render();
});
render();

root.addEventListener('change', event => {
  if (event.target.id !== 'analytics-date') return;
  const offset = dateOffset(event.target.value);
  if (offset === null) {
    notify('Выберите корректную дату не позднее сегодняшнего дня.');
    render();
    return;
  }
  analyticsOffset = offset;
  render();
});
