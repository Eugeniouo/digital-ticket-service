import './manager-guard.js';
import { departmentCaption } from './shared/department.js';
import { escapeHtml } from './shared/html.js';
import { listOperators, createOperator, changePassword, currentOperator } from './operator-accounts.js';
import { departmentApi } from './staff/api.js';

const form = document.querySelector('#create-account');
const message = document.querySelector('#account-message');
const modal = document.querySelector('#modal');
const manager = currentOperator();
let managerDepartment = null;
let accounts = [];
const departmentTitle = document.querySelector('#account-department');
departmentTitle.textContent = 'Загружаем отделение…';

function departmentById(id) {
  return managerDepartment?.id === id ? managerDepartment : null;
}

function render() {
  document.querySelector('#accounts').innerHTML = accounts.filter(account => account.role !== 'admin' && account.department_id === manager.department_id).map(account => {
    const department = departmentById(account.department_id);
    const place = department ? departmentCaption(department) : 'Отделение не найдено';
    return `<article class="queue-item"><h3>${escapeHtml(account.display_name)}</h3><p>${escapeHtml(account.username)} · ${escapeHtml(place)}</p><div class="row"><button data-password="${account.id}">Сменить пароль</button></div></article>`;
  }).join('') || '<p class="muted">Операторов пока нет. Создайте первый аккаунт.</p>';
}

async function loadAccounts() {
  try {
    accounts = await listOperators();
    render();
  } catch {
    message.textContent = 'Не удалось загрузить аккаунты.';
  }
}

if (manager?.department_id) {
  departmentApi.get(manager.department_id).then((department) => {
    managerDepartment = department;
    departmentTitle.textContent = departmentCaption(department);
    render();
  }).catch(() => {
    departmentTitle.textContent = 'Отделение не найдено';
  });
} else {
  departmentTitle.textContent = 'Отделение не найдено';
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
      department_id: manager.department_id,
    });
    form.reset();
    await loadAccounts();
    message.textContent = 'Оператор создан. Теперь можно войти с его логином и паролем.';
  } catch (error) { message.textContent = error.message; }
  finally { submit.disabled = false; }
});
document.querySelector('#accounts').addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  const id = button.dataset.password;
  const account = accounts.find(item => item.id === id);
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
      modal.innerHTML = '';
      await loadAccounts();
      message.textContent = 'Пароль изменён. Для следующего входа используйте новый пароль.';
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
try { void loadAccounts(); } catch { message.textContent = 'Не удалось загрузить аккаунты.'; }
