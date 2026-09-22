import { isUuid } from './shared/ids.js';
import { getStaff } from './shared/staff-session.js';

const KEY = 'pochta-demo-operators-v3';
export function listOperators() {
  return JSON.parse(localStorage.getItem(KEY) || '[]');
}
function save(accounts) {
  localStorage.setItem(KEY, JSON.stringify(accounts));
}
async function digest(password, salt) {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', salt: new Uint8Array(salt), iterations: 100000, hash: 'SHA-256' }, key, 256);
  return Array.from(new Uint8Array(bits)).map(value => value.toString(16).padStart(2, '0')).join('');
}
function validateDepartment(department_id) {
  if (!isUuid(department_id)) throw new Error('Выберите отделение из списка.');
  const sessionDepartmentId = getStaff()?.department_id;
  if (sessionDepartmentId && sessionDepartmentId !== department_id) {
    throw new Error('Выберите отделение из списка.');
  }
}
async function passwordFields(password) {
  password = password.trim();
  if (password.length < 8 || password.length > 128) throw new Error('Пароль должен содержать от 8 до 128 символов.');
  const salt = Array.from(crypto.getRandomValues(new Uint8Array(16)));
  return { salt, passwordHash: await digest(password, salt) };
}
export async function createOperator({ username, display_name, department_id, password }, role = 'operator') {
  username = username.trim().toLowerCase();
  display_name = display_name.trim();
  if (!/^[a-z0-9._-]{3,40}$/.test(username)) throw new Error('Логин: 3–40 латинских букв, цифр, точек, дефисов или подчёркиваний.');
  if (!display_name || display_name.length > 100) throw new Error('Укажите имя длиной до 100 символов.');
  validateDepartment(department_id);
  const fields = await passwordFields(password);
  const accounts = listOperators();
  if (accounts.some(account => account.username === username && account.department_id === department_id)) throw new Error('Этот логин уже занят.');
  accounts.push({ id: crypto.randomUUID(), username, display_name, department_id, role, is_active: true, ...fields });
  save(accounts);
}

export async function initializeManager(details) {
  if (listOperators().some(account => account.role === 'admin' && account.department_id === details.department_id)) {
    throw new Error('Руководитель уже настроен. Войдите с его логином.');
  }

  await createOperator(details, 'admin');
}
export async function changePassword(id, password) {
  const fields = await passwordFields(password);
  const accounts = listOperators();
  const account = accounts.find(item => item.id === id);
  if (!account) throw new Error('Аккаунт не найден.');
  Object.assign(account, fields);
  save(accounts);
}
export async function authenticate(username, password, department_id) {
  const account = listOperators().find(item => item.username === username.trim().toLowerCase() && item.department_id === department_id);
  if (!account || account.is_active === false || await digest(password.trim(), account.salt) !== account.passwordHash) throw new Error('Неверный логин или пароль.');
  return account.id;
}
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
