<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiFetch, requireAuthenticatedUser } from '$lib/services/api';

  interface Player { username: string; }
  interface Deck { id: number; name: string; card_entries: { quantity: number }[]; }
  interface Duel { id: number; duel_code: string; name: string | null; status: string; }

  let player: Player | null = null;
  let decks: Deck[] = [];
  let name = '';
  let deckId = '';
  let joinCode = '';
  let joinDeckId = '';
  let createdDuel: Duel | null = null;
  let error = '';
  let isLoading = true;
  let isCreating = false;
  let isJoining = false;

  onMount(async () => {
    player = await requireAuthenticatedUser<Player>();
    if (!player) return;
    try {
      const response = await apiFetch('/api/decks');
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'No fue posible cargar tus decks.');
      decks = payload;
    } catch (caught) {
      error = caught instanceof Error ? caught.message : 'No fue posible cargar los decks.';
    } finally {
      isLoading = false;
    }
  });

  async function createRoom() {
    error = '';
    isCreating = true;
    try {
      const response = await apiFetch('/api/duels', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim() || null, deck_id: deckId ? Number(deckId) : null })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'No fue posible crear la sala.');
      createdDuel = payload;
    } catch (caught) {
      error = caught instanceof Error ? caught.message : 'No fue posible crear la sala.';
    } finally {
      isCreating = false;
    }
  }

  async function joinRoom() {
    if (!joinCode.trim()) {
      error = 'Ingresa el código de la sala.';
      return;
    }
    error = '';
    isJoining = true;
    try {
      const response = await apiFetch('/api/duels/join', {
        method: 'POST',
        body: JSON.stringify({ duel_code: joinCode.trim(), deck_id: joinDeckId ? Number(joinDeckId) : null })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'No fue posible unirse a la sala.');
      await goto('/');
    } catch (caught) {
      error = caught instanceof Error ? caught.message : 'No fue posible unirse a la sala.';
    } finally {
      isJoining = false;
    }
  }
</script>

<svelte:head><title>Nuevo duelo | Duel Assistant</title></svelte:head>

{#if !isLoading && player}
  <div class="new-page"><a class="back" href="/">← Volver al inicio</a><div class="new-grid"><section><p class="eyebrow">Preparar mesa</p><h1>Abre una sala<br /><em>para jugar.</em></h1><p class="lead">Crea una sala privada y comparte el código con tu oponente, o únete con un código existente.</p></section><section class="setup-panel">
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    <div class="panel-head"><span>Crear sala</span><span class="step">01 / 02</span></div>
    <label>Nombre de la sala<input bind:value={name} maxlength="100" placeholder="Duelo de viernes" /></label>
    <label>Deck para este duelo<select bind:value={deckId}><option value="">Sin deck seleccionado</option>{#each decks as deck (deck.id)}<option value={deck.id}>{deck.name} · {deck.card_entries.reduce((total, entry) => total + entry.quantity, 0)} cartas</option>{/each}</select></label>
    <button on:click={createRoom} disabled={isCreating}>{isCreating ? 'Creando...' : 'Crear sala'} <span>→</span></button>
    {#if createdDuel}<div class="room-code"><small>Código para compartir</small><strong>{createdDuel.duel_code}</strong><button class="copy" on:click={() => navigator.clipboard?.writeText(createdDuel?.duel_code || '')}>Copiar código</button><a href="/">Ver mis salas →</a></div>{/if}
    <div class="join"><div class="panel-head"><span>Unirse a una sala</span><span class="step">02 / 02</span></div><label>Código de sala<input bind:value={joinCode} maxlength="20" placeholder="AB12CD34EF" /></label><label>Deck para este duelo<select bind:value={joinDeckId}><option value="">Sin deck seleccionado</option>{#each decks as deck (deck.id)}<option value={deck.id}>{deck.name}</option>{/each}</select></label><button on:click={joinRoom} disabled={isJoining}>{isJoining ? 'Uniéndose...' : 'Unirse'} <span>→</span></button></div>
  </section></div></div>
{/if}

<style>
  .new-page{min-height:100vh;padding:30px clamp(24px,7vw,100px);background:linear-gradient(125deg,#f4f4ed,#e3ebe0)}.back{font:11px 'DM Mono',monospace;color:#637064}.new-grid{max-width:1100px;margin:clamp(70px,12vw,145px) auto;display:grid;grid-template-columns:1fr 1fr;gap:clamp(45px,10vw,150px);align-items:start}.new-page h1{font-size:clamp(52px,7vw,90px);line-height:.92;letter-spacing:-.075em;margin:15px 0}.new-page h1 em{color:#d9573b;font-style:normal}.eyebrow{color:#d9573b;font:11px 'DM Mono',monospace;text-transform:uppercase;letter-spacing:.08em}.lead{max-width:380px;color:#637064;line-height:1.6}.setup-panel{display:grid;gap:18px;background:#fffdf7;padding:28px;box-shadow:12px 18px 40px #82918122}.panel-head{display:flex;justify-content:space-between;border-bottom:1px solid #e0e5dc;padding-bottom:14px;font:12px 'DM Mono',monospace;text-transform:uppercase}.step{color:#d9573b}.setup-panel label{display:grid;gap:8px;color:#637064;font:11px 'DM Mono',monospace;text-transform:uppercase}.setup-panel input,.setup-panel select{border:1px solid #d5ddd2;padding:14px;background:#f7f8f3;font:15px 'Space Grotesk',sans-serif}.setup-panel button{width:100%;border:0;padding:15px;background:#d9573b;color:#fff;text-align:left;display:flex;justify-content:space-between;cursor:pointer}.setup-panel button:disabled{opacity:.7;cursor:wait}.room-code{padding:20px;background:#f3e4d0;text-align:center}.room-code small{display:block;color:#8f6f4e;font:10px 'DM Mono',monospace;text-transform:uppercase}.room-code strong{display:block;margin:7px;font:700 30px 'DM Mono',monospace;letter-spacing:.08em}.room-code .copy{display:inline-block;width:auto;background:none;color:#d9573b;padding:0;font:11px 'DM Mono',monospace}.room-code a{display:block;margin-top:17px;color:#17211b;font-size:13px}.join{display:grid;gap:18px;border-top:1px solid #e0e5dc;padding-top:22px}.error{margin:0;background:#fde8e4;color:#9d2819;padding:12px}@media(max-width:720px){.new-grid{grid-template-columns:1fr;margin:80px auto}.new-page h1{font-size:57px}}
</style>
