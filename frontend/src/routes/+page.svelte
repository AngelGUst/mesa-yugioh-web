<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import AppShell from '$lib/components/AppShell.svelte';

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  let isCheckingSession = true;
  let error = '';
  let player: Player | null = null;
  let duels: Duel[] = [];
  let decks: Deck[] = [];

  interface Player {
    id: number;
    username: string;
    is_admin: boolean;
    lp_wins: number;
    lp_losses: number;
  }

  interface Duel {
    id: number;
    duel_code: string;
    player1_id: number;
    player2_id: number | null;
    player1_lp: number;
    player2_lp: number;
    status: 'waiting' | 'active' | 'finished';
    turn: number;
    current_phase: string;
  }

  interface Deck {
    id: number;
    card_entries: { quantity: number }[];
  }

  $: activeDuels = duels.filter((duel) => duel.status === 'active');
  $: waitingDuels = duels.filter((duel) => duel.status === 'waiting');
  $: totalCards = decks.reduce(
    (total, deck) => total + deck.card_entries.reduce((deckTotal, entry) => deckTotal + entry.quantity, 0),
    0
  );

  onMount(async () => {
    const token = localStorage.getItem('duel_session');

    if (!token) {
      goto('/login');
      return;
    }

    try {
      const profileResponse = await fetch(`${apiUrl}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      if (!profileResponse.ok) {
        localStorage.removeItem('duel_session');
        goto('/login');
        return;
      }

      player = await profileResponse.json();
      const headers = { Authorization: `Bearer ${token}` };
      const [duelsResponse, decksResponse] = await Promise.all([
        fetch(`${apiUrl}/api/duels`, { headers }),
        fetch(`${apiUrl}/api/decks`, { headers })
      ]);

      if (!duelsResponse.ok || !decksResponse.ok) {
        error = 'No fue posible cargar tu informacion de juego.';
      } else {
        [duels, decks] = await Promise.all([duelsResponse.json(), decksResponse.json()]);
      }
    } catch {
      localStorage.removeItem('duel_session');
      goto('/login');
      return;
    }

    isCheckingSession = false;
  });
</script>

<svelte:head><title>Inicio | Duel Assistant</title></svelte:head>

{#if !isCheckingSession}
  <AppShell active="home" username={player?.username ?? ''} isAdmin={player?.is_admin ?? false}>
    <header class="page-head"><div><p class="eyebrow">Mi mesa</p><h1>Hola, {player?.username}<span>.</span></h1></div><span class="online"><i></i> API conectada</span></header>
    <section class="welcome"><div><p class="eyebrow">Panel de juego</p><h2>Tu partida,<br /><em>bajo control.</em></h2><p>Registra puntos de vida, turnos y acciones sin perder el ritmo del duelo físico.</p></div><a class="start" href="/duel/new">＋ Crear nuevo duelo <span>→</span></a></section>
    {#if error}
      <p class="load-error" role="alert">{error}</p>
    {:else}
      <div class="section-title"><h3>Mis duelos activos</h3><a href="/duel/new">Crear duelo →</a></div>
      <section class="duel-list">
        {#each activeDuels as duel (duel.id)}
          <article class="duel-card active-card"><div class="card-top"><span class="live"><i></i> En curso</span><small>Sala {duel.duel_code}</small></div><div class="match"><div><strong>{player?.username}</strong><b>{duel.player1_id === player?.id ? duel.player1_lp : duel.player2_lp} LP</b></div><span>VS</span><div><strong>Oponente</strong><b>{duel.player1_id === player?.id ? duel.player2_lp : duel.player1_lp} LP</b></div></div><div class="card-bottom"><span>Turno {duel.turn} · {duel.current_phase.replaceAll('_', ' ')}</span><span>En curso</span></div></article>
        {/each}
        {#if activeDuels.length === 0}
          <article class="empty-state"><strong>No tienes duelos activos.</strong><a href="/duel/new">Crear un nuevo duelo →</a></article>
        {/if}
        {#each waitingDuels as duel (duel.id)}
          <article class="duel-card waiting-card"><div class="card-top"><span class="waiting">Esperando oponente</span><small>Sala privada</small></div><div class="waiting-body"><strong>{duel.duel_code}</strong><p>Comparte el codigo para comenzar.</p></div><div class="card-bottom"><span>Turno {duel.turn}</span><span>En espera</span></div></article>
        {/each}
      </section>
      <div class="section-title"><h3>Resumen</h3><a href="/decks">Gestionar decks →</a></div>
      <section class="stats"><article><small>Victorias</small><strong>{player?.lp_wins ?? 0}</strong><span>Registradas en tu cuenta</span></article><article><small>Derrotas</small><strong>{player?.lp_losses ?? 0}</strong><span>Registradas en tu cuenta</span></article><article class="warm"><small>Mis decks</small><strong>{decks.length}</strong><span>{totalCards} cartas configuradas</span></article></section>
    {/if}
  </AppShell>
{/if}

<style>
  .page-head{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:35px}.page-head h1{font-size:clamp(40px,5vw,66px);letter-spacing:-.07em;margin:8px 0 0}.page-head h1 span,.welcome em{color:#d9573b;font-style:normal}.eyebrow{color:#d9573b;font:11px 'DM Mono',monospace;text-transform:uppercase;letter-spacing:.08em;margin:0}.online{font:10px 'DM Mono',monospace;color:#637064}.online i,.live i{display:inline-block;width:7px;height:7px;border-radius:50%;background:#569b62;margin-right:7px}.welcome{display:flex;justify-content:space-between;align-items:end;background:#17211b;color:#f7f4e9;padding:34px 38px;margin-bottom:40px;min-height:220px}.welcome h2{font-size:clamp(38px,5vw,62px);letter-spacing:-.07em;line-height:.92;margin:12px 0}.welcome p:not(.eyebrow){max-width:380px;color:#b2c0b0;line-height:1.5;margin-bottom:0}.start{background:#d9573b;color:#fff;padding:14px 17px;font-size:13px}.start span{margin-left:20px}.section-title{display:flex;justify-content:space-between;align-items:center;margin:0 0 15px}.section-title h3{font-size:18px;margin:0}.section-title a,.empty-state a{color:#d9573b;font:11px 'DM Mono',monospace}.duel-list,.stats{display:grid;grid-template-columns:1.35fr 1fr;gap:13px;margin-bottom:40px}.duel-card,.empty-state{padding:20px;background:#fffdf7;border:1px solid #dbe1d8}.empty-state{display:grid;place-content:center;gap:10px;min-height:170px;color:#637064}.active-card{background:#17211b;color:#f7f4e9;border:0}.card-top,.card-bottom{display:flex;justify-content:space-between;align-items:center;font:10px 'DM Mono',monospace;color:#899789}.active-card .card-top{color:#a6b5a4}.live{color:#70bd7a}.waiting{color:#d9573b}.match{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;text-align:center;gap:15px;padding:27px 0}.match div:first-child{text-align:left}.match div:last-child{text-align:right}.match strong{display:block;font-size:17px}.match b{display:block;color:#e66b4e;font:17px 'DM Mono',monospace;margin-top:6px}.match>span{color:#f0b75f;font:11px 'DM Mono',monospace}.card-bottom{border-top:1px solid #35443a;padding-top:15px}.waiting-card .card-bottom{border-color:#dbe1d8}.waiting-body{padding:27px 0}.waiting-body strong{font:22px 'DM Mono',monospace;letter-spacing:.05em}.waiting-body p{color:#637064;font-size:13px}.stats{grid-template-columns:repeat(3,1fr)}.stats article{background:#fffdf7;border:1px solid #dbe1d8;padding:20px;min-height:130px}.stats .warm{background:#f1e4d1;border-color:#e4d3bb}.stats small,.stats span{display:block;color:#637064;font:10px 'DM Mono',monospace}.stats strong{display:block;font:44px 'DM Mono',monospace;margin:16px 0 5px}.load-error{background:#fde8e4;color:#9d2819;padding:14px}@media(max-width:720px){.welcome{display:block;padding:26px}.start{display:inline-block;margin-top:25px}.duel-list,.stats{grid-template-columns:1fr}.page-head{align-items:start;gap:15px;flex-direction:column}}
</style>
