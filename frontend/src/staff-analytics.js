import { ticketSourceLabel } from './shared/ticket-source.js';

function pad2(value) {
  return String(value).padStart(2, '0');
}

function utcDateValue(date) {
  return `${date.getUTCFullYear()}-${pad2(date.getUTCMonth() + 1)}-${pad2(date.getUTCDate())}`;
}

/** Calendar-day arithmetic uses UTC to avoid daylight-saving hour shifts. */
export function dateOffset(value, today = new Date()) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [year, month, day] = value.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  )
    return null;
  const offset = Math.round(
    (date.getTime() - Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())) / 86400000,
  );
  return offset <= 0 ? offset : null;
}

export function dateValueFromOffset(offset = 0, today = new Date()) {
  return utcDateValue(
    new Date(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate() + offset)),
  );
}

export function todayDateValue(today = new Date()) {
  return dateValueFromOffset(0, today);
}

export function formatRuDate(dateValue) {
  const [year, month, day] = dateValue.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

function secondsToMinutes(seconds) {
  if (seconds == null) return null;
  const value = Number(seconds);
  return Number.isFinite(value) ? Math.round(value / 60) : null;
}

function loadPercent(ratio) {
  if (ratio == null) return null;
  const value = Number(ratio);
  return Number.isFinite(value) ? Math.round(value * 100) : null;
}

/** Map GET /analytics JSON to the staff report view-model. */
export function toDailyReportView(dto) {
  const dateValue = dto.date;
  return {
    dateValue,
    label: formatRuDate(dateValue),
    timezone: dto.timezone,
    total: dto.served_count,
    averageWait: secondsToMinutes(dto.avg_wait_seconds),
    maximumWait: secondsToMinutes(dto.max_wait_seconds),
    averageService: secondsToMinutes(dto.avg_service_seconds),
    hourly: (dto.hourly ?? []).map((item) => ({
      hour: item.hour,
      count: item.served_count,
      label: `${pad2(item.hour)}:00`,
    })),
    sources: (dto.sources ?? []).map((item) => ({
      source: item.source,
      label: ticketSourceLabel(item.source),
      count: item.count,
    })),
    windows: (dto.windows ?? []).map((item) => ({
      id: item.window_id,
      label: item.label,
      percent: loadPercent(item.load_ratio),
    })),
  };
}
