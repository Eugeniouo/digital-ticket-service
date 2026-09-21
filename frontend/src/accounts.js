import './manager-guard.js';
import { branches } from './mock-data.js';
import { escapeHtml } from './shared/html.js';
import { listOperators, createOperator, changePassword, changeBranch, currentOperator } from './operator-accounts.js';

const form = document.querySelector('#create-account');
const message = document.querySelector('#account-message');
const modal = document.querySelector('#modal');
const branchOptions = selected => branches.map(branch => `<option value="${branch.id}" ${branch.id === selected ? 'selected' : ''}>№ ${branch.id} · ${escapeHtml(branch.address)}</option>`).join('');
form.elements.branch.innerHTML = branchOptions(currentOperator().branch);

function render() {
  document.querySelector('#accounts').innerHTML = listOperators().filter(account => account.role !== "manager").map(account => `<article class="queue-item"><h3>${escapeHtml(account.name)}</h3><p>${escapeHtml(account.login)} · Отделение № ${escapeHtml(account.branch)}</p><div class="row"><button data-password="${account.id}">Сменить пароль</button><button data-branch="${account.id}">Сменить отделение</button></div></article>`).join('') || '<p class="muted">Операторов пока нет. Создайте первый аккаунт.</p>';
}
form.addEventListener('submit', async event => {
  event.preventDefault();
  const submit = form.querySelector('button');
  submit.disabled = true;
  try {
    await createOperator({ login: form.elements.username.value, name: form.elements.displayName.value, password: form.elements.password.value, branch: form.elements.branch.value });
    form.reset(); render(); message.textContent = 'Оператор создан. Теперь можно войти с его логином и паролем.';
  } catch (error) { message.textContent = error.message; }
  finally { submit.disabled = false; }
});
document.querySelector('#accounts').addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  const passwordMode = Boolean(button.dataset.password);
  const id = button.dataset.password || button.dataset.branch;
  const account = listOperators().find(item => item.id === id);
  if (!account) return;
  modal.innerHTML = `<div class="backdrop"><section class="dialog" role="dialog" aria-modal="true" aria-labelledby="edit-title"><h2 id="edit-title">${passwordMode ? 'Новый пароль' : 'Другое отделение'}</h2><p>${escapeHtml(account.name)}</p><form id="edit-account"><label for="edit-value">${passwordMode ? 'Пароль — от 8 символов' : 'Отделение'}</label>${passwordMode ? '<input id="edit-value" name="value" type="password" required minlength="8" maxlength="200" autocomplete="new-password">' : `<select id="edit-value" name="value">${branchOptions(account.branch)}</select>`}<p id="edit-message" role="alert"></p><div class="footer"><button type="button" id="close-edit">Отмена</button><button class="primary" type="submit">Сохранить</button></div></form></section></div>`;
  modal.querySelector('#edit-value').focus();
  modal.querySelector('#close-edit').onclick = () => { modal.innerHTML = ''; button.focus(); };
  modal.querySelector('form').onsubmit = async event => {
    event.preventDefault();
    const edit = event.currentTarget;
    const submit = edit.querySelector('[type=submit]');
    submit.disabled = true;
    try {
      if (passwordMode) await changePassword(id, edit.elements.value.value);
      else changeBranch(id, edit.elements.value.value);
      modal.innerHTML = ''; render(); message.textContent = passwordMode ? 'Пароль изменён. Для следующего входа используйте новый пароль.' : 'Отделение изменено. Рабочий экран обновится при следующем открытии.';
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
