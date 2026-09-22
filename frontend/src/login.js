import { signIn } from './demo-session.js';
import { authenticate, initializeManager, listOperators } from './operator-accounts.js';
import { departments } from './mock-data.js';
import { departmentOptionLabel } from './shared/department.js';

const form = document.querySelector('#login-form');
const error = document.querySelector('#login-error');
const setup = !listOperators().some(account => account.role === 'admin');
if (setup) {
  document.querySelector('#login-title').textContent = 'Настройка руководителя';
  document.querySelector('.description').textContent = 'Первый запуск в этом браузере: создайте локальный аккаунт руководителя.';
  const name = document.createElement('input');
  name.id = 'setup-name'; name.name = 'display_name'; name.required = true; name.maxLength = 100;
  const label = document.createElement('label');
  label.htmlFor = name.id; label.textContent = 'Имя руководителя';
  const select = document.createElement('select');
  select.id = 'setup-department'; select.name = 'department_id';
  for (const department of departments) select.add(new Option(departmentOptionLabel(department), department.id));
  const departmentLabel = document.createElement('label');
  departmentLabel.htmlFor = select.id; departmentLabel.textContent = 'Отделение';
  form.prepend(label, name, departmentLabel, select);
  form.elements.password.minLength = 8;
  form.elements.password.maxLength = 128;
  form.elements.password.autocomplete = 'new-password';
  form.querySelector('button[type=submit]').textContent = 'Создать и войти';
}
form.addEventListener('submit', async event => {
  event.preventDefault();
  const button = form.querySelector('button[type=submit]');
  button.disabled = true;
  try {
    if (setup) await initializeManager({
      username: form.elements.username.value, password: form.elements.password.value,
      display_name: form.elements.display_name.value, department_id: form.elements.department_id.value,
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
