const params = new URLSearchParams(location.search);
const isBooking = location.pathname.startsWith('/booking');
const isQr = params.get('source') === 'qr';

const HOME_ACTIONS = [
  {
    href: '/booking',
    title: 'Записаться в отделение',
    hint: 'Выберите услугу, дату и время',
  },
  {
    href: '/src/scan.html',
    title: 'Отсканировать QR',
    hint: 'Получите талон в отделении',
  },
  {
    href: '/src/login.html',
    title: 'Войти как сотрудник отделения',
    hint: 'Вход в рабочее пространство',
    className: 'home-action-staff',
  },
];

function homeAction({ href, title, hint, className }, index) {
  const number = String(index + 1).padStart(2, '0');
  const classes = className ? `home-action ${className}` : 'home-action';
  return `<a class="${classes}" href="${href}"><span class="home-symbol" aria-hidden="true">${number}</span><span><strong>${title}</strong><small>${hint}</small></span><span aria-hidden="true">→</span></a>`;
}

function homeScreen() {
  const intro =
    '<img class="logo" src="/assets/logo.svg" alt="Почта России"><p class="home-kicker">ЭЛЕКТРОННАЯ ОЧЕРЕДЬ</p><h1>Как мы можем помочь?</h1><p class="home-description">Выберите удобный способ обращения</p>';
  return `<main class="screen home-screen">${intro}<div class="home-actions">${HOME_ACTIONS.map(homeAction).join('')}</div></main>`;
}

if (params.get('view') === 'ticket') {
  await import('./tickets/page.js');
} else if (isBooking || isQr) {
  await import('./app.js');
} else {
  document.querySelector('#root').innerHTML = homeScreen();

  const { createTicketStorage } = await import('./tickets/storage.js');
  if (!params.has('view') && createTicketStorage().read()) {
    const link = document.createElement('a');
    link.className = 'home-action';
    link.href = '/?view=ticket';
    link.textContent = 'Вернуться к моему талону';
    document.querySelector('.home-actions')?.prepend(link);
  }
}
