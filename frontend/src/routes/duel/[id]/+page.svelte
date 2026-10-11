<script lang="ts">
  import { onMount } from 'svelte';
  import QRCode from 'qrcode';
  import { slotsForZone } from '$lib/config/board';
  import { page } from '$app/stores';
  import { apiFetch, connectDuelWebSocket, requireAuthenticatedUser } from '$lib/services/api';

  interface Player {
    id: number;
    username: string;
  }

  interface DuelEvent {
    id: number;
    event_type: string;
    payload: Record<string, any> | null;
    actor_player_id: number | null;
    actor_username: string | null;
    source_device: 'web' | 'camera';
    card_id: number | null;
    duel_card_id: number | null;
    source_zone: string | null;
    target_zone: string | null;
    created_at: string;
  }

  interface DeckCardChoice {
    card_id: number;
    section: 'main' | 'extra' | 'side';
    preferred_print_id: number | null;
    card: { name: string };
  }

  interface DuelCard {
    id: number;
    card_id: number | null;
    card_name: string;
    player_id: number;
    player_username: string;
    zone: string;
    position: number | null;
    face_down: boolean;
    hidden: boolean;
  }

  interface DuelSpectator {
    player_id: number;
    username: string;
    invited_by_id: number;
    created_at: string;
  }

  interface Duel {
    id: number;
    duel_code: string;
    name: string | null;
    player1_id: number;
    player2_id: number | null;
    player1_deck_id: number | null;
    player2_deck_id: number | null;
    player1_username: string;
    player2_username: string | null;
    player1_lp: number;
    player2_lp: number;
    status: string;
    turn: number;
    current_phase: string;
    current_player: number;
    winner_id: number | null;
    events: DuelEvent[];
    revision: number;
    viewer_role: 'player' | 'spectator';
  }

  let duelId = $page.params.id;
  let player: Player | null = null;
  let duel: Duel | null = null;
  let isLoading = true;
  let error = '';
  let finished = false;
  let connectionStatus: 'connecting' | 'connected' | 'disconnected' = 'connecting';
  let logs: { turn: number; text: string }[] = [];
  let lastRevision = 0;
  let spectators: DuelSpectator[] = [];
  let spectatorUsername = '';
  let spectatorMessage = '';
  let spectatorError = '';
  let boardCards: DuelCard[] = [];
  let deckChoices: DeckCardChoice[] = [];
  let selectedCard = '';
  let selectedZone = 'monster_zone';
  let selectedPosition = '';
  let selectedFaceDown = false;
  let boardMessage = '';
  let boardError = '';
  let cameraPairingQr = '';
  let cameraPairingUrl = '';
  let cameraPairingExpiry = '';
  let cameraPairingError = '';
  let actionsOpen = false;
  let appVersion = '';

  const duelZones = [
    { value: 'main_deck', label: 'Deck principal' },
    { value: 'extra_deck', label: 'Deck extra' },
    { value: 'side_deck', label: 'Side deck' },
    { value: 'hand', label: 'Mano' },
    { value: 'monster_zone', label: 'Zona de monstruos' },
    { value: 'spell_trap_zone', label: 'Mágicas y trampas' },
    { value: 'field_spell', label: 'Campo' },
    { value: 'pendulum', label: 'Péndulo' },
    { value: 'extra_monster', label: 'Monstruo extra' },
    { value: 'graveyard', label: 'Cementerio' },
    { value: 'banished', label: 'Destierro' }
  ];

  const phases = [
    'DRAW PHASE',
    'STANDBY PHASE',
    'MAIN PHASE 1',
    'BATTLE PHASE',
    'MAIN PHASE 2',
    'END PHASE'
  ];

  $: isPlayer1 = duel && player ? duel.player1_id === player.id : true;
  $: isPlayer = duel && player ? duel.player1_id === player.id || duel.player2_id === player.id : false;
  $: myUsername = player?.username || 'Tú';
  $: opponentUsername = (isPlayer1 ? duel?.player2_username : duel?.player1_username) || 'Oponente';
  $: myLp = duel ? (isPlayer1 ? duel.player1_lp : duel.player2_lp) : 8000;
  $: opponentLp = duel ? (isPlayer1 ? duel.player2_lp : duel.player1_lp) : 8000;
  $: firstPlayerLp = duel ? (isPlayer ? myLp : duel.player1_lp) : 8000;
  $: secondPlayerLp = duel ? (isPlayer ? opponentLp : duel.player2_lp) : 8000;
  $: zoneNeedsPosition = ['monster_zone', 'spell_trap_zone', 'extra_monster', 'pendulum'].includes(selectedZone);
  $: currentPhase = duel?.current_phase ? duel.current_phase.replaceAll('_', ' ') : 'DRAW PHASE';
  $: turn = duel?.turn || 1;

  onMount(() => {
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let pingTimer: ReturnType<typeof setInterval> | undefined;
    let disposed = false;

    function connect() {
      if (disposed) return;
      connectionStatus = 'connecting';

      try {
        socket = connectDuelWebSocket(duelId);
      } catch {
        scheduleReconnect();
        return;
      }

      socket.addEventListener('open', () => {
        connectionStatus = 'connected';
        if (pingTimer) clearInterval(pingTimer);
        pingTimer = setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ action: 'PING' }));
          }
        }, 25000);
      });

      socket.addEventListener('message', (message: MessageEvent<string>) => {
        try {
          const update = JSON.parse(message.data);
          const incomingRevision = Number(update.revision ?? update.duel?.revision);
          if (update.type === 'DUEL_STATE' && update.duel) {
            if (!Number.isFinite(incomingRevision) || incomingRevision < lastRevision) return;
            applyDuelSnapshot(update.duel as Duel, incomingRevision);
          } else if (update.type === 'DUEL_UPDATED' && update.duel) {
            if (!Number.isFinite(incomingRevision) || incomingRevision <= lastRevision) return;
            applyDuelSnapshot(update.duel as Duel, incomingRevision);
          } else if (update.type === 'DUEL_EVENT' && update.event) {
            if (!Number.isFinite(incomingRevision) || incomingRevision <= lastRevision) return;
            if (update.duel) {
              applyDuelSnapshot(update.duel as Duel, incomingRevision);
            } else {
              lastRevision = incomingRevision;
            }

            const duelEvent = update.event as DuelEvent;
            logs = [formatDuelEvent(duelEvent, duel), ...logs];
            if (duelEvent.event_type.startsWith('CARD_')) void loadBoardCards();
          }
        } catch {}
      });

      socket.addEventListener('close', () => {
        connectionStatus = 'disconnected';
        if (pingTimer) clearInterval(pingTimer);
        scheduleReconnect();
      });

      socket.addEventListener('error', () => socket?.close());
    }

    function scheduleReconnect() {
      if (disposed || retryTimer) return;
      connectionStatus = 'disconnected';
      retryTimer = setTimeout(() => {
        retryTimer = undefined;
        connect();
      }, 2500);
    }

    async function initialize() {
      player = await requireAuthenticatedUser<Player>();
      if (!player || disposed) return;
      await loadDuel();
      isLoading = false;
      if (!error) {
        await loadBoardCards();
        try {
          const versionResponse = await fetch('/_app/version.json');
          if (versionResponse.ok) appVersion = String((await versionResponse.json()).version || '').slice(0, 8);
        } catch {}
        if (isPlayer) await Promise.all([loadSpectators(), loadDeckChoices()]);
        connect();
      }
    }

    void initialize();

    return () => {
      disposed = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (pingTimer) clearInterval(pingTimer);
      socket?.close();
    };
  });

  function applyDuelSnapshot(updatedDuel: Duel, revision: number, restoreHistory = false) {
    const previousDuel = duel;
    duel = updatedDuel;
    lastRevision = revision;
    finished = updatedDuel.status === 'finished';

    if (restoreHistory) {
      logs = [...updatedDuel.events]
        .sort((left, right) => right.created_at.localeCompare(left.created_at))
        .map((event) => formatDuelEvent(event, updatedDuel));
    } else if (previousDuel && previousDuel.current_phase !== updatedDuel.current_phase) {
      logs = [{ turn: updatedDuel.turn, text: `Fase: ${updatedDuel.current_phase.replaceAll('_', ' ')}` }, ...logs];
    } else if (previousDuel && previousDuel.turn !== updatedDuel.turn) {
      logs = [{ turn: updatedDuel.turn, text: `Turno ${updatedDuel.turn}` }, ...logs];
    }
  }

  function formatDuelEvent(duelEvent: DuelEvent, currentDuel: Duel) {
    const payload = duelEvent.payload || {};
    const targetPlayerId = Number(payload.target_player_id);
    const targetName = targetPlayerId === currentDuel.player1_id
      ? currentDuel.player1_username
      : targetPlayerId === currentDuel.player2_id
        ? currentDuel.player2_username || 'Oponente'
        : String(payload.target || 'duelo');
    const eventText = duelEvent.event_type === 'LP_CHANGE'
      ? `${targetName} ${Number(payload.delta) > 0 ? '+' : ''}${payload.delta} LP (${payload.new_lp})`
      : duelEvent.event_type.startsWith('CARD_')
        ? `${duelEvent.actor_username || 'Jugador'}: ${zoneLabel(duelEvent.source_zone)} → ${zoneLabel(duelEvent.target_zone)}`
        : `Evento: ${duelEvent.event_type.replaceAll('_', ' ')}`;

    return { turn: currentDuel.turn, text: eventText };
  }

  async function loadDuel() {
    try {
      const res = await apiFetch(`/api/duels/${duelId}`);
      if (!res.ok) {
        const p = await res.json();
        throw new Error(p.detail || 'No se pudo cargar el duelo.');
      }
      duel = await res.json();
      lastRevision = duel.revision;
      if (duel?.status === 'finished') {
        finished = true;
      }
      if (duel) {
        logs = [...duel.events]
          .sort((left, right) => right.created_at.localeCompare(left.created_at))
          .map((event) => formatDuelEvent(event, duel));
        if (logs.length === 0) {
          logs = [{ turn: duel.turn, text: `Duelo iniciado: ${duel.player1_username} vs ${duel.player2_username || 'Oponente'}` }];
        }
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Error al cargar el duelo.';
    }
  }

  async function loadSpectators() {
    const response = await apiFetch(`/api/duels/${duelId}/spectators`);
    if (response.ok) spectators = await response.json();
  }

  async function loadBoardCards() {
    const response = await apiFetch(`/api/duels/${duelId}/cards`);
    if (response.ok) boardCards = await response.json();
  }

  async function loadDeckChoices() {
    if (!duel || !player) return;
    const deckId = duel.player1_id === player.id ? duel.player1_deck_id : duel.player2_deck_id;
    if (!deckId) return;
    const response = await apiFetch(`/api/decks/${deckId}`);
    if (response.ok) deckChoices = (await response.json()).card_entries;
  }

  function zoneLabel(zone: string | null) {
    return duelZones.find((item) => item.value === zone)?.label || zone || 'desconocida';
  }

  function fieldOwnerId(own: boolean): number | null {
    if (!duel || !player) return null;
    if (isPlayer) return own ? player.id : isPlayer1 ? duel.player2_id : duel.player1_id;
    return own ? duel.player1_id : duel.player2_id;
  }

  function cardAt(zone: string, position: number | null, ownerId: number | null, anyOwner = false): DuelCard | undefined {
    return boardCards.find((card) =>
      (anyOwner || card.player_id === ownerId) &&
      card.zone === zone &&
      (position === null || card.position === position));
  }

  function countAt(zone: string, ownerId: number | null): number {
    if (ownerId == null) return 0;
    return boardCards.filter((card) => card.player_id === ownerId && card.zone === zone).length;
  }

  function displayCardName(card: DuelCard): string {
    if (card.face_down) return 'Boca abajo';
    if (card.hidden) return 'Carta oculta';
    return card.card_name;
  }

  async function registerBoardCard(event: SubmitEvent) {
    event.preventDefault();
    boardMessage = '';
    boardError = '';
    const [kind, rawId] = selectedCard.split(':');
    const position = selectedPosition === '' ? null : Number(selectedPosition) - 1;
    let response: Response;

    if (kind === 'instance') {
      response = await apiFetch(`/api/duels/${duelId}/cards/${rawId}`, {
        method: 'PUT',
        body: JSON.stringify({ zone: selectedZone, position, face_down: selectedFaceDown, source_device: 'web' })
      });
    } else {
      const deckCard = deckChoices.find((item) => item.card_id === Number(rawId));
      if (!deckCard) return;
      const sourceZone = { main: 'main_deck', extra: 'extra_deck', side: 'side_deck' }[deckCard.section];
      response = await apiFetch(`/api/duels/${duelId}/cards`, {
        method: 'POST',
        body: JSON.stringify({
          card_id: deckCard.card_id,
          source_zone: sourceZone,
          zone: selectedZone,
          position,
          face_down: selectedFaceDown,
          preferred_print_id: deckCard.preferred_print_id,
          source_device: 'web'
        })
      });
    }

    const result = await response.json();
    if (!response.ok) {
      boardError = result.detail || 'No se pudo guardar el movimiento.';
      return;
    }
    boardMessage = 'Movimiento guardado.';
    selectedCard = '';
    selectedPosition = '';
    selectedFaceDown = false;
    await loadBoardCards();
  }

  async function inviteSpectator(event: SubmitEvent) {
    event.preventDefault();
    spectatorMessage = '';
    spectatorError = '';
    const response = await apiFetch(`/api/duels/${duelId}/spectators`, {
      method: 'POST',
      body: JSON.stringify({ username: spectatorUsername.trim() })
    });
    const result = await response.json();
    if (!response.ok) {
      spectatorError = result.detail || 'No se pudo invitar a esa cuenta.';
      return;
    }
    spectators = [...spectators, result];
    spectatorUsername = '';
    spectatorMessage = `Invitación enviada a ${result.username}.`;
  }

  async function revokeSpectator(spectator: DuelSpectator) {
    const response = await apiFetch(`/api/duels/${duelId}/spectators/${spectator.player_id}`, {
      method: 'DELETE'
    });
    if (!response.ok) {
      spectatorError = 'No se pudo revocar el acceso.';
      return;
    }
    spectators = spectators.filter((item) => item.player_id !== spectator.player_id);
    spectatorMessage = `Acceso de ${spectator.username} revocado.`;
  }

  async function createCameraPairing() {
    cameraPairingError = '';
    try {
      const response = await apiFetch(`/api/duels/${duelId}/camera-pairings`, { method: 'POST' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'No se pudo crear el QR.');
      cameraPairingUrl = new URL(`/scanner?pairing_token=${encodeURIComponent(result.pairing_token)}`, window.location.origin).toString();
      cameraPairingExpiry = new Date(result.expires_at).toLocaleTimeString();
      cameraPairingQr = await QRCode.toDataURL(cameraPairingUrl, {
        errorCorrectionLevel: 'H',
        margin: 2,
        width: 320
      });
    } catch (cause) {
      cameraPairingError = cause instanceof Error ? cause.message : 'No se pudo crear el QR.';
    }
  }

  async function changeLp(delta: number, target: 'me' | 'opponent') {
    if (!duel) return;
    const isTargetP1 = target === 'me' ? isPlayer1 : !isPlayer1;
    const currentVal = isTargetP1 ? duel.player1_lp : duel.player2_lp;
    const newLp = Math.max(0, currentVal + delta);

    const updateBody = isTargetP1 ? { player1_lp: newLp } : { player2_lp: newLp };

    if (isTargetP1) duel.player1_lp = newLp;
    else duel.player2_lp = newLp;
    duel = { ...duel };

    const targetName = target === 'me' ? myUsername : opponentUsername;
    try {
      await apiFetch(`/api/duels/${duelId}`, {
        method: 'PUT',
        body: JSON.stringify(updateBody)
      });
      await apiFetch(`/api/duels/${duelId}/events`, {
        method: 'POST',
        body: JSON.stringify({
          event_type: 'LP_CHANGE',
          payload: {
            target: targetName,
            target_player_id: isTargetP1 ? duel.player1_id : duel.player2_id,
            delta,
            new_lp: newLp
          }
        })
      });
    } catch {}
  }

  async function advancePhase() {
    if (!duel) return;
    const currentIdx = phases.indexOf(currentPhase);
    let nextIdx = (currentIdx + 1) % phases.length;
    let nextTurn = duel.turn;
    if (nextIdx === 0) {
      nextTurn += 1;
    }
    const newPhase = phases[nextIdx];

    duel.current_phase = newPhase.replaceAll(' ', '_');
    duel.turn = nextTurn;
    duel = { ...duel };

    logs = [{ turn: nextTurn, text: `Fase: ${newPhase}` }, ...logs];

    try {
      await apiFetch(`/api/duels/${duelId}`, {
        method: 'PUT',
        body: JSON.stringify({
          current_phase: duel.current_phase,
          turn: nextTurn
        })
      });
    } catch {}
  }

  async function endTurn() {
    if (!duel) return;
    const nextTurn = duel.turn + 1;
    duel.turn = nextTurn;
    duel.current_phase = 'DRAW_PHASE';
    duel = { ...duel };

    logs = [{ turn: nextTurn, text: `Fin de turno → Turno ${nextTurn} (DRAW PHASE)` }, ...logs];

    try {
      await apiFetch(`/api/duels/${duelId}`, {
        method: 'PUT',
        body: JSON.stringify({
          turn: nextTurn,
          current_phase: 'DRAW_PHASE'
        })
      });
    } catch {}
  }

  async function concedeDuel() {
    if (!duel || !confirm('¿Estás seguro de conceder la partida?')) return;
    finished = true;
    try {
      await apiFetch(`/api/duels/${duelId}`, {
        method: 'PUT',
        body: JSON.stringify({
          status: 'finished'
        })
      });
    } catch {}
  }
</script>

<svelte:head>
  <title>Duelo {duel?.duel_code || duelId} | Duel Assistant</title>
</svelte:head>

{#if isLoading}
  <div class="loading-screen">
    <p>Cargando mesa de duelo...</p>
  </div>
{:else if error}
  <div class="error-screen">
    <h2>Error al cargar la mesa</h2>
    <p>{error}</p>
    <a href="/">← Volver al inicio</a>
  </div>
{:else if duel}
  <div class="duel-page">
    <header class="duel-top">
      <a class="duel-brand" href="/">DA <span>DUEL ASSISTANT</span></a>
      <div class="turn">
        <small>TURNO {turn}</small>
        <strong>{currentPhase}</strong>
        {#if isPlayer}
          <button class="phase-btn" on:click={advancePhase} title="Avanzar a la siguiente fase">
            Avanzar fase ↷
          </button>
        {:else}
          <small class="spectator-banner">VISTA DE ESPECTADOR · SOLO LECTURA</small>
        {/if}
        <div class="connection-status" class:online={connectionStatus === 'connected'} aria-live="polite">
          <span aria-hidden="true"></span>
          {connectionStatus === 'connected' ? 'En vivo' : connectionStatus === 'connecting' ? 'Conectando' : 'Reconectando'}
        </div>
      </div>
      <a href="/" class="exit">Salir al inicio ×</a>
    </header>

    <section class="scoreboard">
      <!-- JUGADOR ACTUAL -->
      <div class="fighter me">
        <small>{isPlayer ? 'TU LP' : duel.player1_username}</small>
        <strong>{firstPlayerLp}</strong>
        <span>{isPlayer ? myUsername : duel.player1_username}</span>
        {#if isPlayer}
          <div class="lp-actions">
            <button on:click={() => changeLp(-1000, 'me')}>−1000</button>
            <button on:click={() => changeLp(-500, 'me')}>−500</button>
            <button on:click={() => changeLp(-100, 'me')}>−100</button>
            <button on:click={() => changeLp(100, 'me')}>+100</button>
            <button on:click={() => changeLp(500, 'me')}>+500</button>
            <button on:click={() => changeLp(1000, 'me')}>+1000</button>
          </div>
        {/if}
      </div>

      <div class="versus">
        VS<br />
        <small>SALA {duel.duel_code}</small>
        {#if appVersion}<small class="build-tag">build {appVersion}</small>{/if}
      </div>

      <!-- OPONENTE -->
      <div class="fighter opponent">
        <small>{isPlayer ? 'OPONENTE' : duel.player2_username || 'Oponente'}</small>
        <strong>{secondPlayerLp}</strong>
        <span>{isPlayer ? opponentUsername : duel.player2_username || 'Oponente'}</span>
        {#if isPlayer}
          <div class="lp-actions">
            <button on:click={() => changeLp(-1000, 'opponent')}>−1000</button>
            <button on:click={() => changeLp(-500, 'opponent')}>−500</button>
            <button on:click={() => changeLp(-100, 'opponent')}>−100</button>
            <button on:click={() => changeLp(100, 'opponent')}>+100</button>
            <button on:click={() => changeLp(500, 'opponent')}>+500</button>
            <button on:click={() => changeLp(1000, 'opponent')}>+1000</button>
          </div>
        {/if}
      </div>
    </section>

    <!-- TABLERO DIGITAL DE YU-GI-OH! (REGLA MAESTRA / 7 COLUMNAS) -->
    {#snippet zoneCell(cls, label, zone, position, ownerId, anyOwner = false, badge = '')}
      <div class="zone {cls}" class:occupied={position !== null && !!cardAt(zone, position, ownerId, anyOwner)}>
        {#if badge}<span class="emz-badge">{badge}</span>{/if}
        {#if position !== null && cardAt(zone, position, ownerId, anyOwner)}
          <strong class="zone-card-name">{displayCardName(cardAt(zone, position, ownerId, anyOwner))}</strong>
          <span class="zone-card-sub">{cardAt(zone, position, ownerId, anyOwner).player_username}</span>
        {:else if position === null && countAt(zone, ownerId) > 0}
          <span>{label} ({countAt(zone, ownerId)})</span>
        {:else}
          <span>{label}</span>
        {/if}
      </div>
    {/snippet}
    <section class="board">
      <!-- CAMPO OPONENTE -->
      <div class="field-side opponent-field">
        <small class="field-label">CAMPO DEL OPONENTE ({opponentUsername})</small>
        
        <!-- Fila Mágicas / Trampas y Decks Oponente -->
        <div class="ygo-grid">
          {@render zoneCell('deck-zone', 'DECK', 'main_deck', null, fieldOwnerId(false))}
          {@render zoneCell('pendulum-zone red', 'PÉNDULO (ROJO)', 'pendulum', 1, fieldOwnerId(false))}
          {@render zoneCell('spell-zone', 'MÁGICAS & TRAMPAS', 'spell_trap_zone', 3, fieldOwnerId(false))}
          {@render zoneCell('spell-zone', 'MÁGICAS & TRAMPAS', 'spell_trap_zone', 2, fieldOwnerId(false))}
          {@render zoneCell('spell-zone', 'MÁGICAS & TRAMPAS', 'spell_trap_zone', 1, fieldOwnerId(false))}
          {@render zoneCell('pendulum-zone blue', 'PÉNDULO (AZUL)', 'pendulum', 0, fieldOwnerId(false))}
          {@render zoneCell('extra-deck-zone', 'DECK EXTRA', 'extra_deck', null, fieldOwnerId(false))}
        </div>

        <!-- Fila Monstruos Oponente -->
        <div class="ygo-grid">
          {@render zoneCell('grave-zone', 'CEMENTERIO', 'graveyard', null, fieldOwnerId(false))}
          {@render zoneCell('monster-zone', 'MONSTRUO 5', 'monster_zone', 4, fieldOwnerId(false))}
          {@render zoneCell('monster-zone', 'MONSTRUO 4', 'monster_zone', 3, fieldOwnerId(false))}
          {@render zoneCell('monster-zone', 'MONSTRUO 3', 'monster_zone', 2, fieldOwnerId(false))}
          {@render zoneCell('monster-zone', 'MONSTRUO 2', 'monster_zone', 1, fieldOwnerId(false))}
          {@render zoneCell('monster-zone', 'MONSTRUO 1', 'monster_zone', 0, fieldOwnerId(false))}
          {@render zoneCell('field-spell-zone', 'CAMPO', 'field_spell', 0, fieldOwnerId(false))}
        </div>
      </div>

      <!-- ZONAS DE MONSTRUO EXTRA (COMPARTIDAS EN EL CENTRO) -->
      <div class="emz-container">
        <div class="ygo-grid">
          <div class="empty-cell"></div>
          <div class="empty-cell"></div>
          {@render zoneCell('extra-monster-zone', 'MONSTRUO EXTRA', 'extra_monster', 0, null, true, 'EMZ 1')}
          <div class="empty-cell"></div>
          {@render zoneCell('extra-monster-zone', 'MONSTRUO EXTRA', 'extra_monster', 1, null, true, 'EMZ 2')}
          <div class="empty-cell"></div>
          <div class="empty-cell"></div>
        </div>
        <div class="divider-line">
          <span>FASE ACTUAL: {currentPhase}</span>
        </div>
      </div>

      <!-- CAMPO PROPIO -->
      <div class="field-side my-field">
        <!-- Fila Monstruos Propio -->
        <div class="ygo-grid">
          {@render zoneCell('field-spell-zone', 'ZONA DEL CAMPO', 'field_spell', 0, fieldOwnerId(true))}
          {@render zoneCell('monster-zone', 'MONSTRUO 1', 'monster_zone', 0, fieldOwnerId(true))}
          {@render zoneCell('monster-zone', 'MONSTRUO 2', 'monster_zone', 1, fieldOwnerId(true))}
          {@render zoneCell('monster-zone', 'MONSTRUO 3', 'monster_zone', 2, fieldOwnerId(true))}
          {@render zoneCell('monster-zone', 'MONSTRUO 4', 'monster_zone', 3, fieldOwnerId(true))}
          {@render zoneCell('monster-zone', 'MONSTRUO 5', 'monster_zone', 4, fieldOwnerId(true))}
          {@render zoneCell('grave-zone', 'CEMENTERIO', 'graveyard', null, fieldOwnerId(true))}
        </div>

        <!-- Fila Mágicas / Trampas y Decks Propio -->
        <div class="ygo-grid">
          {@render zoneCell('extra-deck-zone', 'DECK EXTRA', 'extra_deck', null, fieldOwnerId(true))}
          {@render zoneCell('pendulum-zone blue', 'PÉNDULO (AZUL)', 'pendulum', 0, fieldOwnerId(true))}
          {@render zoneCell('spell-zone', 'MÁGICAS & TRAMPAS 2', 'spell_trap_zone', 1, fieldOwnerId(true))}
          {@render zoneCell('spell-zone', 'MÁGICAS & TRAMPAS 3', 'spell_trap_zone', 2, fieldOwnerId(true))}
          {@render zoneCell('spell-zone', 'MÁGICAS & TRAMPAS 4', 'spell_trap_zone', 3, fieldOwnerId(true))}
          {@render zoneCell('pendulum-zone red', 'PÉNDULO (ROJO)', 'pendulum', 1, fieldOwnerId(true))}
          {@render zoneCell('deck-zone', 'DECK', 'main_deck', null, fieldOwnerId(true))}
        </div>

        <!-- Barra inferior: Destierro, Escáner y Mano -->
        <div class="bottom-tools">
          <div class="zone banish-zone"><span>DESTIERRO ({countAt('banished', fieldOwnerId(true))})</span></div>
          {#if isPlayer}
            <button class="scan-button" on:click={createCameraPairing}>
              📷 Vincular Escáner
            </button>
          {/if}
          <div class="hand">
            <span>MANO ({myUsername}) ({countAt('hand', fieldOwnerId(true))})</span>
            {#each Array.from({ length: Math.min(6, countAt('hand', fieldOwnerId(true))) }) as _, i (i)}<i></i>{/each}
          </div>
        </div>

        <small class="field-label">TU CAMPO ({myUsername})</small>
      </div>
    </section>

    <section class="board-card-ledger" aria-label="Cartas registradas en zonas">
      <header>
        <div><small class="eyebrow">Estado del tablero</small><h2>Cartas en zonas</h2></div>
        <span>{boardCards.length} registradas</span>
      </header>
      {#if boardCards.length > 0}
        <div class="board-card-list">
          {#each boardCards as boardCard (boardCard.id)}
            <article>
              <strong>{boardCard.hidden ? 'Carta oculta' : boardCard.card_name}</strong>
              <span>{boardCard.player_username} · {zoneLabel(boardCard.zone)}{boardCard.position !== null ? ` ${boardCard.position + 1}` : ''}</span>
              {#if boardCard.face_down}<small>Boca abajo</small>{/if}
            </article>
          {/each}
        </div>
      {:else}
        <p class="board-empty">Todavía no hay cartas registradas fuera de los decks.</p>
      {/if}
    </section>

    <!-- PANEL DE ACCIONES Y REGISTRO EN VIVO -->
    <aside class="actions-panel" class:collapsed={!actionsOpen}>
      <button type="button" class="actions-toggle" on:click={() => (actionsOpen = !actionsOpen)} aria-expanded={actionsOpen} aria-label="Mostrar u ocultar el registro de mesa">
        <span class="toggle-title"><small class="eyebrow">Registro de Mesa</small>{#if !actionsOpen}<span class="toggle-count">{logs.length} eventos</span>{/if}</span>
        <span class="toggle-chevron" aria-hidden="true">{actionsOpen ? '▾' : '▸'}</span>
      </button>
      {#if actionsOpen}
      <div>
        <small class="eyebrow">Registro de Mesa</small>
        <h2>Acciones</h2>
      </div>
      <div class="action-log">
        {#each logs as log, idx (`log-${idx}`)}
          <p><b>T{log.turn}</b> {log.text}</p>
        {/each}
        {#if logs.length === 0}
          <p>Mesa lista. Registra cambios de LP o fases.</p>
        {/if}
      </div>
      {#if isPlayer}
        <button class="primary" on:click={endTurn}>Fin de turno <span>→</span></button>
        <button class="secondary" on:click={concedeDuel}>Conceder duelo</button>
        {#if !finished}
          {#if deckChoices.length > 0}
            <section class="board-tools">
              <small class="eyebrow">Registrar carta o movimiento</small>
              <form on:submit={registerBoardCard}>
                <label for="board-card">Carta</label>
                <select id="board-card" bind:value={selectedCard} required>
                  <option value="">Selecciona una carta</option>
                  {#each deckChoices as deckCard (`deck-${deckCard.card_id}`)}
                    <option value={`deck:${deckCard.card_id}`}>{deckCard.card.name} · {deckCard.section}</option>
                  {/each}
                  {#each boardCards.filter((card) => card.player_id === player?.id) as boardCard (`instance-${boardCard.id}`)}
                    <option value={`instance:${boardCard.id}`}>{boardCard.hidden ? 'Carta oculta' : boardCard.card_name} · {zoneLabel(boardCard.zone)}</option>
                  {/each}
                </select>
                <label for="board-zone">Zona destino</label>
                <select id="board-zone" bind:value={selectedZone}>
                  {#each duelZones as zone (zone.value)}
                    <option value={zone.value}>{zone.label}</option>
                  {/each}
                </select>
                <label for="board-position">Slot {zoneNeedsPosition ? '(requerido)' : '(opcional)'}</label>
                <select id="board-position" bind:value={selectedPosition} required={zoneNeedsPosition}>
                  {#if !zoneNeedsPosition}<option value="">Automático</option>{/if}
                  {#each Array.from({ length: slotsForZone(selectedZone) || 5 }, (_, i) => i + 1) as slot (slot)}
                    <option value={String(slot)}>{slot}</option>
                  {/each}
                </select>
                <label class="face-down-toggle"><input type="checkbox" bind:checked={selectedFaceDown} /> Boca abajo</label>
                {#if boardError}<p class="board-feedback error" role="alert">{boardError}</p>{/if}
                {#if boardMessage}<p class="board-feedback" role="status">{boardMessage}</p>{/if}
                <button class="primary" type="submit">Guardar movimiento</button>
              </form>
            </section>
          {/if}
          <section class="spectator-tools">
            <small class="eyebrow">Espectadores invitados</small>
            <form on:submit={inviteSpectator}>
              <label for="spectator-username">Cuenta</label>
              <div class="spectator-invite-row">
                <input id="spectator-username" bind:value={spectatorUsername} minlength="3" maxlength="50" required placeholder="Nombre de usuario" />
                <button type="submit" title="Invitar espectador" aria-label="Invitar espectador">＋</button>
              </div>
            </form>
            {#if spectatorError}<p class="spectator-feedback error" role="alert">{spectatorError}</p>{/if}
            {#if spectatorMessage}<p class="spectator-feedback" role="status">{spectatorMessage}</p>{/if}
            <ul>
              {#each spectators as spectator (spectator.player_id)}
                <li>
                  <span>{spectator.username}</span>
                  <button type="button" on:click={() => revokeSpectator(spectator)} title="Revocar acceso a {spectator.username}" aria-label="Revocar acceso a {spectator.username}">×</button>
                </li>
              {/each}
            </ul>
          </section>
        {/if}
      {/if}
      {/if}
    </aside>

    {#if finished}
      <div class="overlay">
        <div class="finish">
          <small class="eyebrow">Duelo terminado</small>
          <h2>Partida finalizada.</h2>
          <p>El resultado ha quedado guardado en tu historial.</p>
          <a href="/">Volver al inicio →</a>
        </div>
      </div>
    {/if}
    {#if cameraPairingQr}
      <div class="camera-pairing-backdrop" role="presentation" on:click={() => (cameraPairingQr = '')}>
        <div class="camera-pairing-dialog" role="dialog" aria-modal="true" aria-labelledby="camera-pairing-title" tabindex="-1" on:click|stopPropagation>
          <button class="camera-pairing-close" type="button" on:click={() => (cameraPairingQr = '')} aria-label="Cerrar QR">×</button>
          <small class="eyebrow">Cámara compañera</small>
          <h2 id="camera-pairing-title">Vincula este teléfono</h2>
          <img src={cameraPairingQr} alt="QR temporal para vincular la cámara a este duelo" />
          <p>Abre el escáner del teléfono y apunta a este código.</p>
          <small>El QR vence a las {cameraPairingExpiry} y solo puede usarse una vez.</small>
          <a href={cameraPairingUrl}>Abrir escáner en este dispositivo</a>
        </div>
      </div>
    {/if}
    {#if cameraPairingError}
      <div class="camera-pairing-error" role="alert">{cameraPairingError}<button type="button" on:click={() => (cameraPairingError = '')} aria-label="Cerrar">×</button></div>
    {/if}
  </div>
{/if}

<style>
  .loading-screen, .error-screen {
    min-height: 100vh;
    display: grid;
    place-content: center;
    background: #101812;
    color: #eef2e8;
    text-align: center;
    font-family: 'DM Mono', monospace;
  }
  .error-screen a { color: #d9573b; margin-top: 16px; display: inline-block; }

  .duel-page {
    min-height: 100vh;
    background: #101812;
    color: #eef2e8;
    padding: 22px 30px;
    position: relative;
  }
  .duel-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #334137;
    padding-bottom: 20px;
  }
  .duel-brand {
    font: 700 16px 'DM Mono', monospace;
    color: #e66b4e;
    text-decoration: none;
  }
  .duel-brand span {
    font-size: 10px;
    color: #b5c2b3;
    margin-left: 8px;
  }
  .turn {
    text-align: center;
  }
  .turn small, .fighter small, .board small {
    display: block;
    color: #91a092;
    font: 10px 'DM Mono', monospace;
    letter-spacing: .1em;
  }
  .turn strong {
    display: block;
    color: #f5bb68;
    font-size: 14px;
    margin-top: 4px;
    font-family: 'DM Mono', monospace;
  }
  .phase-btn {
    margin-top: 6px;
    background: #223326;
    border: 1px solid #3d5943;
    color: #a3c4a7;
    font: 10px 'DM Mono', monospace;
    padding: 3px 8px;
    cursor: pointer;
  }
  .phase-btn:hover { background: #324a37; color: #fff; }
  .connection-status {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    margin-top: 7px;
    color: #d9a441;
    font: 9px 'DM Mono', monospace;
  }
  .connection-status span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }
  .connection-status.online { color: #58c772; }
  .spectator-banner {
    margin-top: 8px;
    color: #d9a441 !important;
  }
  .exit {
    color: #91a092;
    font: 11px 'DM Mono', monospace;
    text-decoration: none;
  }
  .exit:hover { color: #d9573b; }

  .scoreboard {
    max-width: 820px;
    margin: 28px auto;
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    gap: 24px;
    align-items: center;
    text-align: center;
  }
  .fighter {
    padding: 18px;
    border: 1px solid #334137;
    background: #141f17;
  }
  .fighter strong {
    display: block;
    font: 700 clamp(36px, 6vw, 64px) 'DM Mono', monospace;
    letter-spacing: -0.05em;
    margin: 6px 0;
    color: #fff;
  }
  .fighter span {
    color: #b5c2b3;
    font-size: 14px;
  }
  .fighter.me strong {
    color: #58c772;
  }
  .fighter.opponent strong {
    color: #ff725e;
  }

  .versus {
    font: 11px 'DM Mono', monospace;
    color: #f5bb68;
  }
  .versus small {
    color: #718071;
  }

  .lp-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 4px;
    margin-top: 12px;
  }
  .lp-actions button, .secondary {
    border: 1px solid #425045;
    background: transparent;
    color: #d5dfd1;
    padding: 6px 8px;
    font: 10px 'DM Mono', monospace;
    cursor: pointer;
  }
  .lp-actions button:hover { background: #223126; color: #fff; }

  .board {
    max-width: 960px;
    margin: auto;
    border: 1px solid #334137;
    background: radial-gradient(ellipse at center, #18281d 0%, #111a13 100%);
    padding: 20px 16px;
    border-radius: 8px;
    box-shadow: 0 16px 40px rgba(0,0,0,0.5);
  }
  .board-card-ledger {
    max-width: 960px;
    margin: 12px auto 0;
    padding: 10px 0 16px;
    border-bottom: 1px solid #334137;
  }
  .board-card-ledger header { display: flex; align-items: end; justify-content: space-between; gap: 12px; }
  .board-card-ledger h2 { margin: 4px 0 0; font: 15px 'DM Mono', monospace; }
  .board-card-ledger header > span, .board-empty { color: #91a092; font: 10px 'DM Mono', monospace; }
  .board-card-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 1px 16px; margin-top: 10px; }
  .board-card-list article { display: flex; flex-direction: column; gap: 3px; border-top: 1px solid #26352a; padding: 8px 0; }
  .board-card-list strong { color: #e8eee5; font-size: 12px; }
  .board-card-list span, .board-card-list small { color: #91a092; font: 10px 'DM Mono', monospace; }
  .board-empty { margin: 10px 0 0; }
  .field-side {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .field-label {
    text-align: center;
    color: #8da090;
    font: 10px 'DM Mono', monospace;
    letter-spacing: .08em;
    margin: 4px 0;
  }
  .ygo-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 6px;
    align-items: stretch;
  }
  .empty-cell {
    visibility: hidden;
    aspect-ratio: 5.87 / 8.57;
  }
  .zone {
    aspect-ratio: 5.87 / 8.57;
    border-radius: 4px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    font: 8px 'DM Mono', monospace;
    padding: 4px 2px;
    transition: all 0.15s ease;
    user-select: none;
    box-sizing: border-box;
  }
  .zone-card-name {
    font-size: 8px;
    font-weight: 700;
    line-height: 1.25;
    word-break: break-word;
    display: -webkit-box;
    -webkit-line-clamp: 4;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .zone-card-sub { font-size: 7px; opacity: 0.85; margin-top: 2px; }
  .zone.occupied { border-style: solid; filter: brightness(1.3); }
  /* Campo */
  .field-spell-zone {
    border: 2px solid #2e7d32;
    background: rgba(46, 125, 50, 0.22);
    color: #81c784;
  }
  /* Monstruos */
  .monster-zone {
    border: 2px solid #b45309;
    background: rgba(180, 83, 9, 0.2);
    color: #fcd34d;
  }
  /* Monstruo Extra */
  .extra-monster-zone {
    border: 2px dashed #0284c7;
    background: rgba(2, 132, 199, 0.25);
    color: #7dd3fc;
  }
  .emz-badge {
    font-size: 7px;
    background: #0369a1;
    color: #fff;
    padding: 1px 4px;
    border-radius: 2px;
    margin-bottom: 2px;
  }
  /* Cementerio */
  .grave-zone {
    border: 2px solid #64748b;
    background: rgba(100, 116, 139, 0.25);
    color: #cbd5e1;
  }
  /* Extra Deck */
  .extra-deck-zone {
    border: 2px solid #94a3b8;
    background: rgba(148, 163, 184, 0.2);
    color: #e2e8f0;
  }
  /* Deck Principal */
  .deck-zone {
    border: 2px solid #92400e;
    background: linear-gradient(135deg, rgba(146, 64, 14, 0.35), rgba(77, 34, 7, 0.5));
    color: #fed7aa;
  }
  /* Mágicas y Trampas */
  .spell-zone {
    border: 2px solid #0f766e;
    background: rgba(15, 118, 110, 0.2);
    color: #5eead4;
  }
  /* Péndulo */
  .pendulum-zone.blue {
    border: 2px solid #2563eb;
    background: linear-gradient(180deg, rgba(37, 99, 235, 0.35) 0%, rgba(15, 118, 110, 0.15) 100%);
    color: #93c5fd;
  }
  .pendulum-zone.red {
    border: 2px solid #dc2626;
    background: linear-gradient(180deg, rgba(220, 38, 38, 0.35) 0%, rgba(15, 118, 110, 0.15) 100%);
    color: #fca5a5;
  }
  .pend-gem {
    font-size: 11px;
    line-height: 1;
    margin-bottom: 2px;
  }
  .blue-gem { color: #60a5fa; }
  .red-gem { color: #f87171; }

  /* EMZ container & divisor */
  .emz-container {
    margin: 8px 0;
  }
  .divider-line {
    text-align: center;
    border-top: 1px dashed #334137;
    margin-top: 8px;
    padding-top: 6px;
    color: #d9573b;
    font: 10px 'DM Mono', monospace;
    font-weight: 700;
  }

  /* Herramientas inferiores */
  .bottom-tools {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid #223326;
  }
  .banish-zone {
    border: 2px solid #78350f;
    background: rgba(120, 53, 15, 0.3);
    color: #fcd34d;
    min-height: 44px;
    padding: 4px 10px;
  }
  .scan-button {
    border: 1px solid #d9573b;
    background: #d9573b;
    color: #fff;
    padding: 8px 12px;
    font: 10px 'DM Mono', monospace;
    cursor: pointer;
  }

  .hand {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin: 18px 0 6px;
  }
  .hand span { color: #91a092; font: 10px 'DM Mono', monospace; margin-right: 7px; }
  .hand i {
    display: block;
    width: 34px;
    height: 50px;
    border: 1px solid #6d5040;
    background: linear-gradient(135deg, #714b31, #b16a3b);
    transform: rotate(-3deg);
  }
  .hand i:nth-child(odd) { transform: rotate(3deg); }

  .actions-panel {
    position: fixed;
    right: 30px;
    bottom: 25px;
    width: 255px;
    background: #f4f1e8;
    color: #17211b;
    padding: 18px;
    box-shadow: 0 10px 35px rgba(0,0,0,0.5);
    border-radius: 4px;
    z-index: 100;
    max-height: calc(100vh - 50px);
    overflow-y: auto;
  }
  .actions-panel h2 { margin: 4px 0 12px; font-size: 22px; }
  .actions-panel.collapsed { width: auto; min-width: 200px; padding: 10px 14px; }
  .actions-toggle { display: flex !important; align-items: center; justify-content: space-between; gap: 12px; width: 100% !important; background: transparent !important; border: 0 !important; padding: 4px 0 !important; cursor: pointer; }
  .actions-toggle .toggle-title { display: flex; align-items: baseline; gap: 10px; }
  .actions-toggle .toggle-count { font-size: 11px; color: #68766a; }
  .actions-toggle .toggle-chevron { font-size: 14px; color: #17211b; }
  .action-log {
    border-top: 1px solid #d5ddd2;
    border-bottom: 1px solid #d5ddd2;
    margin-bottom: 14px;
    max-height: 140px;
    overflow-y: auto;
  }
  .action-log p { font-size: 11px; color: #68766a; line-height: 1.4; margin: 4px 0; }
  .action-log b { color: #d9573b; }
  .actions-panel button { width: 100%; padding: 11px; border: 0; cursor: pointer; font-family: 'DM Mono', monospace; font-size: 11px; }
  .primary { background: #d9573b; color: #fff; font-weight: 700; }
  .primary:hover { background: #c2462c; }
  .secondary { margin-top: 6px; background: transparent; color: #68766a; border: 1px solid #ccd5c8 !important; }
  .secondary:hover { background: #e5ede2; }
  .spectator-tools {
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid #d5ddd2;
  }
  .spectator-tools form { margin-top: 8px; }
  .spectator-tools label { display: block; margin-bottom: 5px; font: 10px 'DM Mono', monospace; }
  .spectator-invite-row { display: flex; gap: 6px; }
  .spectator-invite-row input {
    min-width: 0;
    flex: 1;
    border: 1px solid #ccd5c8;
    padding: 8px;
    font: 11px 'DM Mono', monospace;
  }
  .spectator-invite-row button { width: 40px !important; background: #17211b; color: white; }
  .spectator-tools ul { list-style: none; margin: 8px 0 0; padding: 0; }
  .spectator-tools li { display: flex; align-items: center; justify-content: space-between; border-top: 1px solid #d5ddd2; padding: 5px 0; font: 11px 'DM Mono', monospace; }
  .spectator-tools li button { width: 30px !important; padding: 5px; background: transparent; color: #d9573b; }
  .spectator-feedback { margin: 7px 0 0; color: #387b45; font-size: 11px; }
  .spectator-feedback.error { color: #b33e2a; }
  .camera-pairing-backdrop {
    position: fixed;
    inset: 0;
    z-index: 1200;
    display: grid;
    place-items: center;
    padding: 20px;
    background: rgba(7, 12, 8, .78);
  }
  .camera-pairing-dialog {
    position: relative;
    width: min(390px, 100%);
    display: grid;
    justify-items: center;
    gap: 10px;
    padding: 30px;
    background: #f4f1e8;
    color: #17211b;
    text-align: center;
    box-shadow: 0 20px 60px rgba(0,0,0,.4);
  }
  .camera-pairing-dialog h2 { margin: 0; font-size: 25px; }
  .camera-pairing-dialog img { width: 250px; height: 250px; image-rendering: pixelated; }
  .camera-pairing-dialog p { margin: 0; font-size: 13px; }
  .camera-pairing-dialog small { color: #68766a; font: 10px 'DM Mono', monospace; }
  .camera-pairing-dialog a { color: #d9573b; font: 11px 'DM Mono', monospace; }
  .camera-pairing-close {
    position: absolute;
    right: 8px;
    top: 8px;
    width: 32px;
    height: 32px;
    border: 0;
    background: transparent;
    color: #17211b;
    font-size: 22px;
    cursor: pointer;
  }
  .camera-pairing-error {
    position: fixed;
    z-index: 1300;
    right: 20px;
    top: 20px;
    max-width: calc(100% - 40px);
    padding: 12px 40px 12px 14px;
    background: #f4f1e8;
    color: #a93625;
    font-size: 12px;
  }
  .camera-pairing-error button { position: absolute; right: 8px; top: 5px; border: 0; background: transparent; font-size: 18px; }
  .board-tools { margin-top: 14px; padding-top: 12px; border-top: 1px solid #d5ddd2; }
  .board-tools form { display: grid; gap: 6px; margin-top: 8px; }
  .board-tools label { font: 10px 'DM Mono', monospace; }
  .board-tools select, .board-tools input:not([type='checkbox']) { width: 100%; min-width: 0; box-sizing: border-box; border: 1px solid #ccd5c8; padding: 8px; background: #fff; color: #17211b; font: 11px 'DM Mono', monospace; }
  .board-tools .face-down-toggle { display: flex; align-items: center; gap: 6px; }
  .board-tools .face-down-toggle input { margin: 0; }
  .board-feedback { margin: 4px 0; color: #387b45; font-size: 11px; }
  .board-feedback.error { color: #b33e2a; }
  .eyebrow { color: #d9573b; font: 10px 'DM Mono', monospace; text-transform: uppercase; letter-spacing: .08em; }

  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(16, 24, 18, 0.85);
    display: grid;
    place-items: center;
    z-index: 1000;
  }
  .finish {
    background: #f4f1e8;
    color: #17211b;
    padding: 40px;
    text-align: center;
    width: min(420px, calc(100% - 40px));
    border-radius: 4px;
  }
  .finish h2 { font-size: 34px; letter-spacing: -0.05em; margin: 10px 0; }
  .finish a {
    display: inline-block;
    margin-top: 15px;
    background: #d9573b;
    color: #fff;
    padding: 12px 20px;
    text-decoration: none;
    font-family: 'DM Mono', monospace;
    font-size: 12px;
  }

  @media(max-width: 920px) {
    .actions-panel {
      position: static;
      width: auto;
      max-width: 920px;
      margin: 18px auto 0;
    }
  }
</style>
