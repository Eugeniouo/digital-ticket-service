import { departmentPath, request, segment } from "../shared/api.js";

const windowPath = (departmentId, windowId) =>
  `${departmentPath(departmentId)}/windows/${segment(windowId)}`;

export const authApi = {
  signIn: (payload) => request("/auth/signin", { method: "POST", body: payload }),
};

export const departmentApi = {
  list: (signal) => request("/departments", { signal }),
  get: (id, signal) => request(departmentPath(id), { signal }),
  getQueueRules: (id, signal) => request(`${departmentPath(id)}/queue-rules`, { signal }),
  patchQueueRules: (id, payload, signal) =>
    request(`${departmentPath(id)}/queue-rules`, { method: "PATCH", body: payload, signal }),
  getAnalytics: (id, date, signal) =>
    request(`${departmentPath(id)}/analytics?date=${segment(date)}`, { signal }),
};

export const servicesApi = {
  list: (departmentId, signal) => request(`${departmentPath(departmentId)}/services`, { signal }),
  active: (departmentId, signal) =>
    request(`${departmentPath(departmentId)}/services/active`, { signal }),
};

export const windowsApi = {
  list: (departmentId, signal) => request(`${departmentPath(departmentId)}/windows`, { signal }),
  update: (departmentId, windowId, payload) =>
    request(windowPath(departmentId, windowId), { method: "PATCH", body: payload }),
  open: (departmentId, windowId, payload) =>
    request(`${windowPath(departmentId, windowId)}:open`, { method: "POST", body: payload }),
  close: (departmentId, windowId) =>
    request(`${windowPath(departmentId, windowId)}:close`, { method: "POST" }),
  queue: (departmentId, windowId, signal) =>
    request(`${windowPath(departmentId, windowId)}/queue`, { signal }),
  callNext: (departmentId, windowId) =>
    request(`${windowPath(departmentId, windowId)}:call-next`, { method: "POST" }),
  start: (departmentId, windowId) =>
    request(`${windowPath(departmentId, windowId)}:start`, { method: "POST" }),
  noshow: (departmentId, windowId) =>
    request(`${windowPath(departmentId, windowId)}:noshow`, { method: "POST" }),
  complete: (departmentId, windowId) =>
    request(`${windowPath(departmentId, windowId)}:complete`, { method: "POST" }),
  requeue: (departmentId, windowId) =>
    request(`${windowPath(departmentId, windowId)}:requeue`, { method: "POST" }),
  redirect: (departmentId, windowId, payload) =>
    request(`${windowPath(departmentId, windowId)}:redirect`, { method: "POST", body: payload }),
};

export const issuesApi = {
  list: (departmentId, signal) => request(`${departmentPath(departmentId)}/issues`, { signal }),
  create: (departmentId, payload) =>
    request(`${departmentPath(departmentId)}/issues`, { method: "POST", body: payload }),
  resolve: (departmentId, issueId) =>
    request(`${departmentPath(departmentId)}/issues/${segment(issueId)}:resolve`, { method: "POST" }),
};

export const staffApi = {
  list: (signal) => request("/staff", { signal }),
  create: (payload) => request("/staff", { method: "POST", body: payload }),
  changePassword: (staffId, password) =>
    request(`/staff/${segment(staffId)}/password`, { method: "PATCH", body: { password } }),
};
