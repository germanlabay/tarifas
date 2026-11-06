/* Service worker: deja la app disponible sin señal.
 *
 * El armazon (html/css/js/iconos) se sirve desde cache y se refresca en segundo
 * plano. Las tarifas NO se cachean aca: app.js las pide siempre a la red y
 * guarda la ultima copia descifrada en localStorage, asi nunca muestra una
 * tarifa vieja creyendo que es la actual.
 */

const VERSION = 'v2';
const CACHE = 'tarifas-' + VERSION;

const ARMAZON = [
  './',
  'index.html',
  'estilos.css',
  'app.js',
  'manifest.webmanifest',
  'icono-192.png',
  'icono-512.png',
];

self.addEventListener('install', (ev) => {
  ev.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(ARMAZON))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (ev) => {
  ev.waitUntil(
    caches.keys()
      .then((claves) => Promise.all(
        claves.filter((k) => k !== CACHE).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (ev) => {
  const req = ev.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Las tarifas siempre van a la red; si falla, app.js usa su copia local.
  if (url.pathname.includes('tarifas.json')) return;

  ev.respondWith(
    caches.match(req, { ignoreSearch: true }).then((guardado) => {
      const red = fetch(req)
        .then((resp) => {
          if (resp && resp.ok && resp.type === 'basic') {
            const copia = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copia));
          }
          return resp;
        })
        .catch(() => guardado || caches.match('index.html'));

      return guardado || red;
    })
  );
});
