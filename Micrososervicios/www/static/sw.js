/* =========================================================
   Service Worker - Librería Salesiana (PWA)
   Estrategia:
   - Precache de los archivos base al instalar.
   - Navegación: network-first con respaldo a caché.
   - Estáticos (css/js/img): cache-first.
   - APIs (/api/*): solo red (no se cachean datos de negocio).
   ========================================================= */
const CACHE_VERSION = 'librospe-v4';
const PRECACHE = [
  '/',
  '/catalogo',
  '/static/css/base.css',
  '/static/css/base_cliente.css',
  '/static/css/catalogo_cliente.css',
  '/static/css/index.css',
  '/static/js/app.js',
  '/static/js/cliente.js',
  '/static/js/index.js',
  '/static/js/catalogo_cliente_2.js',
  '/static/img/default-product.png',
  '/static/img/icon-192.png',
  '/static/img/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== 'GET') return;
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() =>
          caches.match(request).then((cached) =>
            cached || caches.match('/catalogo')
          )
        )
    );
    return;
  }

  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
          }
          return response;
        });
      })
    );
    return;
  }
});