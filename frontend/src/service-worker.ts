/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

import { build, files, version } from '$service-worker';

const CACHE = `duel-assistant-${version}`;
const ASSETS = [...build, ...files];

self.addEventListener('install', (event: any) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => (self as any).skipWaiting())
  );
});

self.addEventListener('activate', (event: any) => {
  event.waitUntil(
    caches.keys().then(async (keys) => {
      for (const key of keys) {
        if (key !== CACHE && key.startsWith('duel-assistant-')) {
          await caches.delete(key);
        }
      }
      await (self as any).clients.claim();
    })
  );
});

self.addEventListener('fetch', (event: any) => {
  const url = new URL(event.request.url);

  // Solo peticiones GET
  if (event.request.method !== 'GET') return;

  // REGLA NETWORK-ONLY: La API (/api/*) y WebSockets nunca se cachean para garantizar datos en vivo
  if (url.pathname.startsWith('/api') || url.protocol === 'ws:' || url.protocol === 'wss:') {
    return;
  }

  // REGLA CACHE-FIRST para imágenes de cartas (YGOProDeck CDN o assets de cartas)
  const isCardImage =
    url.hostname.includes('ygoprodeck.com') ||
    url.pathname.endsWith('.jpg') ||
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.webp');

  if (isCardImage) {
    event.respondWith(
      caches.open(`${CACHE}-cards`).then(async (cache) => {
        const cachedResponse = await cache.match(event.request);
        if (cachedResponse) {
          return cachedResponse;
        }
        try {
          const networkResponse = await fetch(event.request);
          if (networkResponse.ok) {
            cache.put(event.request, networkResponse.clone());
          }
          return networkResponse;
        } catch {
          return cachedResponse || new Response('Imagen no disponible sin conexión', { status: 503 });
        }
      })
    );
    return;
  }

  // REGLA CACHE-FIRST para assets estáticos generados por el build
  if (ASSETS.includes(url.pathname)) {
    event.respondWith(
      caches.open(CACHE).then(async (cache) => {
        const response = await cache.match(event.request);
        if (response) return response;
        return fetch(event.request);
      })
    );
    return;
  }

  // REGLA NETWORK-FIRST con fallback a caché para navegación HTML
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(event.request);
          if (cached) return cached;
          const fallback = await caches.match('/');
          return fallback || new Response('Sin conexión', { status: 503 });
        })
    );
    return;
  }
});
