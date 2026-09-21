import { branches } from './mock-data.js';

const KEY = 'pochta-demo-operators-v1';
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
function validateBranch(branch) {
  if (!branches.some(item => item.id === branch)) throw new Error('Выберите отделение из списка.');
}
async function passwordFields(password) {
  if (password.length < 8 || !password.trim()) throw new Error('Пароль должен содержать не менее 8 символов.');
  const salt = Array.from(crypto.getRandomValues(new Uint8Array(16)));
  return { salt, passwordHash: await digest(password, salt) };
}
export async function createOperator({ login, name, branch, password }, role = 'operator') {
  login = login.trim().toLowerCase();
  name = name.trim();
  if (!/^[a-z0-9._-]{3,40}$/.test(login)) throw new Error('Логин: 3–40 латинских букв, цифр, точек, дефисов или подчёркиваний.');
  if (!name || name.length > 100) throw new Error('Укажите имя длиной до 100 символов.');
  validateBranch(branch);
  const fields = await passwordFields(password);
  const accounts = listOperators();
  if (accounts.some(account => account.login === login)) throw new Error('Этот логин уже занят.');
  accounts.push({ id: crypto.randomUUID(), login, name, branch, role, ...fields });
  save(accounts);
}

export async function initializeManager(details) {
  if (listOperators().some(account => account.role === 'manager')) throw new Error('Руководитель уже настроен. Войдите с его логином.');
  await createOperator(details, 'manager');
}
export async function changePassword(id, password) {
  const fields = await passwordFields(password);
  const accounts = listOperators();
  const account = accounts.find(item => item.id === id);
  if (!account) throw new Error('Аккаунт не найден.');
  Object.assign(account, fields);
  save(accounts);
}
export function changeBranch(id, branch) {
  validateBranch(branch);
  const accounts = listOperators();
  const account = accounts.find(item => item.id === id);
  if (!account) throw new Error('Аккаунт не найден.');
  account.branch = branch;
  save(accounts);
}
export async function authenticate(login, password) {
  const account = listOperators().find(item => item.login === login.trim().toLowerCase());
  if (!account || await digest(password, account.salt) !== account.passwordHash) throw new Error('Неверный логин или пароль.');
  return account.id;
}
export function currentOperator() {
  const id = sessionStorage.getItem('pochta-demo-operator-id');
  return listOperators().find(item => item.id === id) || null;
}
