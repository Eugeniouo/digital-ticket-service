import { isUuid } from '../shared/ids.js'

export const TICKET_STORAGE_KEY = 'pochta.visitor-ticket.v1'

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
    clear() {
      try {
        getStorage().removeItem(TICKET_STORAGE_KEY)
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
