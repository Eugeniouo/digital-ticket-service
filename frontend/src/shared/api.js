import { getAccessToken } from "./staff-session.js";

export class ApiError extends Error {
  constructor(status) {
    super(`API request failed (${status})`);
    this.status = status;
  }
}

export async function request(path, { method = "GET", body, signal } = {}) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  if (signal?.aborted) abort();
  const timeout = setTimeout(abort, 10000);
  const token = getAccessToken();
  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    const response = await fetch(`/api${path}`, {
      method,
      signal: controller.signal,
      cache: "no-store",
      credentials: "same-origin",
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) throw new ApiError(response.status);
    if (response.status === 204) return null;
    const text = await response.text();
    if (!text) return null;
    return JSON.parse(text);
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
  }
}

export const segment = encodeURIComponent;
export const departmentPath = (id) => `/departments/${segment(id)}`;
