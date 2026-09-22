import { signIn } from './demo-session.js';
import { authenticate, initializeManager, listOperators } from './operator-accounts.js';
import { departments } from './mock-data.js';
import { departmentOptionLabel } from './shared/department.js';

const form = document.querySelector('#login-form');
const error = document.querySelector('#login-error');
const setupFields = document.querySelector('#setup-fields');
const nameInput = form.elements.display_name;
const select = form.elements.department_id;

for (const department of departments) select.add(new Option(departmentOptionLabel(department), department.id));

function needsSetup(departmentId) {
  return !listOperators().some(account => account.role === 'admin' && account.department_id === departmentId);
}

function applySetup() {
  const setup = needsSetup(select.value);

  document.querySelector('#login-title').textContent = setup ? 'Настройка руководителя' : 'Вход для сотрудников';
  document.querySelector('.description').textContent = setup
    ? 'В этом отделении ещё нет руководителя. Создайте локальный аккаунт.'
    : 'Войдите в рабочее пространство отделения';
  setupFields.hidden = !setup;
  nameInput.required = setup;
  form.elements.password.autocomplete = setup ? 'new-password' : 'current-password';
  form.querySelector('button[type=submit]').textContent = setup ? 'Создать и войти' : 'Войти';
}

applySetup();
select.addEventListener('change', applySetup);

form.addEventListener('submit', async event => {
  event.preventDefault();
  const button = form.querySelector('button[type=submit]');
  button.disabled = true;
  try {
    const departmentId = select.value;
    if (needsSetup(departmentId)) await initializeManager({
      username: form.elements.username.value, password: form.elements.password.value,
      display_name: nameInput.value, department_id: departmentId,
    });
    const id = await authenticate(form.elements.username.value, form.elements.password.value, departmentId);
    sessionStorage.setItem('pochta-demo-operator-id', id);
    signIn();
    form.reset();
    location.assign('/src/staff.html');
  } catch (failure) { error.textContent = failure.message; }
  finally { button.disabled = false; }
});
form.addEventListener('input', () => { error.textContent = ''; });
form.addEventListener('change', () => { error.textContent = ''; });
