import { signOut } from './demo-session.js';
// No demo role switcher. Child management pages use the staff sidebar.
if (window.self === window.top && location.pathname !== '/') {
  const navigation = document.createElement('nav');
  navigation.className = 'app-navigation';
  navigation.setAttribute('aria-label', 'Навигация');
  const link = document.createElement('a');
  const staffPage = ['/src/staff.html', '/src/accounts.html', '/src/qr.html'].includes(location.pathname);
  link.textContent = staffPage ? 'Выйти' : '← На главную';
  link.href = staffPage ? '/src/login.html' : '/';
  if (staffPage) link.addEventListener('click', signOut);
  navigation.append(link);
  document.body.prepend(navigation);
}
