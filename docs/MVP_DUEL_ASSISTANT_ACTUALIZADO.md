# Duel Assistant — MVP de asistencia para duelo físico

**Objetivo de producto:** usar una PC como tablero principal y uno o dos celulares como cámaras vinculadas para asistir —no arbitrar automáticamente— un duelo físico de Yu-Gi-Oh!.

## Estado de la visión

| Capacidades del producto | Estado |
|---|---|
| Cuenta, JWT, perfil, decks y salas | Implementado |
| Catálogo e impresiones físicas | Implementado |
| Selección de deck por jugador antes del duelo | Implementado en la creación/unión de sala |
| Persistencia de LP, turno, fase, eventos y cartas por zona | Implementada en API |
| Tablero de una sala persistida | Implementado para LP, turno, fase, resultado y registro/movimiento manual de cartas por zona. |
| Sincronización entre dos sesiones | Implementada con WebSocket, snapshots al conectar/reconectar y revisiones monotónicas. |
| Celular vinculado por QR | Implementado con token de un uso (5 min) y sesión acotada al duelo/jugador. |
| Cámara y calibración | Implementadas en `/scanner` para HTTPS, cámara trasera y AprilTag `tagStandard41h12`; falta validar físicamente en Android/iOS. |
| OCR y reconocimiento de cartas | Implementados como sugerencia local con Tesseract.js y candidatas del deck; el humano corrige/confirma. |
| Autorización privada de espectadores por sala | Implementada: invitación a cuenta existente, solo lectura, revocable y válida hasta finalizar el duelo. |
| Motor completo de reglas, cadenas y efectos | Fuera del MVP inicial |

## Decisiones de arquitectura

- La **PC** es la interfaz primaria para administrar la sala y el tablero.
- El **celular** será un dispositivo compañero de cámara, no una sesión independiente de juego.
- El **backend** será la fuente de verdad: autoriza, persiste eventos y difundirá cambios en tiempo real.
- El **frontend** solo envía intenciones; no es la autoridad de reglas ni de estado.
- Una detección visual será una propuesta con confianza y necesitará confirmación humana antes de modificar el duelo.
- El deck activo restringirá las candidatas del escaneo para reducir latencia y coincidencias incorrectas.

## Modelo de cartas

El sistema implementado separa dos conceptos:

| Nivel | Datos | Uso |
|---|---|---|
| Carta canónica | Nombre, efecto, tipo, ATK, DEF, nivel, raza, atributo y arquetipo. | Decks, estado y reglas futuras. |
| Impresión física | Código y nombre de set, idioma, rareza, código de rareza y precio. | Representación, inventario futuro y reconocimiento. |

Una carta canónica puede tener múltiples impresiones. La identidad de una impresión usa carta, código de set, código de rareza y rareza, por lo que dos variantes con el mismo `set_code` no se sobrescriben.

Un deck referencia siempre la carta canónica y puede indicar una impresión preferida. La impresión no cambia las reglas de la carta ni impide usar reimpresiones equivalentes.

## Flujo actual disponible

```text
Registro / login
  -> Home autenticado
  -> Crear o editar deck
       -> buscar catálogo local
       -> importar desde YGOProDeck si falta
       -> seleccionar sección e impresión preferida
  -> Crear sala con deck opcional
  -> Segundo jugador se une por código con su deck opcional
  -> Abrir tablero persistido; REST carga el snapshot inicial
  -> Registrar/mover copias del deck en zonas y consultar historial con actor/dispositivo
  -> WebSocket difunde estado y eventos con revisión monotónica
  -> Al reconectar, recibir snapshot actual y descartar revisiones antiguas
```

El tablero sincroniza LP, turno, fase, estado y copias registradas por zona. El scanner propone cartas desde una captura y registra solo después de la confirmación humana; la detección automática continua de movimientos sigue fuera del MVP.

El constructor de decks deduplica respuestas de catálogo y usa claves de render estables para soportar variantes de impresión sin provocar el error `each_key_duplicate`.

## Flujo del celular implementado

### Vinculación

Desde el tablero de la PC, el jugador pulsa **Vincular Escáner**. El backend genera un token aleatorio, de un solo uso y válido cinco minutos, vinculado al jugador y duelo. Al canjearlo, el teléfono recibe un token de cámara limitado a colocar/mover cartas de ese jugador; la sesión vence a las 12 horas como máximo y se revoca al terminar el duelo. La PC muestra un QR que abre:

```text
/scanner?pairing_token=...
```

El backend valida el pairing y el teléfono nunca recibe el JWT completo del jugador. El token de pairing no puede reutilizarse y la acción cámara solo acepta cartas del deck asignado.

### Calibración del tapete

La ruta `/scanner` detecta los cuatro AprilTags Standard41h12 impresos en [la hoja A4](marcadores/hoja_marcadores_A4.svg), con IDs `0`, `1`, `2` y `4`, colocados en las esquinas del tapete:

```text
[Superior izquierdo]                         [Superior derecho]

                     Tapete

[Inferior izquierdo]                         [Inferior derecho]
```

