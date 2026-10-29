import { isSignedIn } from './demo-session.js';
import { currentOperator } from './operator-accounts.js';

// Client navigation guard. The API still checks the token.
let signedIn = false;
try {
  signedIn = isSignedIn();
} catch {
  /* Login explains storage limitations. */
}
if (signedIn && currentOperator()) {
  await import('./staff.js');
} else {
  location.replace('/src/login.html');
}
