export const TICKET_STORAGE_KEY = 'pochta.visitor-ticket.v1'
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
export const isUuid = value => typeof value === 'string' && uuid.test(value)

export function validReference(value) {
  return Boolean(value && isUuid(value.departmentId) && isUuid(value.ticketId))
}

// Accessing localStorage itself may throw in restricted browsers.
export function createTicketStorage(getStorage = () => window.localStorage) {
  return {
    read() {
      try {
        const value = JSON.parse(getStorage().getItem(TICKET_STORAGE_KEY))
        return validReference(value) ? {
          departmentId: value.departmentId, ticketId: value.ticketId,
        } : null
      } catch { return null }
    },
    save(ref) {
      if (!validReference(ref)) throw new Error('Invalid ticket reference')
      try {
        getStorage().setItem(TICKET_STORAGE_KEY, JSON.stringify({
          departmentId: ref.departmentId, ticketId: ref.ticketId,
        }))
        return true
      } catch { return false }
    },
  }
}

export function referenceFromTicket(ticket) {
  const ref = { departmentId: ticket.department_id, ticketId: ticket.id }
  if (!validReference(ref)) throw new Error('Invalid ticket response')
  return ref
}
