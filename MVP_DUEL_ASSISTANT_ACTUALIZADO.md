# Duel Assistant - MVP actualizado

**Objetivo:** asistir un duelo fisico de Yu-Gi-Oh! desde una PC mientras uno o dos celulares funcionan como camaras vinculadas. El sistema debe reflejar en tiempo real los eventos confirmados por los jugadores, sin intentar automatizar por completo el arbitraje del juego.

## Resultado del MVP

Un jugador puede:

1. Iniciar sesion en la PC con su cuenta real.
2. Ver sus decks y crear o unirse a una sala mediante un codigo.
3. Abrir el tablero compartido del duelo.
4. Vincular un celular a ese duelo escaneando un codigo QR temporal.
5. Calibrar el tapete con cuatro marcadores fisicos.
6. Escanear una carta de forma puntual, seleccionar una accion y confirmar el resultado.
7. Ver de inmediato en ambas sesiones los LP, turno, fase, zonas e historial actualizados.

El MVP no pretende reconocer automaticamente todas las cartas ni aplicar todas las reglas de Yu-Gi-Oh!. Cada deteccion relevante requiere confirmacion del jugador.

## Mapa de ideas y decisiones

| Categoria | Idea | Estado |
|---|---|---|
| Requisito del MVP | PC como tablero principal y celular como camara vinculada. | Acordado |
| Requisito del MVP | Sala de duelo, autentificacion real, JWT y estado sincronizado por WebSocket. | Acordado |
| Requisito del MVP | Emparejar el celular con un QR temporal creado desde el duelo. | Acordado |
| Requisito del MVP | Calibrar el tapete con cuatro marcadores fiduciarios y superponer las zonas. | Acordado |
| Requisito del MVP | Escaneo puntual guiado por una accion elegida y confirmada por el jugador. | Acordado |
| Decision posterior | Construir/seleccionar el deck antes del duelo para restringir las cartas candidatas del escaneo. | Acordado |
| Decision posterior | Separar la carta de juego de sus impresiones fisicas: idioma, arte, edicion y rareza. | Acordado |
| Decision posterior | Administrador como privilegio global; jugador y espectador como participaciones por sala. | Acordado |
| Idea futura | Detectar automaticamente todos los movimientos y zonas del tapete en video continuo. | Posterior al MVP |
| Idea futura | Rol de arbitro o juez para resolver disputas dentro de una sala. | Posterior al MVP |
| Idea futura | Validar de forma completa reglas, cadenas y efectos de Yu-Gi-Oh!. | Posterior al MVP |

Las decisiones posteriores se integran al MVP porque mejoran directamente la precision y velocidad del escaneo. Las ideas futuras no bloquean el primer lanzamiento.

## Principios de diseno

- La PC es la interfaz principal para administrar el duelo.
- El celular es un dispositivo companero para usar la camara, no una sesion aislada de juego.
- El backend es la fuente de verdad: valida permisos, guarda eventos y publica cambios.
- El frontend envia intenciones; no debe ser la autoridad de reglas ni del estado.
- Las detecciones de vision son propuestas con nivel de confianza, nunca cambios definitivos sin confirmacion.
- La calibracion del tapete, la identificacion de la carta y la validacion de la accion son problemas separados.
- El deck seleccionado limita las candidatas de reconocimiento; el catalogo completo solo se usa como respaldo.
- La identidad de juego de una carta es independiente de la impresion fisica que use el jugador.

## Roles y acceso

Los permisos se separan en dos niveles:

| Nivel | Rol | Alcance |
|---|---|---|
| Cuenta | Administrador | Gestiona funciones administrativas de toda la aplicacion. No puede obtenerse durante el registro publico. |
| Sala | Jugador | Crea o se une a un duelo como participante y puede ejecutar acciones de su lado del tablero. Es el rol inicial de toda cuenta nueva. |
| Sala | Espectador | Solo puede ver el estado y el historial publico del duelo. Existe unicamente tras recibir invitacion o unirse a una sala que permita espectadores. |

