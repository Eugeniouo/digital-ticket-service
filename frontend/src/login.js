import { ApiError } from './shared/api.js';
import { departmentOptionLabel } from './shared/department.js';
import { setStaffSession } from './shared/staff-session.js';
import { authApi, departmentApi } from './staff/api.js';

const form = document.querySelector('#login-form');
const error = document.querySelector('#login-error');
const select = form.elements.department_id;
const submit = form.querySelector('button[type=submit]');

async function loadDepartments() {
  try {
    const departments = await departmentApi.list();
    select.replaceChildren();
    for (const department of departments) {
      select.add(new Option(departmentOptionLabel(department), department.id));
    }
    if (!departments.length) {
      error.textContent = 'Нет отделений. Сначала заполните справочник.';
      submit.disabled = true;
    }
  } catch {
    error.textContent = 'Не удалось загрузить отделения.';
    submit.disabled = true;
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  submit.disabled = true;
  try {
    const result = await authApi.signIn({
      username: form.elements.username.value,
      password: form.elements.password.value,
      department_id: select.value,
    });
    setStaffSession(result.access_token, result.staff);
    location.assign('/src/staff.html');
  } catch (failure) {
    error.textContent = failure instanceof ApiError && failure.status === 401
      ? 'Неверный логин или пароль.'
      : 'Не удалось войти. Попробуйте ещё раз.';
  } finally {
    submit.disabled = false;
  }
});
form.addEventListener('input', () => { error.textContent = ''; });
form.addEventListener('change', () => { error.textContent = ''; });

loadDepartments();
