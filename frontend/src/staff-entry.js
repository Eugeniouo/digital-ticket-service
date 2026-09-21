import { isSignedIn } from './demo-session.js';
import { currentOperator } from './operator-accounts.js';

// Navigation guard for the prototype, not a security boundary.
let signedIn = false;
try { signedIn = isSignedIn(); } catch { /* Login explains storage limitations. */ }
if (signedIn && currentOperator()) {
  await import('./staff.js');
} else {
  location.replace('/src/login.html');
}