Una misma cuenta puede ser jugador en un duelo y espectador en otro. Por eso `espectador` no debe almacenarse como un rol global permanente del perfil.

El rol de arbitro o juez se pospone. Cuando se implemente, tambien debe ser un permiso de sala concedido por sus participantes, con acciones delimitadas como pausar el duelo, revisar eventos y registrar una resolucion; no debe modificar libremente el estado ni otorgar privilegios de administrador.

## Experiencia de usuario

### 1. Autenticacion y sala

El usuario inicia sesion en el frontend con el backend real. El JWT se guarda de forma segura y las rutas privadas requieren una sesion valida.

Desde el inicio puede:

- Crear una sala de duelo.
- Unirse con un codigo de sala.
- Seleccionar un deck.
- Abrir un duelo existente.

La ruta de duelo muestra tablero, LP, jugador activo, fase, historial y el estado de conexion en tiempo real.

### 2. Deck antes del duelo

Antes de crear la sala, el jugador construye su deck usando el catalogo de cartas. El buscador consulta primero la base local; cuando una carta no existe, el backend la obtiene de YGOProDeck y la guarda para reutilizarla.

El jugador selecciona su deck al iniciar el duelo. Entonces el escaner prioriza las cartas de ese Main Deck, Extra Deck y Side Deck, en lugar de buscar entre todo el catalogo de Yu-Gi-Oh!. Esto reduce la latencia y las coincidencias incorrectas.

El deck conserva:

- Carta de juego y cantidad disponible.
- Seccion: Main Deck, Extra Deck o Side Deck.
- Impresion fisica preferida de forma opcional.

Seleccionar una impresion no cambia la identidad de juego de la carta ni impide usar otras reimpresiones equivalentes durante un duelo casual.

### 3. Vincular celular

En la PC, dentro de un duelo, el jugador pulsa **Vincular camara**. El backend genera un token de emparejamiento de un solo uso, con expiracion corta y asociado al usuario y al duelo.

La PC muestra un codigo QR que abre la ruta movil:

```text
/scanner?pairing_token=...
```

El celular:

1. Abre la ruta de escaneo.
2. Valida el token de emparejamiento.
3. Solicita permiso para la camara trasera con `getUserMedia`.
4. Se conecta por WebSocket como dispositivo vinculado al duelo.
5. Muestra una interfaz exclusiva de camara y confirmacion, sin el tablero completo.

Un token de emparejamiento no sustituye a la autorizacion del duelo: el backend debe comprobar que el propietario del celular es participante autorizado.

### 4. Calibrar tapete

Antes de escanear cartas, la camara debe reconocer un marco fisico de cuatro marcadores colocados alrededor del tapete.

```text
[Marcador superior izquierdo]             [Marcador superior derecho]

                 Tapete de juego

[Marcador inferior izquierdo]             [Marcador inferior derecho]
```

Se recomiendan marcadores fiduciarios **ArUco** o **AprilTags** impresos, no post-its de colores. Los colores son sensibles a iluminacion, sombras, reflejos, fondo y balance de blancos; los marcadores codificados proporcionan identidad, posicion y orientacion confiables.

Los cuatro marcadores se colocan fuera de las zonas de cartas, idealmente en un marco impreso ligeramente mayor que el tapete. Cada marcador usa un identificador fijo.

Flujo:

1. El usuario selecciona **Calibrar tablero**.
2. La camara informa cuantos marcadores reconoce, por ejemplo, `3 de 4 detectados`.
3. Al detectar los cuatro, se calcula una transformacion de perspectiva u homografia.
4. La app dibuja encima del video las zonas virtuales del tablero.
5. El usuario confirma que los recuadros coinciden con el tapete real.
6. La sesion conserva la calibracion mientras la camara no se mueva.

Si faltan marcadores o la camara cambia de posicion, el escaneo se pausa y se solicita recalibrar.

### 5. Escaneo puntual con confirmacion

El primer modo funcional sera manualmente asistido, no continuo. Antes de capturar, el usuario elige la intencion:

- Agregar a cartas desterradas.
- Enviar al cementerio.
- Invocar en una zona de monstruos.
- Colocar en una zona de magia/trampa.
- Mover al extra deck.
- Agregar a la mano.

