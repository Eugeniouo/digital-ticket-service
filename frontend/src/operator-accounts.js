import { isUuid } from './shared/ids.js';
import { getStaff } from './shared/staff-session.js';
import { staffApi } from './staff/api.js';

export function currentOperator() {
  const staff = getStaff();
  if (!staff) return null;
  return {
    id: staff.id,
    username: staff.username,
    display_name: staff.display_name,
    department_id: staff.department_id,
    role: staff.role,
    is_active: staff.is_active,
  };
}

function validateDepartment(department_id) {
  if (!isUuid(department_id)) throw new Error('Выберите отделение из списка.');
  const sessionDepartmentId = getStaff()?.department_id;
  if (sessionDepartmentId && sessionDepartmentId !== department_id) {
    throw new Error('Выберите отделение из списка.');
  }
}

function mapStaffError(error) {
  if (error?.status === 409) throw new Error('Этот логин уже занят.');
  if (error?.status === 403) throw new Error('Недостаточно прав.');
  if (error?.status === 404) throw new Error('Отделение не найдено.');
  if (error?.status === 400) throw new Error('Проверьте данные аккаунта.');
  throw error;
}

export function listOperators() {
  return staffApi.list();
}

export async function createOperator({ username, display_name, department_id, password }, role = 'operator') {
  username = username.trim().toLowerCase();
  display_name = display_name.trim();
  password = password.trim();

  if (!/^[a-z0-9._-]{3,40}$/.test(username)) throw new Error('Логин: 3–40 латинских букв, цифр, точек, дефисов или подчёркиваний.');
  if (!display_name || display_name.length > 100) throw new Error('Укажите имя длиной до 100 символов.');
  if (password.length < 8 || password.length > 128) throw new Error('Пароль должен содержать от 8 до 128 символов.');
  validateDepartment(department_id);

  try {
    return await staffApi.create({ username, display_name, department_id, password, role });
  } catch (error) {
    mapStaffError(error);
  }
}

export async function changePassword(id, password) {
  password = password.trim();
  if (password.length < 8 || password.length > 128) throw new Error('Пароль должен содержать от 8 до 128 символов.');
  if (!isUuid(id)) throw new Error('Аккаунт не найден.');

  try {
    return await staffApi.changePassword(id, password);
  } catch (error) {
    if (error?.status === 404) throw new Error('Аккаунт не найден.');
    mapStaffError(error);
  }
}
