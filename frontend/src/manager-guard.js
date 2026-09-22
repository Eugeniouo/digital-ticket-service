import { currentOperator } from './operator-accounts.js';
import { isSignedIn } from './demo-session.js';
// Client navigation guard. The API still checks the token.
if (!isSignedIn() || currentOperator()?.role !== 'admin') {
  location.replace('/src/login.html');
  throw new Error('Manager sign-in required');
}
