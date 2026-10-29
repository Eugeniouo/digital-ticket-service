export { ApiError, departmentPath, request } from '../shared/api.js';
import { departmentPath, request } from '../shared/api.js';

const ticketPath = (ref) =>
  `${departmentPath(ref.departmentId)}/tickets/${encodeURIComponent(ref.ticketId)}`;
export const ticketApi = {
  get: (ref, signal) => request(ticketPath(ref), { signal }),
  cancel: (ref, signal) => request(`${ticketPath(ref)}:cancel`, { method: 'POST', signal }),
  create: (departmentId, payload) =>
    request(`${departmentPath(departmentId)}/tickets`, {
      method: 'POST',
      body: payload,
    }),
  incomplete: (departmentId, signal) =>
    request(`${departmentPath(departmentId)}/tickets/incomplete`, { signal }),
  statusHistory: (ref, signal) => request(`${ticketPath(ref)}/status-history`, { signal }),
};
