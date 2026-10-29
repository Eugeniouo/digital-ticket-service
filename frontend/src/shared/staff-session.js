const TOKEN_KEY = 'pochta-staff-access-token';
const STAFF_KEY = 'pochta-staff';

function readStorage(key) {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key, value) {
  sessionStorage.setItem(key, value);
}

function clearStorage(key) {
  try {
    sessionStorage.removeItem(key);
  } catch {
    /* Private mode may block storage; sign-out should still proceed. */
  }
}

export function getAccessToken() {
  return readStorage(TOKEN_KEY);
}

export function getStaff() {
  const raw = readStorage(STAFF_KEY);
  if (!raw) return null;
  try {
    const staff = JSON.parse(raw);
    if (!staff || typeof staff !== 'object' || typeof staff.id !== 'string') return null;
    return staff;
  } catch {
    return null;
  }
}

export function hasStaffSession() {
  return Boolean(getAccessToken() && getStaff());
}

export function setStaffSession(accessToken, staff) {
  if (typeof accessToken !== 'string' || !accessToken || !staff?.id) {
    throw new Error('Invalid staff session');
  }
  writeStorage(TOKEN_KEY, accessToken);
  writeStorage(STAFF_KEY, JSON.stringify(staff));
}

export function clearStaffSession() {
  clearStorage(TOKEN_KEY);
  clearStorage(STAFF_KEY);
  clearStorage('pochta-demo-sign-in');
  clearStorage('pochta-demo-operator-id');
}

export function departmentIdFromSession() {
  const id = getStaff()?.department_id;
  return typeof id === 'string' && id ? id : null;
}
