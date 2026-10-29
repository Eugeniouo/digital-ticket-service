import { request, departmentPath } from './tickets/api.js';
import { departmentIdFromSearch } from './shared/ids.js';
import { departmentCaption } from './shared/department.js';

const id = departmentIdFromSearch(location.search);
const caption = document.querySelector('#visitor-department');
try {
  if (!id) throw new Error('Invalid department');
  const department = await request(departmentPath(id));
  if (!department.is_active) throw new Error('Inactive department');
  caption.textContent = departmentCaption(department);
  const join = document.querySelector('#join');
  join.href = `/?source=qr&department=${encodeURIComponent(department.id)}`;
  join.hidden = false;
} catch {
  caption.textContent =
    'Не удалось загрузить отделение. Проверьте связь и QR-код: он должен содержать UUID отделения.';
}
