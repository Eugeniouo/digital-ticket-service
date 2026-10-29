export const TICKET_SOURCE_LABELS = {
  web: 'Запись',
  qr: 'QR-код',
  'walk-in': 'Живая очередь',
};

export function ticketSourceLabel(source) {
  return TICKET_SOURCE_LABELS[source] ?? source;
}
