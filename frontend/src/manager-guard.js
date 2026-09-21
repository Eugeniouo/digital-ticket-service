import { currentOperator } from './operator-accounts.js';
import { isSignedIn } from './demo-session.js';
// Prototype routing only. Real permissions must be enforced by the server.
if (!isSignedIn() || currentOperator()?.role !== 'manager') {
  location.replace('/src/login.html');
  throw new Error('Manager sign-in required');
}
