/** Deterministic demo reports by day. Replace with API reports in production. */
export function getDailyReport(offset = 0, today = new Date()) {
  const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() + offset);
  const variation = Math.abs(offset) % 7;
  const hourly = [12, 24, 19, 31, 27, 24].map(value => value + variation);
  const total = hourly.reduce((sum, value) => sum + value, 0);
  return {
    label: date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }),
    dateValue: [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-'),
    hourly,
    total,
    averageWait: 11 + variation,
    maximumWait: 29 + variation * 2,
    averageService: 4 + variation % 2,
    sources: [['web', 45 + variation * 2], ['qr', 64 + variation * 3], ['walk-in', 28 + variation]],
    utilization: [78, 62, 85, 57].map(value => value - variation),
  };
}

/** Calendar-day arithmetic uses UTC to avoid daylight-saving hour shifts. */
export function dateOffset(value, today = new Date()) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [year, month, day] = value.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  const offset = Math.round((date.getTime() - Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())) / 86400000);
  return offset <= 0 ? offset : null;
}