Con los cuatro marcadores se calcula una homografía y se dibuja la superposición de zonas. Si falta un marcador, se pierde la cámara o no puede validarse la calibración, se bloquea la confirmación. Falta probar tamaño/distancia e iluminación en los teléfonos físicos.

### Escaneo puntual confirmado

La primera versión no analiza video continuo. El jugador mantiene los marcadores visibles, captura la carta, revisa la propuesta OCR contra su deck y confirma zona/posición:

```text
Elegir acción y zona
  -> capturar carta
  -> verificar calibración y corregir perspectiva (captura manual)
  -> leer texto de la captura con OCR local
  -> buscar primero en el deck activo
  -> mostrar sugerencia y confianza
  -> confirmar, corregir o cancelar
  -> confirmar explícitamente
  -> registrar carta/evento idempotente y sincronizar el tablero
```

Acciones iniciales:

- Agregar a cartas desterradas.
- Enviar al cementerio.
- Invocar en una zona de monstruos.
- Colocar en una zona de magia/trampa.
- Mover al extra deck.
- Agregar a la mano.

## Estrategia de reconocimiento

Prioridad de identificación:

1. OCR del nombre normalizado de la captura, primero contra el deck activo.
2. Selección manual de una candidata del deck si el OCR no encuentra coincidencia clara.
3. Código de contraseña y código de set quedan para una mejora posterior del reconocedor.
4. ATK, DEF, nivel, tipo y atributo para desambiguar.
5. Ilustración como señal de respaldo.

No se transmitirá video continuo al servidor. La aplicación enviará una captura cuando el usuario lo solicite —o fotogramas reducidos y espaciados en una evolución posterior— para limitar batería, datos, procesamiento y latencia.

## Zonas de tablero objetivo

- Cinco Main Monster Zones por jugador.
- Cinco Spell & Trap Zones por jugador.
- Extra Monster Zones.
- Field Spell Zone.
- Graveyard.
- Extra Deck.
- Main Deck.
- Hand.
- Removed Cards / Banish Pile.

Las zonas son destinos elegidos manualmente desde el panel del tablero. Las posiciones de monstruos, magia/trampa y monstruo extra se validan; la detección automática de movimientos queda para después.

## Permisos

| Nivel | Rol | Alcance |
|---|---|---|
| Cuenta | Administrador | Privilegios administrativos globales. No se otorga desde el registro público. |
| Sala | Jugador | Crea o participa en un duelo y registra acciones de su lado. |
| Sala | Espectador | Requiere invitación por username a una cuenta existente. Solo lectura; un jugador puede revocar el acceso y la invitación expira al terminar el duelo. |

El árbitro o juez será un permiso de sala futuro, con acciones explícitas y limitadas; no debe ser un administrador global.

## Criterios de aceptación para el MVP completo

- [x] Dos jugadores autenticados pueden entrar a una misma sala mediante código.
- [x] El tablero refleja LP, turno, fase y estado persistidos; los eventos se guardan en la API.
- [x] Los jugadores registran/mueven copias del deck en zonas y el historial guarda actor, dispositivo, carta y zonas de origen/destino.
- [x] Las cartas del deck, la mano y las cartas boca abajo ocultan su identidad a otros participantes y espectadores.
- [x] Los cambios llegan a sesiones conectadas sin recargar; tras una reconexión llega un snapshot autoritativo versionado.
- [x] Solo participantes e invitados activos pueden consultar el duelo; el espectador no puede cambiar estado ni crear eventos.
- [x] Un jugador puede invitar y revocar cuentas espectadoras; la revocación cierra su WebSocket y finalizar el duelo retira todos los accesos de espectador.
- [x] Un teléfono autorizado se vincula con QR de un solo uso que expira a los cinco minutos y recibe una sesión acotada.
- [x] El scanner detecta los cuatro IDs AprilTag y calcula/dibuja la calibración; falta validación en los dispositivos físicos objetivo.
- [x] Una captura propone una carta del deck activo, el usuario la confirma y se registra en la zona elegida como evento de fuente `camera`.
- [x] Las impresiones de idiomas, rarezas o artes diferentes no duplican la carta en la lógica del deck.
- [x] La cámara/calibración inválida bloquea confirmar; los fallos de red conservan la captura y el ID idempotente evita duplicados. Falta prueba end-to-end física de desconexión/reconexión.

## Fuera de alcance inicial

- Detección continua y autónoma de todos los movimientos.
- Identificación confiable de cartas boca abajo.
- Aplicación completa de reglas, efectos y cadenas.
- Chat, replay, rangos y estadísticas competitivas avanzadas.
- Aplicación móvil nativa; la primera implementación será web/PWA.

## Orden de implementación restante

1. Validar en Android/iOS el certificado HTTPS, permisos de cámara, AprilTags impresos, calibración y OCR.
2. Añadir pruebas end-to-end con dos jugadores y un teléfono, incluyendo pérdida de red/cámara y reintentos.
3. Evolucionar más adelante a propuestas entre fotogramas y validaciones de reglas.
