# Duel Assistant — Estado de Integración PWA (Progressive Web App)

**Fecha:** Octubre de 2026  
**Objetivo:** documentar la PWA implementada: recursos de aplicación precargados, caché local de imágenes y modo instalable para móviles y PC.

---

## 1. Estado e impacto en el MVP

El manifiesto, los iconos y el service worker están implementados. La PWA mejora la carga de recursos estáticos, pero **no ofrece partidas offline**: autenticación, API y sincronización de duelos requieren conexión.

El service worker omite las peticiones `GET` a `/api/*`. Las conexiones WebSocket no usan el evento `fetch` del service worker; su sincronización se gestiona directamente entre navegador y backend. El trabajo de revisiones/snapshots del WebSocket sí incluye cambios separados en backend y base de datos.

El scanner requiere HTTPS para `getUserMedia`. El worker/WASM de AprilTag se sirve localmente desde el build PWA; Tesseract.js descarga el modelo OCR inglés en el primer uso. Si esa descarga falla, el usuario puede elegir manualmente una candidata del deck, pero el camera pairing y el registro siguen necesitando API/red.

El escáner usa `getUserMedia` en un contexto seguro (HTTPS o localhost). AprilTagJS/WASM se sirve localmente desde los assets del frontend. Tesseract.js ejecuta OCR en el dispositivo, pero descarga el modelo de idioma en el primer uso; si no hay conexión o falla esa descarga, se puede elegir manualmente una candidata del deck.

La app conserva su funcionamiento web normal cuando un navegador no soporta service workers; simplemente no obtiene caché offline ni instalación PWA.

---

## 2. Archivos implementados

La integración PWA existente usa estos archivos:

```text
frontend/
├── static/
│   ├── manifest.json            Configuración de nombre, tema e instalación
│   └── icons/                   Iconos de la app (192x192 y 512x512)
├── src/
│   ├── app.html                 Enlace al manifest y theme-color
│   └── service-worker.ts        Service worker nativo de SvelteKit
```

### Detalle de modificaciones:

| Archivo | Acción | Impacto |
|---|---|---|
| `backend/*` | Sin cambios para la función PWA | El WebSocket versionado es una función aparte y sí usa backend/base de datos. |
| `frontend/src/app.html` | Implementado | Enlaza `/manifest.json` y configura el tema visual. |
| `frontend/static/manifest.json` | Implementado | Define nombre, colores, `standalone` e iconos. |
| `frontend/src/service-worker.ts` | Implementado | Precarga assets de build y aplica reglas de caché por tipo de recurso. |
| `frontend/static/vendor/apriltag-js/` | Implementado | Worker y WASM local para la familia AprilTag `tagStandard41h12`, con licencia y NOTICE. |

---

## 3. Estrategia de caché implementada

No todos los datos se deben cachear igual. Para no interferir con las partidas en vivo, se dividen en 3 niveles:

| Tipo de recurso | Estrategia implementada | Comportamiento |
|---|---|---|
| Assets incluidos en el build | Cache-first y precarga durante instalación | Se solicitan por red si no están en caché. |
| Imágenes de cartas | Cache-first al primer acceso | Se conservan localmente; no hay límite ni expulsión configurados. |
| `GET /api/*` | Network-only desde el service worker | El service worker no responde desde su caché; API y autenticación requieren conexión. |
| WebSocket | Fuera del evento `fetch` del service worker | Conexión directa navegador-backend; requiere red para actualizaciones. |

---

## 4. Impacto en el servidor modesto (Intel Celeron 847)

La PWA puede reducir peticiones repetidas de assets e imágenes almacenados en los dispositivos. El efecto real depende de clientes y tráfico; no hay benchmarks de CPU, ancho de banda ni latencia registrados.

1. Los assets precargados pueden servirse desde el dispositivo después de la instalación o visita inicial.
2. Las imágenes ya vistas pueden reutilizarse desde caché; no se configura actualmente un máximo de almacenamiento.
3. La caché del cliente no cambia el coste de consultas, escrituras ni conexiones WebSocket del backend.

---

## 5. Estado y validación pendiente

1. Manifiesto, iconos y service worker: **implementados**.
2. Precarga de assets estáticos y exclusión de `GET /api/*`: **implementadas**.
3. Caché de imágenes: **implementada como cache-first**, sin límite de tamaño ni política de expulsión por ahora.
4. Instalación y navegación offline en navegadores móviles: **pendiente de validación manual** en Android/iOS.
5. La caché no sustituye la API: no hay cola offline de escrituras y un duelo no puede continuar sincronizado sin red.
