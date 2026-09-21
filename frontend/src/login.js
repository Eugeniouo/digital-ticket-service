import { signIn } from './demo-session.js';
import { authenticate, initializeManager, listOperators } from './operator-accounts.js';
import { branches } from './mock-data.js';

const form = document.querySelector('#login-form');
const error = document.querySelector('#login-error');
const setup = !listOperators().some(account => account.role === 'manager');
if (setup) {
  document.querySelector('#login-title').textContent = 'Настройка руководителя';
  document.querySelector('.description').textContent = 'Первый запуск в этом браузере: создайте локальный аккаунт руководителя.';
  const name = document.createElement('input');
  name.id = 'setup-name'; name.name = 'displayName'; name.required = true; name.maxLength = 100;
  const label = document.createElement('label');
  label.htmlFor = name.id; label.textContent = 'Имя руководителя';
  const select = document.createElement('select');
  select.id = 'setup-branch'; select.name = 'branch';
  for (const branch of branches) select.add(new Option('№ ' + branch.id + ' · ' + branch.address, branch.id));
  const branchLabel = document.createElement('label');
  branchLabel.htmlFor = select.id; branchLabel.textContent = 'Отделение';
  form.prepend(label, name, branchLabel, select);
  form.elements.password.minLength = 8;
  form.elements.password.autocomplete = 'new-password';
  form.querySelector('button[type=submit]').textContent = 'Создать и войти';
}
form.addEventListener('submit', async event => {
  event.preventDefault();
  const button = form.querySelector('button[type=submit]');
  button.disabled = true;
  try {
    if (setup) await initializeManager({
      login: form.elements.username.value, password: form.elements.password.value,
      name: form.elements.displayName.value, branch: form.elements.branch.value,
    });
    const id = await authenticate(form.elements.username.value, form.elements.password.value);
    sessionStorage.setItem('pochta-demo-operator-id', id);
    signIn();
    form.reset();
    location.assign('/src/staff.html');
  } catch (failure) { error.textContent = failure.message; }
  finally { button.disabled = false; }
});
form.addEventListener('input', () => { error.textContent = ''; });
