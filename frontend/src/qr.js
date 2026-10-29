import './manager-guard.js';
import { currentOperator } from './operator-accounts.js';
import { departmentCaption, departmentOptionLabel } from './shared/department.js';
import { departmentApi } from './staff/api.js';

const site = document.querySelector('#site-url');
const select = document.querySelector('#qr-department');
const message = document.querySelector('#qr-message');
const staff = currentOperator();
let department = null;
if (staff?.department_id) {
  try {
    department = await departmentApi.get(staff.department_id);
  } catch {
    department = null;
  }
}
if (department) {
  select.add(new Option(departmentOptionLabel(department), department.id));
}
select.disabled = true;
if (location.protocol === 'https:') site.value = location.origin;
document.querySelector('#generate').addEventListener('click', () => {
  document.querySelector('#qr-image').replaceChildren();
  document.querySelector('#qr-link').hidden = true;
  document.querySelector('#print').hidden = true;
  document.querySelector('#qr-address').textContent = '';
  try {
    if (!department) throw new Error('Отделение сотрудника не найдено. Войдите снова.');
    const origin = new URL(site.value.trim());
    if (
      origin.protocol !== 'https:' ||
      origin.username ||
      origin.password ||
      /^(localhost|127\.|0\.|\[::1\])/.test(origin.hostname)
    )
      throw new Error('Укажите публичный HTTPS-адрес опубликованного сайта, не localhost.');
    const url = new URL('/src/visitor.html', origin.origin);
    url.searchParams.set('department', department.id);
    const code = window.qrcode(0, 'M');
    code.addData(url.href);
    code.make();
    document.querySelector('#qr-image').innerHTML = code.createSvgTag({
      cellSize: 7,
      margin: 28,
      scalable: true,
    });
    document.querySelector('#qr-image svg').setAttribute('aria-label', 'QR-код страницы отделения');
    document.querySelector('#qr-address').textContent = departmentCaption(department);
    const link = document.querySelector('#qr-link');
    link.href = url.href;
    link.hidden = false;
    document.querySelector('#print').hidden = false;
    message.textContent =
      'Перед печатью откройте ссылку и проверьте сканирование на телефоне. Генератор не проверяет доступность сайта.';
  } catch (error) {
    message.textContent = error.message;
  }
});
document.querySelector('#print').addEventListener('click', () => window.print());
