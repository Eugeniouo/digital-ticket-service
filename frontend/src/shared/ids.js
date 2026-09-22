export const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function isUuid(value) {
  return typeof value === 'string' && UUID_PATTERN.test(value)
}

/** Department identity in visitor/QR/booking URLs is `department=<uuid>`. */
export function departmentIdFromSearch(search) {
  const params = search instanceof URLSearchParams ? search : new URLSearchParams(search ?? '')
  const value = params.get('department')
  return isUuid(value) ? value : null
}
