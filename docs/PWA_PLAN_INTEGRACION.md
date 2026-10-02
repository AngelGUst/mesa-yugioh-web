# Duel Assistant — Propuesta y Plan de Integración PWA (Progressive Web App)

**Fecha:** Octubre de 2026  
**Objetivo:** Transformar Duel Assistant en una PWA con descarga progresiva de recursos en segundo plano, caché local de cartas y modo instalable para móviles y PC.

---

## 1. ¿Afecta al MVP actual?

**Respuesta: NO afecta negativamente ni rompe nada del MVP.**

La integración de una PWA se basa en el principio de **mejora progresiva (*Progressive Enhancement*)**:
* **Cero cambios en Backend:** FastAPI, SQLAlchemy, PostgreSQL, la autenticación JWT y los endpoints se mantienen **100% idénticos**.
* **Cero cambios en la base de datos:** No se tocan tablas ni migraciones.
* **Tolerancia a fallos:** Si un navegador antiguo o una conexión no soporta Service Workers, la aplicación sigue funcionando exactamente igual como hasta hoy por HTTP estándar.
* **Beneficio directo a la Fase 8 (Celular como cámara):** Al ser PWA, el celular puede "instalar" la app, ejecutándose en pantalla completa sin barra de navegación del navegador (Chrome/Safari), lo que otorga más espacio para el visor de la cámara.

---

## 2. ¿Qué tanto código se moverá? (Alcance del cambio)

El cambio es **mínimo y estrictamente aditivo** (se añaden archivos nuevos sin reescribir la lógica existente):

```text
frontend/
├── static/
│   ├── manifest.json            [NUEVO] Configuración de la PWA (nombre, tema, iconos)
│   └── icons/                   [NUEVO] Iconos de la app (192x192 y 512x512)
├── src/
│   ├── app.html                 [MODIFICADO] 2 líneas para enlazar el manifest y theme-color
│   └── service-worker.ts        [NUEVO] Service worker nativo de SvelteKit (lógica de caché)
```

### Detalle de modificaciones:

| Archivo | Acción | Impacto |
|---|---|---|
| `backend/*` | **Ninguna** | 0% cambios. |
| `frontend/src/app.html` | **Modificar** | Añadir `<link rel="manifest" href="/manifest.json">` y `<meta name="theme-color" content="#101812">`. |
| `frontend/static/manifest.json` | **Crear** | Define el nombre "Duel Assistant", colores oscuros y comportamiento `standalone` (app independiente). |
| `frontend/src/service-worker.ts` | **Crear** | SvelteKit compila automáticamente este archivo y le inyecta la lista de todos los assets generados para descargarlos en segundo plano. |

---

## 3. Estrategia de Caché Progresiva propuesta

No todos los datos se deben cachear igual. Para no interferir con las partidas en vivo, se dividen en 3 niveles:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        ESTRATEGIA DE CACHÉ                             │
├──────────────────────────┬───────────────────────┬─────────────────────┤
│ Tipo de Recurso          │ Estrategia            │ Comportamiento      │
├──────────────────────────┼───────────────────────┼─────────────────────┤
│ 1. Assets de la App      │ Cache-First           │ Se descargan en 2°  │
│    (HTML, JS, CSS, fonts)│ (Precarga silenciosa) │ plano. Carga en 0ms │
│                          │                       │ la próxima vez.     │
├──────────────────────────┼───────────────────────┼─────────────────────┤
│ 2. Imágenes de Cartas    │ Stale-While-Revalidate│ Se guardan en disco │
│    (YGOProDeck CDN)      │ con límite de tamaño  │ local al verse. No  │
│                          │                       │ vuelven a gastar red│
├──────────────────────────┼───────────────────────┼─────────────────────┤
│ 3. API y WebSockets      │ Network-Only          │ NUNCA se cachean.   │
│    (Duelos, LP, turnos)  │ (Siempre en vivo)     │ Datos 100% frescos  │
│                          │                       │ garantizados.       │
└──────────────────────────┴───────────────────────┴─────────────────────┘
```

---

## 4. Impacto en el servidor modesto (Intel Celeron 847)

Implementar la PWA es especialmente ventajoso para servidores con hardware ajustado:

1. **Ahorro masivo de ancho de banda y CPU:**
   * Sin PWA: Cada vez que un jugador o espectador abre la página, el Celeron tiene que transferir todos los archivos compilados de SvelteKit.
   * Con PWA: El Celeron los sirve **una sola vez**. El resto de las sesiones se cargan desde el almacenamiento local del teléfono o PC del usuario.
2. **Cero saturación por imágenes de cartas:**
   * Las cartas cacheadas en los dispositivos de los usuarios reducen las peticiones externas y la latencia del cliente a cero.
3. **CPU dedicada 100% al juego:**
   * El Celeron solo tendrá que procesar los eventos de WebSockets (turnos, LP y fases), que consumen menos de 1% de CPU.

---

## 5. Fases de ejecución recomendadas

1. **Paso 1: Manifiesto e Iconos:** Crear `static/manifest.json` y los iconos básicos.
2. **Paso 2: Service Worker de SvelteKit:** Implementar `src/service-worker.ts` utilizando las variables nativas de SvelteKit (`$service-worker: build, files, version`).
3. **Paso 3: Regla de exclusión de API:** Asegurar que `/api/*` y las conexiones WebSocket pasen directo a la red sin tocar la caché.
4. **Paso 4: Validación PWA:** Probar la instalación en navegador móvil (Android/iOS) y verificar la navegación offline de recursos estáticos.
