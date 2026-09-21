/** UI-only demo session. This is not authentication or authorization. */
const SESSION_KEY = 'pochta-demo-sign-in';

export function isSignedIn() {
  return sessionStorage.getItem(SESSION_KEY) === 'true';
}

export function signIn() {
  // Never retain the entered password or login.
  sessionStorage.setItem(SESSION_KEY, 'true');
}

export function signOut() {
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem('pochta-demo-operator-id');
}

export function staffDestination(role) {
  return `/src/staff.html?role=${role === 'admin' ? 'admin' : 'operator'}`;
}
