/** Ticket series prefix is Service.kind (query_service issue_ticket). */
export function ticketLabelPrefix(kind) {
  return String(kind || 'other')
}

export function formatTicketLabel(prefix, serial) {
  return `${prefix}-${String(serial).padStart(3, '0')}`
}
