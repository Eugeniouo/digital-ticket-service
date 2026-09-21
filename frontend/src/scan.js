import { branches } from './mock-data.js';

const video = document.querySelector('#camera');
const status = document.querySelector('#scan-status');
const start = document.querySelector('#start-camera');
const stop = document.querySelector('#stop-camera');
let stream;
let timer;
let generation = 0;

function stopCamera() {
  generation++;
  clearTimeout(timer);
  stream?.getTracks().forEach(track => track.stop());
  stream = null;
  video.srcObject = null;
  start.hidden = false;
  start.disabled = false;
  stop.hidden = true;
}

function destination(raw) {
  try {
    const url = new URL(raw);
    const branch = url.searchParams.get('branch');
    // Do not navigate to arbitrary sites, scripts or unrelated QR codes.
    if (url.origin !== location.origin || url.pathname !== '/src/visitor.html' || !branches.some(item => item.id === branch)) return null;
    return `/src/visitor.html?branch=${encodeURIComponent(branch)}`;
  } catch { return null; }
}

start.addEventListener('click', async () => {
  if (typeof window.jsQR !== 'function') {
    status.textContent = 'Не удалось загрузить распознавание QR. Обновите страницу или отсканируйте код обычной камерой телефона.';
    return;
  }
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    status.textContent = 'Для камеры откройте сайт по HTTPS. Локальный адрес компьютера на телефоне не подходит.';
    return;
  }
  start.disabled = true;
  const run = ++generation;
  try {
    const cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
    if (run !== generation) { cameraStream.getTracks().forEach(track => track.stop()); return; }
    stream = cameraStream;
    video.srcObject = stream;
    await video.play();
    if (run !== generation) return;
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d', { willReadFrequently: true });
    if (!context) throw new Error('Canvas is unavailable');
    start.hidden = true;
    stop.hidden = false;
    status.textContent = 'Поместите QR-код отделения в рамку.';
    async function scan() {
      if (run !== generation) return;
      try {
        if (!video.videoWidth || video.readyState < 2) {
          timer = setTimeout(scan, 250);
          return;
        }
        const scale = Math.min(1, 640 / video.videoWidth);
        canvas.width = Math.round(video.videoWidth * scale);
        canvas.height = Math.round(video.videoHeight * scale);
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const frame = context.getImageData(0, 0, canvas.width, canvas.height);
        const decoded = window.jsQR(frame.data, frame.width, frame.height, { inversionAttempts: 'attemptBoth' });
        const codes = decoded ? [{ rawValue: decoded.data }] : [];
        if (run !== generation) return;
        for (const code of codes) {
          const target = destination(code.rawValue);
          if (target) { stopCamera(); location.assign(target); return; }
          status.textContent = 'Это не QR-код отделения этого сайта. Наведите камеру на нужный код.';
        }
      } catch {
        stopCamera();
        status.textContent = 'Распознавание прервалось. Попробуйте включить камеру снова или используйте камеру телефона.';
        return;
      }
      if (run === generation) timer = setTimeout(scan, 250);
    }
    scan();
  } catch (error) {
    if (run !== generation) return;
    stopCamera();
    status.textContent = error.name === 'NotAllowedError' ? 'Доступ к камере не разрешён. Разрешите его в настройках сайта или используйте камеру телефона.' : 'Не удалось включить камеру. Проверьте, не занята ли она другим приложением.';
  }
});
stop.addEventListener('click', () => { stopCamera(); status.textContent = 'Камера выключена.'; });
window.addEventListener('pagehide', stopCamera);
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { stopCamera(); status.textContent = 'Камера выключена. Нажмите кнопку, чтобы продолжить.'; }
});
