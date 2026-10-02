# Duel Assistant — MVP de asistencia para duelo físico

**Objetivo de producto:** usar una PC como tablero principal y uno o dos celulares como cámaras vinculadas para asistir —no arbitrar automáticamente— un duelo físico de Yu-Gi-Oh!.

## Estado de la visión

| Capacidades del producto | Estado |
|---|---|
| Cuenta, JWT, perfil, decks y salas | Implementado |
| Catálogo e impresiones físicas | Implementado |
| Selección de deck por jugador antes del duelo | Implementado en la creación/unión de sala |
| Persistencia de LP, turno, fase y eventos | Implementado en API |
| Tablero de una sala persistida | Pendiente |
| Sincronización entre dos sesiones | Pendiente: no hay WebSockets |
| Celular vinculado por QR | Pendiente |
| Cámara, calibración y escaneo puntual | Pendiente |
| OCR y reconocimiento de cartas | Pendiente |
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
  -> API persiste LP, turno, fase, resultado y eventos
```

El constructor de decks deduplica respuestas de catálogo y usa claves de render estables para soportar variantes de impresión sin provocar el error `each_key_duplicate`.

## Flujo objetivo del celular

### Vinculación

Desde el tablero de la PC, el jugador pulsará **Vincular cámara**. El backend generará un token temporal, de un solo uso, vinculado al usuario y duelo. La PC mostrará un QR que abrirá:

```text
/scanner?pairing_token=...
```

El backend deberá validar tanto el token como que el propietario del teléfono sea un participante autorizado. Un token QR no sustituye la autorización de sala.

### Calibración del tapete

La cámara deberá reconocer cuatro marcadores ArUco o AprilTags colocados alrededor del tapete:

```text
[Superior izquierdo]                         [Superior derecho]

                     Tapete

[Inferior izquierdo]                         [Inferior derecho]
```

Con los cuatro marcadores se calculará una homografía y se dibujarán las zonas virtuales. Si falta un marcador o la cámara cambia de posición, se pausará el escaneo y se pedirá recalibrar. Se usan marcadores fiduciarios y no post-its de colores porque son más estables ante luz, sombras y reflejos.

### Escaneo puntual confirmado

La primera versión de cámara no analizará video continuo. El jugador elegirá una intención, encuadrará la carta y confirmará el resultado:

```text
Elegir acción y zona
  -> capturar carta
  -> corregir perspectiva
  -> reconocer código, set y texto
  -> buscar primero en el deck activo
  -> mostrar sugerencia y confianza
  -> confirmar, corregir o cancelar
  -> persistir evento y sincronizar el tablero
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

1. Código de contraseña de ocho dígitos.
2. Código de set para identificar una impresión concreta.
3. OCR del nombre normalizado, primero contra el deck activo.
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

Las primeras versiones usarán estas zonas como guía visual y destinos elegidos manualmente. La detección automática de movimientos queda para después.

## Permisos

| Nivel | Rol | Alcance |
|---|---|---|
| Cuenta | Administrador | Privilegios administrativos globales. No se otorga desde el registro público. |
| Sala | Jugador | Crea o participa en un duelo y registra acciones de su lado. |
| Sala | Espectador | Lectura del estado e historial de una sala habilitada para espectadores. Pendiente de implementación. |

El árbitro o juez será un permiso de sala futuro, con acciones explícitas y limitadas; no debe ser un administrador global.

## Criterios de aceptación para el MVP completo

- Dos jugadores autenticados pueden entrar a una misma sala mediante código.
- El tablero real refleja LP, turno, fase y eventos persistidos.
- Los cambios llegan a ambas sesiones sin recargar.
- Un teléfono autorizado se vincula con QR temporal que expira.
- El sistema detecta cuatro marcadores y superpone las zonas correctamente.
- Una captura propone una carta del deck activo, el usuario la confirma y se registra en la zona elegida.
- Las impresiones de idiomas, rarezas o artes diferentes no duplican la carta en la lógica del deck.
- El historial muestra actor, momento, origen de dispositivo y carta asociada.
- Las pérdidas de conexión, cámara o calibración se muestran como error y no producen cambios parciales.

## Fuera de alcance inicial

- Detección continua y autónoma de todos los movimientos.
- Identificación confiable de cartas boca abajo.
- Aplicación completa de reglas, efectos y cadenas.
- Chat, replay, rangos y estadísticas competitivas avanzadas.
- Aplicación móvil nativa; la primera implementación será web/PWA.

## Orden de implementación restante

1. Tablero real en `duel/[id]` sobre la API existente.
2. WebSockets, reconexión y permisos de sala.
3. Emparejamiento QR y ruta móvil.
4. Cámara trasera, marcadores y calibración.
5. Captura puntual, reconocimiento y confirmación.
6. Evolución a propuestas de movimiento entre fotogramas y validaciones de reglas.
