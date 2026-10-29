import { clearStaffSession, hasStaffSession } from './shared/staff-session.js';

export function isSignedIn() {
  return hasStaffSession();
}

export function signOut() {
  clearStaffSession();
}

export function staffDestination(role) {
  return `/src/staff.html?role=${role === 'admin' ? 'admin' : 'operator'}`;
}
