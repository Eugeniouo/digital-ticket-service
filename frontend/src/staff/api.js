import { departmentPath, request, segment } from "../shared/api.js";

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
