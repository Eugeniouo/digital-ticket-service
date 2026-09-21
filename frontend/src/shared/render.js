/** Update existing DOM instead of discarding loaded images and focused controls. */
export function renderHtml(container, html) {
  const images = new Map([...container.querySelectorAll('img')].map(image => [image.getAttribute('src'), image]));
  const template = document.createElement('template');
  template.innerHTML = html;
  reconcile(container, template.content);
  // A step may move the logo into a different wrapper. Retain its decoded image.
  for (const image of container.querySelectorAll('img')) {
    const previous = images.get(image.getAttribute('src'));
    if (!previous || previous === image || container.contains(previous)) continue;
    for (const attribute of [...previous.attributes]) {
      if (!image.hasAttribute(attribute.name)) previous.removeAttribute(attribute.name);
    }
    for (const attribute of image.attributes) previous.setAttribute(attribute.name, attribute.value);
    image.replaceWith(previous);
  }
}

function reconcile(parent, incoming) {
  const desired = [...incoming.childNodes];
  desired.forEach((next, index) => {
    const current = parent.childNodes[index];
    if (!current) { parent.append(next.cloneNode(true)); return; }
    if (current.nodeType !== next.nodeType || current.nodeName !== next.nodeName) {
      current.replaceWith(next.cloneNode(true));
      return;
    }
    if (next.nodeType !== Node.ELEMENT_NODE) {
      if (current.nodeValue !== next.nodeValue) current.nodeValue = next.nodeValue;
      return;
    }
    for (const attribute of [...current.attributes]) {
      if (!next.hasAttribute(attribute.name)) current.removeAttribute(attribute.name);
    }
    for (const attribute of next.attributes) {
      if (current.getAttribute(attribute.name) !== attribute.value) {
        current.setAttribute(attribute.name, attribute.value);
      }
    }
    // Properties can differ from attributes after a user edits a control.
    if (current instanceof HTMLInputElement) {
      if (current.value !== next.value) current.value = next.value;
      current.checked = next.checked;
    }
    reconcile(current, next);
  });
  while (parent.childNodes.length > desired.length) parent.lastChild.remove();
}
