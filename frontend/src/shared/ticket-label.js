/** Display prefix of a ticket label, matching query_service TicketService._get_category_prefix. */
export function ticketLabelPrefix(serviceName) {
  const name = String(serviceName).toLowerCase()
  if (name.includes('посылк')) return 'П'
  if (name.includes('пенси') || name.includes('пособи')) return 'С'
  if (name.includes('платеж') || name.includes('перевод')) return 'К'
  if (name.includes('письм')) return 'М'
  return 'У'
}

export function formatTicketLabel(prefix, serial) {
  return `${prefix}-${String(serial).padStart(3, '0')}`
}