El flujo es:

```text
Elegir accion y zona
  -> Encadrar la carta en la guia
  -> Capturar una imagen
  -> Corregir perspectiva y reconocer texto
  -> Buscar coincidencias en cartas locales
  -> Mostrar carta sugerida y confianza
  -> Confirmar, corregir o cancelar
  -> Guardar evento y actualizar el duelo por WebSocket
```

La interfaz movil debe ofrecer botones grandes: **Confirmar**, **Corregir**, **Cancelar**, **Pausar camara** y **Recalibrar**.

## Arquitectura tecnica

```text
PC /duel/{id}
  -> REST: crear, consultar y administrar duelo
  -> WebSocket: recibir estado y eventos
  -> QR de emparejamiento

Celular /scanner
  -> getUserMedia: camara trasera
  -> deteccion de marcadores y guia visual
  -> REST/WebSocket: enviar captura o propuesta de accion

Backend FastAPI
  -> autenticar y autorizar
  -> identificar carta
  -> validar accion
  -> persistir DuelEvent
  -> publicar cambios del duelo

PostgreSQL
  -> jugadores, decks, duelos, cartas y eventos
```

No se debe transmitir video completo al servidor en el MVP. Se envia una captura al pulsar escanear, o fotogramas reducidos y espaciados solo cuando haya una carta estable dentro de la guia. Esto reduce consumo de datos, bateria, carga de procesamiento y latencia.

## Estado y eventos

El backend mantiene el estado canonico del duelo. Cada cambio debe convertirse en un evento persistido, por ejemplo:

```json
{
  "type": "card_moved",
  "duel_id": 42,
  "actor_id": 7,
  "card_id": 46986414,
  "from_zone": "monster_zone_2",
  "to_zone": "graveyard",
  "source": "mobile_scan",
  "confidence": 0.91,
  "confirmed_by_user": true
}
```

El servidor valida que el actor pertenezca al duelo y que pueda realizar la accion. Inicialmente puede aceptar acciones semimanuales; el motor de reglas endurecera estas validaciones en fases posteriores.

Los clientes deben recibir eventos y aplicar el nuevo estado desde el servidor, no calcular cada uno una version propia del duelo.

## Reconocimiento de cartas e impresiones fisicas

El reconocimiento se implementa gradualmente:

1. Detectar que una carta esta dentro del marco de captura.
2. Recortar la carta y corregir perspectiva.
3. Intentar leer el codigo de contraseña de ocho digitos y, cuando sea visible, el codigo de set.
4. Ejecutar OCR sobre el nombre.
5. Normalizar el texto y buscarlo primero entre las cartas del deck activo.
6. Mostrar la coincidencia principal y alternativas si la confianza es baja.
7. Requerir confirmacion del usuario.

La busqueda local evita depender de la API externa durante cada escaneo. Cuando el OCR no sea suficiente, se pueden incorporar caracteristicas visuales de la ilustracion como apoyo, no como unico criterio.

### Carta de juego e impresion

La informacion se separa en dos niveles:

| Nivel | Contenido | Uso |
|---|---|---|
| Carta canonica | Nombre base, efecto, tipo, atributo, nivel, ATK y DEF. | Deck, estado y reglas del duelo. |
| Impresion fisica | Idioma, nombre localizado, arte, rareza, codigo de set e imagen. | Reconocimiento y representacion visual. |

Por ejemplo, `Dark Magician` y `Mago Oscuro` se asocian con una misma carta canonica. Un jugador puede tener reimpresiones en ingles y espanol, con rarezas o artes distintas, sin crear copias distintas para la logica del deck.

El codigo de contraseña identifica normalmente la carta sin depender del idioma o rareza. El codigo de set permite identificar una impresion concreta. El OCR del nombre consulta una tabla de nombres localizados y alias; ATK, DEF, nivel, tipo y atributo sirven para desambiguar. La ilustracion es un apoyo final debido a reflejos, fundas y artes alternativos.

