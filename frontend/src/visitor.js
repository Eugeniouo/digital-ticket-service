import { branches } from './mock-data.js';
const id = new URLSearchParams(location.search).get('branch');
const branch = branches.find(item => item.id === id);
const caption = document.querySelector('#visitor-branch');
if (!branch) {
  caption.textContent = 'Отделение не найдено. Отсканируйте QR-код на плакате ещё раз или обратитесь к сотруднику.';
} else {
  caption.textContent = `Отделение № ${branch.id}: ${branch.address}`;
  const join = document.querySelector('#join');
  join.href = `/?source=qr&branch=${encodeURIComponent(branch.id)}`;
  join.hidden = false;
}
