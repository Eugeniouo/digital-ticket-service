/** Ticket series prefix lives on ServiceKind (query_service ServiceKind.prefix). */
const PREFIX_BY_KIND = {
  parcel_receive: 'П',
  parcel_send: 'П',
  letters: 'М',
  payments: 'К',
  pension: 'С',
  other: 'У',
};

export function ticketLabelPrefix(kind) {
  return PREFIX_BY_KIND[kind] || PREFIX_BY_KIND.other;
}

export function formatTicketLabel(prefix, serial) {
  return `${prefix}-${String(serial).padStart(3, '0')}`;
}
