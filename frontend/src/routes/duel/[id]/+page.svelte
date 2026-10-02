<script lang="ts">
  import { onMount } from 'svelte';
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
    created_at: string;
  }

  interface Duel {
    id: number;
    duel_code: string;
    name: string | null;
    player1_id: number;
    player2_id: number | null;
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
  }

  let duelId = $page.params.id;
  let player: Player | null = null;
  let duel: Duel | null = null;
  let isLoading = true;
  let error = '';
  let finished = false;
  let connectionStatus: 'connecting' | 'connected' | 'disconnected' = 'connecting';
  let logs: { turn: number; text: string }[] = [];

  const phases = [
    'DRAW PHASE',
    'STANDBY PHASE',
    'MAIN PHASE 1',
    'BATTLE PHASE',
    'MAIN PHASE 2',
    'END PHASE'
  ];

  $: isPlayer1 = duel && player ? duel.player1_id === player.id : true;
  $: myUsername = player?.username || 'Tú';
  $: opponentUsername = (isPlayer1 ? duel?.player2_username : duel?.player1_username) || 'Oponente';
  $: myLp = duel ? (isPlayer1 ? duel.player1_lp : duel.player2_lp) : 8000;
  $: opponentLp = duel ? (isPlayer1 ? duel.player2_lp : duel.player1_lp) : 8000;
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
          if (update.type === 'DUEL_UPDATED' && update.duel) {
            const previousDuel = duel;
            const updatedDuel = update.duel as Duel;
            duel = updatedDuel;
            finished = updatedDuel.status === 'finished';

            if (previousDuel && previousDuel.current_phase !== updatedDuel.current_phase) {
              logs = [{ turn: updatedDuel.turn, text: `Fase: ${updatedDuel.current_phase.replaceAll('_', ' ')}` }, ...logs];
            } else if (previousDuel && previousDuel.turn !== updatedDuel.turn) {
              logs = [{ turn: updatedDuel.turn, text: `Turno ${updatedDuel.turn}` }, ...logs];
            }
          } else if (update.type === 'DUEL_EVENT' && update.event) {
            const duelEvent = update.event as DuelEvent;
            const payload = duelEvent.payload || {};
            const targetPlayerId = Number(payload.target_player_id);
            const targetName = targetPlayerId === duel?.player1_id
              ? duel.player1_username
              : targetPlayerId === duel?.player2_id
                ? duel.player2_username || 'Oponente'
                : String(payload.target || 'duelo');
            const eventText = duelEvent.event_type === 'LP_CHANGE'
              ? `${targetName} ${Number(payload.delta) > 0 ? '+' : ''}${payload.delta} LP (${payload.new_lp})`
              : `Evento: ${duelEvent.event_type.replaceAll('_', ' ')}`;

            logs = [{ turn: duel?.turn || 1, text: eventText }, ...logs];
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
      if (!error) connect();
    }

    void initialize();

    return () => {
      disposed = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (pingTimer) clearInterval(pingTimer);
      socket?.close();
    };
  });

  async function loadDuel() {
    try {
      const res = await apiFetch(`/api/duels/${duelId}`);
      if (!res.ok) {
        const p = await res.json();
        throw new Error(p.detail || 'No se pudo cargar el duelo.');
      }
      duel = await res.json();
      if (duel?.status === 'finished') {
        finished = true;
      }
      if (duel) {
        logs = [
          { turn: duel.turn, text: `Duelo iniciado: ${duel.player1_username} vs ${duel.player2_username || 'Oponente'}` }
        ];
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Error al cargar el duelo.';
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
        <button class="phase-btn" on:click={advancePhase} title="Avanzar a la siguiente fase">
          Avanzar fase ↷
        </button>
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
        <small>TU LP</small>
        <strong>{myLp}</strong>
        <span>{myUsername}</span>
        <div class="lp-actions">
          <button on:click={() => changeLp(-1000, 'me')}>−1000</button>
          <button on:click={() => changeLp(-500, 'me')}>−500</button>
          <button on:click={() => changeLp(-100, 'me')}>−100</button>
          <button on:click={() => changeLp(100, 'me')}>+100</button>
          <button on:click={() => changeLp(500, 'me')}>+500</button>
          <button on:click={() => changeLp(1000, 'me')}>+1000</button>
        </div>
      </div>

      <div class="versus">
        VS<br />
        <small>SALA {duel.duel_code}</small>
      </div>

      <!-- OPONENTE -->
      <div class="fighter opponent">
        <small>OPONENTE</small>
        <strong>{opponentLp}</strong>
        <span>{opponentUsername}</span>
        <div class="lp-actions">
          <button on:click={() => changeLp(-1000, 'opponent')}>−1000</button>
          <button on:click={() => changeLp(-500, 'opponent')}>−500</button>
          <button on:click={() => changeLp(-100, 'opponent')}>−100</button>
          <button on:click={() => changeLp(100, 'opponent')}>+100</button>
          <button on:click={() => changeLp(500, 'opponent')}>+500</button>
          <button on:click={() => changeLp(1000, 'opponent')}>+1000</button>
        </div>
      </div>
    </section>

    <!-- TABLERO DIGITAL DE YU-GI-OH! (REGLA MAESTRA / 7 COLUMNAS) -->
    <section class="board">
      <!-- CAMPO OPONENTE -->
      <div class="field-side opponent-field">
        <small class="field-label">CAMPO DEL OPONENTE ({opponentUsername})</small>
        
        <!-- Fila Mágicas / Trampas y Decks Oponente -->
        <div class="ygo-grid">
          <div class="zone deck-zone"><span>DECK</span></div>
          <div class="zone pendulum-zone red"><span>PÉNDULO<br/>(ROJO)</span></div>
          <div class="zone spell-zone"><span>MÁGICAS &amp; TRAMPAS</span></div>
          <div class="zone spell-zone"><span>MÁGICAS &amp; TRAMPAS</span></div>
          <div class="zone spell-zone"><span>MÁGICAS &amp; TRAMPAS</span></div>
          <div class="zone pendulum-zone blue"><span>PÉNDULO<br/>(AZUL)</span></div>
          <div class="zone extra-deck-zone"><span>DECK EXTRA</span></div>
        </div>

        <!-- Fila Monstruos Oponente -->
        <div class="ygo-grid">
          <div class="zone grave-zone"><span>CEMENTERIO</span></div>
          <div class="zone monster-zone"><span>MONSTRUO 5</span></div>
          <div class="zone monster-zone"><span>MONSTRUO 4</span></div>
          <div class="zone monster-zone"><span>MONSTRUO 3</span></div>
          <div class="zone monster-zone"><span>MONSTRUO 2</span></div>
          <div class="zone monster-zone"><span>MONSTRUO 1</span></div>
          <div class="zone field-spell-zone"><span>CAMPO</span></div>
        </div>
      </div>

      <!-- ZONAS DE MONSTRUO EXTRA (COMPARTIDAS EN EL CENTRO) -->
      <div class="emz-container">
        <div class="ygo-grid">
          <div class="empty-cell"></div>
          <div class="empty-cell"></div>
          <div class="zone extra-monster-zone">
            <span class="emz-badge">EMZ 1</span>
            <span>MONSTRUO EXTRA</span>
          </div>
          <div class="empty-cell"></div>
          <div class="zone extra-monster-zone">
            <span class="emz-badge">EMZ 2</span>
            <span>MONSTRUO EXTRA</span>
          </div>
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
          <div class="zone field-spell-zone"><span>ZONA DEL CAMPO</span></div>
          <div class="zone monster-zone"><span>MONSTRUO 1</span></div>
          <div class="zone monster-zone"><span>MONSTRUO 2</span></div>
          <div class="zone monster-zone"><span>MONSTRUO 3</span></div>
          <div class="zone monster-zone"><span>MONSTRUO 4</span></div>
          <div class="zone monster-zone"><span>MONSTRUO 5</span></div>
          <div class="zone grave-zone"><span>CEMENTERIO</span></div>
        </div>

        <!-- Fila Mágicas / Trampas y Decks Propio -->
        <div class="ygo-grid">
          <div class="zone extra-deck-zone"><span>DECK EXTRA</span></div>
          <div class="zone pendulum-zone blue">
            <span class="pend-gem blue-gem">⯁</span>
            <span>PÉNDULO (AZUL)</span>
          </div>
          <div class="zone spell-zone"><span>MÁGICAS &amp; TRAMPAS 2</span></div>
          <div class="zone spell-zone"><span>MÁGICAS &amp; TRAMPAS 3</span></div>
          <div class="zone spell-zone"><span>MÁGICAS &amp; TRAMPAS 4</span></div>
          <div class="zone pendulum-zone red">
            <span class="pend-gem red-gem">⯁</span>
            <span>PÉNDULO (ROJO)</span>
          </div>
          <div class="zone deck-zone"><span>DECK</span></div>
        </div>

        <!-- Barra inferior: Destierro, Escáner y Mano -->
        <div class="bottom-tools">
          <div class="zone banish-zone"><span>DESTIERRO (0)</span></div>
          <button class="scan-button" on:click={() => alert('Escáner móvil se activará con código QR')}>
            📷 Vincular Escáner
          </button>
          <div class="hand">
            <span>MANO ({myUsername})</span>
            <i></i><i></i><i></i><i></i><i></i>
          </div>
        </div>

        <small class="field-label">TU CAMPO ({myUsername})</small>
      </div>
    </section>

    <!-- PANEL DE ACCIONES Y REGISTRO EN VIVO -->
    <aside class="actions-panel">
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
      <button class="primary" on:click={endTurn}>Fin de turno <span>→</span></button>
      <button class="secondary" on:click={concedeDuel}>Conceder duelo</button>
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
  }
  .zone {
    min-height: 68px;
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
  }
  .actions-panel h2 { margin: 4px 0 12px; font-size: 22px; }
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
