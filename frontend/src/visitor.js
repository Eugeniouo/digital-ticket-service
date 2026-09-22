import { request, departmentPath } from './tickets/api.js';
import { isUuid } from './tickets/storage.js';
const params = new URLSearchParams(location.search);
const id = params.get('department') || params.get('branch');
const caption = document.querySelector('#visitor-branch');
try {
  if (!isUuid(id)) throw new Error('Invalid department');
  const branch = await request(departmentPath(id));
  if (!branch.is_active) throw new Error('Inactive department');
  caption.textContent = `Отделение № ${branch.code}: ${branch.address}`;
  const join = document.querySelector('#join');
  join.href = `/?source=qr&branch=${encodeURIComponent(branch.id)}`;
  join.hidden = false;
} catch {
  caption.textContent = 'Не удалось загрузить отделение. Проверьте связь и QR-код: он должен содержать UUID отделения из backend.';
}
