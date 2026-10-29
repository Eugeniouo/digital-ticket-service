// Start loading shared artwork once. Never change its URL on selection.
const assets = [
  'logo',
  'clock',
  'warning',
  'send-selected',
  'receive-selected',
  'receipt-selected',
  'payments-selected',
  'letter-selected',
  'services-selected',
];
for (const name of assets) {
  const image = new Image();
  image.src = `/assets/${name}.svg`;
  image.decode().catch(() => {
    /* The browser still handles normal image fallback. */
  });
}
