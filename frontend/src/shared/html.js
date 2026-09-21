/** Escape text before inserting it into an HTML template. */
export function escapeHtml(value) {
  const entities = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };
  return String(value).replace(/[&<>"']/g, (character) => entities[character]);
}

export function button(text, action, className = "", disabled = false) {
  return `<button class="${escapeHtml(className)}" data-action="${escapeHtml(action)}" ${disabled ? "disabled" : ""}>${escapeHtml(text)}</button>`;
}

export function badge(text, className = "") {
  return `<span class="pill ${escapeHtml(className)}">${escapeHtml(text)}</span>`;
}