El tablero ofrece estas opciones de presentacion:

- Mostrar la impresion detectada.
- Mostrar la carta en el idioma preferido por el usuario.
- Mostrar nombre en espanol e ingles.

En formatos con diferencias TCG/OCG, erratas o restricciones, el duelo debe guardar el formato. Para el MVP, la legalidad puede ser una advertencia y el modo casual debe permitir continuar.

## Zonas iniciales

Tras normalizar el tablero a una cuadrícula virtual, se definen las zonas como rectangulos relativos al marco calibrado:

- Main Monster Zones (cinco por jugador).
- Spell & Trap Zones (cinco por jugador).
- Extra Monster Zones.
- Field Spell Zone.
- Graveyard.
- Extra Deck.
- Main Deck.
- Hand.
- Removed Cards / Banish Pile.

La primera version solo usa estas zonas para mostrar la guia y permitir que el usuario seleccione destino. La deteccion automatica de movimientos entre zonas se reserva para una fase posterior.

## Alcance fuera del MVP

- Deteccion continua y autonoma de todas las cartas del tablero.
- Identificacion fiable de cartas boca abajo.
- Deteccion de cambios mientras hay manos, dados, fichas u objetos sobre el tapete.
- Aplicacion completa de reglas, cadenas y efectos de todas las cartas.
- Chat, espectadores, replay y rangos.
- Soporte multiplataforma nativo fuera del navegador/PWA.

## Evolucion posterior

### Fase A: Integracion real

- Conectar login, JWT y proteccion de rutas al backend.
- Consumir decks reales, con cartas locales importadas desde YGOProDeck.
- Guardar Main Deck, Extra Deck, Side Deck y cantidades.
- Crear/unirse a salas y cargar estado persistido.
- Implementar WebSocket de duelo, reconexion y sincronizacion.

### Fase B: Dispositivo movil

- Ruta `/scanner`.
- Emparejamiento por QR temporal.
- Camara trasera y liberacion correcta al cerrar.
- Indicadores de permisos, conexion y bateria.

### Fase C: Calibracion y captura puntual

- Generar e imprimir marcadores ArUco o AprilTags.
- Detectar los cuatro marcadores con OpenCV.
- Calcular homografia y dibujar zonas superpuestas.
- Capturar, reconocer y confirmar cartas.
- Persistir los eventos de escaneo.

### Fase D: Asistencia avanzada

- Detectar cartas que aparecen, desaparecen o cambian de zona entre fotogramas.
- Proponer movimientos con nivel de confianza.
- Mantener confirmacion humana para evitar falsos positivos.
- Integrar validaciones progresivas del motor de reglas.

## Criterios de aceptacion del MVP

- Dos jugadores autenticados pueden entrar a la misma sala con codigo.
- El cambio de LP, turno, fase o evento aparece en ambas sesiones sin recargar.
- Un celular autorizado se vincula a un duelo mediante QR que expira.
- La aplicacion detecta cuatro marcadores y dibuja correctamente las zonas sobre el tapete.
- El usuario puede capturar una carta, confirmar una coincidencia y registrarla en una zona elegida.
- El escaneo prioriza las cartas del deck activo y reconoce nombres en espanol o ingles como una misma carta de juego.
- Una impresion con arte o rareza diferente puede mostrarse como tal sin duplicar la carta en la logica del deck.
- El historial conserva quien realizo la accion, cuando, desde que dispositivo y con que carta.
- Si se pierde la camara, WebSocket o calibracion, la interfaz muestra el error y no registra cambios incompletos.

## Seguridad y operacion

- No incluir contrasenas, JWT ni credenciales de base de datos en documentacion ni en el repositorio.
- Rotar cualquier credencial que haya sido expuesta.
- Usar variables de entorno y un archivo `.env` no versionado.
- Aplicar migraciones con Alembic en lugar de depender de `create_all` para evolucionar el esquema.
- Limitar tamaño, frecuencia y tipo de las imagenes enviadas desde el celular.
- Eliminar capturas temporales despues del reconocimiento salvo que el usuario acepte guardarlas como evidencia.
