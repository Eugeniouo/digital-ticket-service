/** Form fields match GET/PATCH /queue-rules. UI is minutes, API is seconds. */
export const QUEUE_RULE_FIELDS = [
  { key: 'bonus_web', label: 'Бонус записи, минут' },
  { key: 'bonus_qr', label: 'Бонус QR, минут' },
  { key: 'bonus_walk_in', label: 'Бонус живой очереди, минут' },
  { key: 'max_wait_web', label: 'Запись сгорает через, минут после начала слота' },
  { key: 'max_wait_qr', label: 'Порог ожидания QR, минут' },
  { key: 'max_wait_walk_in', label: 'Порог ожидания живой очереди, минут' },
];

export const RULE_MINUTE_MIN = 0;
export const RULE_MINUTE_MAX = 1440;

export function queueRulesToMinutes(dto) {
  const minutes = {};
  for (const { key } of QUEUE_RULE_FIELDS) {
    const seconds = Number(dto[key]);
    minutes[key] = Number.isFinite(seconds) ? Math.round(seconds / 60) : 0;
  }
  return minutes;
}

export function queueRulesToSeconds(minutes) {
  const seconds = {};
  for (const { key } of QUEUE_RULE_FIELDS) {
    seconds[key] = minutes[key] * 60;
  }
  return seconds;
}

export function readQueueRulesForm(root = document) {
  const minutes = {};
  for (const { key } of QUEUE_RULE_FIELDS) {
    const raw = root.querySelector(`#rule-${key}`)?.value.trim() ?? '';
    const value = Number(raw);
    if (
      raw === '' ||
      !Number.isInteger(value) ||
      value < RULE_MINUTE_MIN ||
      value > RULE_MINUTE_MAX
    ) {
      return null;
    }
    minutes[key] = value;
  }
  return minutes;
}
