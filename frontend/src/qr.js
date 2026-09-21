import './manager-guard.js';
import { currentOperator } from './operator-accounts.js';
import { branches } from './mock-data.js';
const site = document.querySelector('#site-url');
const branch = document.querySelector('#qr-branch');
const message = document.querySelector('#qr-message');
branches.filter(item => item.id === currentOperator().department_id).forEach(item => branch.add(new Option(`№ ${item.id} · ${item.address}`, item.id)));
branch.disabled = true;
if (location.protocol === 'https:') site.value = location.origin;
document.querySelector('#generate').addEventListener('click', () => {
  document.querySelector('#qr-image').replaceChildren();
  document.querySelector('#qr-link').hidden = true;
  document.querySelector('#print').hidden = true;
  document.querySelector('#qr-address').textContent = '';
  try {
    const origin = new URL(site.value.trim());
    if (origin.protocol !== 'https:' || origin.username || origin.password || /^(localhost|127\.|0\.|\[::1\])/.test(origin.hostname)) throw new Error('Укажите публичный HTTPS-адрес опубликованного сайта, не localhost.');
    const url = new URL('/src/visitor.html', origin.origin);
    url.searchParams.set('branch', branch.value);
    const code = window.qrcode(0, 'M');
    code.addData(url.href); code.make();
    document.querySelector('#qr-image').innerHTML = code.createSvgTag({ cellSize: 7, margin: 28, scalable: true });
    document.querySelector('#qr-image svg').setAttribute('aria-label', 'QR-код страницы отделения');
    document.querySelector('#qr-address').textContent = `Отделение № ${branch.value} · ${branches.find(item => item.id === branch.value).address}`;
    const link = document.querySelector('#qr-link'); link.href = url.href; link.hidden = false;
    document.querySelector('#print').hidden = false;
    message.textContent = 'Перед печатью откройте ссылку и проверьте сканирование на телефоне. Генератор не проверяет доступность сайта.';
  } catch (error) { message.textContent = error.message; }
});
document.querySelector('#print').addEventListener('click', () => window.print());
