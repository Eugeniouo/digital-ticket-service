import { getDailyReport } from './staff-analytics.js';

/** Accessible modal date picker, styled with the application palette. */
export function openReportCalendar(selected, onSelect) {
  const [year, month] = selected.split('-').map(Number);
  let viewed = new Date(year, month - 1, 1);
  const today = getDailyReport().dateValue;
  const previousFocus = document.activeElement;
  const dialog = document.createElement('dialog');
  dialog.className = 'report-calendar';
  dialog.setAttribute('aria-labelledby', 'report-calendar-title');
  document.body.append(dialog);

  function draw() {
    const y = viewed.getFullYear();
    const m = viewed.getMonth();
    const offset = (new Date(y, m, 1).getDay() + 6) % 7;
    const count = new Date(y, m + 1, 0).getDate();
    const label = viewed.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
    const nextMonth = `${y}-${String(m + 1).padStart(2, '0')}` >= today.slice(0, 7);
    dialog.innerHTML = `<div class="report-calendar-top"><div><span class="report-calendar-caption">СТАТИСТИКА ЗА ДЕНЬ</span><h2 id="report-calendar-title">Выберите дату</h2></div><button type="button" data-calendar="close" class="calendar-close" aria-label="Закрыть календарь">×</button></div><div class="report-month"><button type="button" data-calendar="previous" aria-label="Предыдущий месяц">‹</button><strong aria-live="polite">${label}</strong><button type="button" data-calendar="next" aria-label="Следующий месяц" ${nextMonth ? 'disabled' : ''}>›</button></div><div class="report-weekdays" aria-hidden="true">${['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].map(day => `<span>${day}</span>`).join('')}</div><div class="report-days">${'<span></span>'.repeat(offset)}${Array.from({ length: count }, (_, index) => {
      const day = index + 1;
      const value = `${y}-${String(m + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const spoken = new Date(y, m, day).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
      return `<button type="button" data-day="${value}" class="report-day ${value === selected ? 'selected' : ''} ${value === today ? 'today' : ''}" aria-label="${spoken}" aria-pressed="${value === selected}" ${value === today ? 'aria-current="date"' : ''} ${value > today ? 'disabled' : ''}>${day}</button>`;
    }).join('')}</div><div class="report-calendar-bottom"><span>Будущие даты недоступны</span><button type="button" data-calendar="today">Сегодня</button></div>`;
  }

  function choose(value) {
    onSelect(value);
    dialog.close();
  }
  dialog.addEventListener('click', event => {
    const button = event.target.closest('button');
    if (!button || button.disabled) return;
    if (button.dataset.day) { choose(button.dataset.day); return; }
    const action = button.dataset.calendar;
    if (action === 'close') dialog.close();
    if (action === 'today') choose(today);
    if (action === 'previous' || action === 'next') {
      viewed.setMonth(viewed.getMonth() + (action === 'previous' ? -1 : 1));
      draw();
      dialog.querySelector(`[data-calendar="${action}"]:not(:disabled)`)?.focus();
    }
  });
  dialog.addEventListener('close', () => { dialog.remove(); previousFocus?.focus({ preventScroll: true }); });
  draw();
  dialog.showModal();
  (dialog.querySelector('.selected:not(:disabled)') || dialog.querySelector('.report-day:not(:disabled)'))?.focus();
}
