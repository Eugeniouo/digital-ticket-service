import './manager-guard.js';
import { departments } from './mock-data.js';
import { departmentCaption, departmentOptionLabel } from './shared/department.js';
import { escapeHtml } from './shared/html.js';
import { listOperators, createOperator, changePassword, currentOperator } from './operator-accounts.js';

const form = document.querySelector('#create-account');
const message = document.querySelector('#account-message');
const modal = document.querySelector('#modal');
const departmentOptions = selected => departments.map(department => `<option value="${escapeHtml(department.id)}" ${department.id === selected ? 'selected' : ''}>${escapeHtml(departmentOptionLabel(department))}</option>`).join('');
form.elements.department_id.innerHTML = departmentOptions(currentOperator().department_id);

function departmentById(id) {
  return departments.find(department => department.id === id);
}

function render() {
  document.querySelector('#accounts').innerHTML = listOperators().filter(account => account.role !== 'admin').map(account => {
    const department = departmentById(account.department_id);
    const place = department ? departmentCaption(department) : 'Отделение не найдено';
    return `<article class="queue-item"><h3>${escapeHtml(account.display_name)}</h3><p>${escapeHtml(account.username)} · ${escapeHtml(place)}</p><div class="row"><button data-password="${account.id}">Сменить пароль</button></div></article>`;
  }).join('') || '<p class="muted">Операторов пока нет. Создайте первый аккаунт.</p>';
}
form.addEventListener('submit', async event => {
  event.preventDefault();
  const submit = form.querySelector('button');
  submit.disabled = true;
  try {
    await createOperator({
      username: form.elements.username.value,
      display_name: form.elements.display_name.value,
      password: form.elements.password.value,
      department_id: form.elements.department_id.value,
    });
    form.reset(); render(); message.textContent = 'Оператор создан. Теперь можно войти с его логином и паролем.';
  } catch (error) { message.textContent = error.message; }
  finally { submit.disabled = false; }
});
document.querySelector('#accounts').addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  const id = button.dataset.password;
  const account = listOperators().find(item => item.id === id);
  if (!account) return;
  modal.innerHTML = `<div class="backdrop"><section class="dialog" role="dialog" aria-modal="true" aria-labelledby="edit-title"><h2 id="edit-title">Новый пароль</h2><p>${escapeHtml(account.display_name)}</p><form id="edit-account"><label for="edit-value">Пароль — от 8 символов</label><input id="edit-value" name="value" type="password" required minlength="8" maxlength="128" autocomplete="new-password"><p id="edit-message" role="alert"></p><div class="footer"><button type="button" id="close-edit">Отмена</button><button class="primary" type="submit">Сохранить</button></div></form></section></div>`;
  modal.querySelector('#edit-value').focus();
  modal.querySelector('#close-edit').onclick = () => { modal.innerHTML = ''; button.focus(); };
  modal.querySelector('form').onsubmit = async event => {
    event.preventDefault();
    const edit = event.currentTarget;
    const submit = edit.querySelector('[type=submit]');
    submit.disabled = true;
    try {
      await changePassword(id, edit.elements.value.value);
      modal.innerHTML = ''; render(); message.textContent = 'Пароль изменён. Для следующего входа используйте новый пароль.';
    } catch (error) { modal.querySelector('#edit-message').textContent = error.message; submit.disabled = false; }
  };
});
document.addEventListener('keydown', event => {
  if (!modal.firstChild) return;
  if (event.key === 'Escape') { modal.innerHTML = ''; return; }
  if (event.key === 'Tab') {
    const fields = [...modal.querySelectorAll('input,select,button')];
    if (event.shiftKey && document.activeElement === fields[0]) { event.preventDefault(); fields.at(-1).focus(); }
    else if (!event.shiftKey && document.activeElement === fields.at(-1)) { event.preventDefault(); fields[0].focus(); }
  }
});
try { render(); } catch { message.textContent = 'Данные недоступны. Проверьте разрешение на хранение данных сайта.'; }
