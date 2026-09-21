const isBooking = location.pathname.startsWith('/booking');
const isQr = new URLSearchParams(location.search).get('source') === 'qr';
if (isBooking || isQr) {
  await import('./app.js');
} else {
  document.querySelector('#root').innerHTML = `<main class="screen home-screen"><img class="logo" src="/assets/logo.svg" alt="Почта России"><p class="home-kicker">ЭЛЕКТРОННАЯ ОЧЕРЕДЬ</p><h1>Как мы можем помочь?</h1><p class="home-description">Выберите удобный способ обращения</p><div class="home-actions"><a class="home-action" href="/booking"><span class="home-symbol" aria-hidden="true">01</span><span><strong>Записаться в отделение</strong><small>Выберите услугу, дату и время</small></span><span aria-hidden="true">→</span></a><a class="home-action" href="/src/scan.html"><span class="home-symbol" aria-hidden="true">02</span><span><strong>Отсканировать QR</strong><small>Получите талон в отделении</small></span><span aria-hidden="true">→</span></a><a class="home-action home-action-staff" href="/src/login.html"><span class="home-symbol" aria-hidden="true">03</span><span><strong>Войти как сотрудник отделения</strong><small>Вход в рабочее пространство</small></span><span aria-hidden="true">→</span></a></div></main>`;
}
