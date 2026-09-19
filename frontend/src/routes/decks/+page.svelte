<script lang="ts">
  import { onMount } from 'svelte';
  import AppShell from '$lib/components/AppShell.svelte';
  import { apiFetch, requireAuthenticatedUser } from '$lib/services/api';

  type Section = 'main' | 'extra' | 'side';
  interface Print { id: number; set_name: string; set_code: string; language: string | null; rarity: string | null; }
  interface Card { id: number; name: string; card_type: string | null; image_url_small: string | null; prints: Print[]; }
  interface DeckEntry { card_id: number; quantity: number; section: Section; preferred_print_id: number | null; card: Card; }
  interface Deck { id: number; name: string; description: string | null; card_entries: DeckEntry[]; }
  interface Player { username: string; is_admin: boolean; }

  let player: Player | null = null;
  let decks: Deck[] = [];
  let selectedDeck: Deck | null = null;
  let draftName = '';
  let draftDescription = '';
  let draftEntries: DeckEntry[] = [];
  let search = '';
  let searchResults: Card[] = [];
  let searchMessage = '';
  let error = '';
  let isLoading = true;
  let isSaving = false;
  let isSearching = false;

  $: sectionTotals = {
    main: draftEntries.filter((entry) => entry.section === 'main').reduce((total, entry) => total + entry.quantity, 0),
    extra: draftEntries.filter((entry) => entry.section === 'extra').reduce((total, entry) => total + entry.quantity, 0),
    side: draftEntries.filter((entry) => entry.section === 'side').reduce((total, entry) => total + entry.quantity, 0)
  };

  onMount(async () => {
    player = await requireAuthenticatedUser<Player>();
    if (!player) return;
    await loadDecks();
    isLoading = false;
  });

  async function readJson<T>(response: Response): Promise<T> {
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'No fue posible completar la operación.');
    return payload as T;
  }

  async function loadDecks() {
    try {
      decks = await readJson<Deck[]>(await apiFetch('/api/decks'));
    } catch (caught) {
      error = caught instanceof Error ? caught.message : 'No fue posible cargar tus decks.';
    }
  }

  function newDeck() {
    selectedDeck = null;
    draftName = '';
    draftDescription = '';
    draftEntries = [];
    error = '';
  }

  function editDeck(deck: Deck) {
    selectedDeck = deck;
    draftName = deck.name;
    draftDescription = deck.description || '';
    draftEntries = deck.card_entries.map((entry) => ({ ...entry }));
    error = '';
  }

  async function findCards(importMissing = false) {
    const term = search.trim();
    if (!term) {
      searchMessage = 'Escribe el nombre de una carta.';
      return;
    }
    isSearching = true;
    searchMessage = '';
    try {
      let response = await apiFetch(`/api/cards?search=${encodeURIComponent(term)}`);
      searchResults = await readJson<Card[]>(response);
      if (searchResults.length === 0 && importMissing) {
        await readJson(await apiFetch(`/api/cards/import?search=${encodeURIComponent(term)}&limit=20`, { method: 'POST' }));
        response = await apiFetch(`/api/cards?search=${encodeURIComponent(term)}`);
        searchResults = await readJson<Card[]>(response);
      }
      if (searchResults.length === 0) searchMessage = importMissing
        ? 'YGOProDeck no devolvió cartas para esa búsqueda.'
        : 'La carta no está en tu catálogo local. Puedes importarla desde YGOProDeck.';
    } catch (caught) {
      searchMessage = caught instanceof Error ? caught.message : 'No fue posible buscar cartas.';
    } finally {
      isSearching = false;
    }
  }

  function addCard(card: Card) {
    if (draftEntries.some((entry) => entry.card_id === card.id)) {
      searchMessage = 'Esta carta ya está en el deck; ajusta su cantidad.';
      return;
    }
    draftEntries = [...draftEntries, {
      card_id: card.id,
      quantity: 1,
      section: 'main',
      preferred_print_id: null,
      card
    }];
  }

  function updateEntry(cardId: number, changes: Partial<DeckEntry>) {
    draftEntries = draftEntries.map((entry) => entry.card_id === cardId ? { ...entry, ...changes } : entry);
  }

  function removeEntry(cardId: number) {
    draftEntries = draftEntries.filter((entry) => entry.card_id !== cardId);
  }

  async function saveDeck() {
    if (!draftName.trim()) {
      error = 'El deck necesita un nombre.';
      return;
    }
    isSaving = true;
    error = '';
    const body = JSON.stringify({
      name: draftName.trim(),
      description: draftDescription.trim() || null,
      cards: draftEntries.map(({ card_id, quantity, section, preferred_print_id }) => ({
        card_id, quantity, section, preferred_print_id
      }))
    });
    try {
      const response = selectedDeck
        ? await apiFetch(`/api/decks/${selectedDeck.id}`, { method: 'PUT', body })
        : await apiFetch('/api/decks', { method: 'POST', body });
      const saved = await readJson<Deck>(response);
      await loadDecks();
      editDeck(saved);
    } catch (caught) {
      error = caught instanceof Error ? caught.message : 'No fue posible guardar el deck.';
    } finally {
      isSaving = false;
    }
  }

  async function deleteDeck() {
    if (!selectedDeck || !confirm(`¿Eliminar "${selectedDeck.name}"?`)) return;
    try {
      const response = await apiFetch(`/api/decks/${selectedDeck.id}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('No fue posible eliminar el deck.');
      await loadDecks();
      newDeck();
    } catch (caught) {
      error = caught instanceof Error ? caught.message : 'No fue posible eliminar el deck.';
    }
  }
</script>

<svelte:head><title>Mis decks | Duel Assistant</title></svelte:head>

{#if !isLoading && player}
  <AppShell active="decks" username={player.username} isAdmin={player.is_admin}>
    <header class="page-head"><div><p class="eyebrow">Biblioteca personal</p><h1>Mis decks<span>.</span></h1></div><button class="create" on:click={newDeck}>＋ Nuevo deck</button></header>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    <section class="workspace">
      <aside class="deck-list">
        {#each decks as deck (deck.id)}
          <button class:chosen={selectedDeck?.id === deck.id} on:click={() => editDeck(deck)}><strong>{deck.name}</strong><small>{deck.card_entries.reduce((total, entry) => total + entry.quantity, 0)} cartas</small></button>
        {/each}
        {#if decks.length === 0}<p class="empty-list">Aún no tienes decks. Crea el primero.</p>{/if}
      </aside>
      <section class="editor">
        <div class="editor-head"><div><p class="eyebrow">{selectedDeck ? 'Editar deck' : 'Nuevo deck'}</p><h2>{selectedDeck ? selectedDeck.name : 'Construye tu deck'}</h2></div>{#if selectedDeck}<button class="delete" on:click={deleteDeck}>Eliminar</button>{/if}</div>
        <label>Nombre del deck<input bind:value={draftName} maxlength="100" placeholder="Ej. Blue-Eyes Control" /></label>
        <label>Descripción<textarea bind:value={draftDescription} maxlength="500" placeholder="Estrategia o notas opcionales"></textarea></label>
        <div class="search"><label>Buscar carta<input bind:value={search} on:keydown={(event) => event.key === 'Enter' && findCards()} placeholder="Dark Magician" /></label><button on:click={() => findCards()} disabled={isSearching}>{isSearching ? 'Buscando...' : 'Buscar'}</button><button class="secondary" on:click={() => findCards(true)} disabled={isSearching}>Importar de YGOProDeck</button></div>
        {#if searchMessage}<p class="hint">{searchMessage}</p>{/if}
        {#if searchResults.length}
          <div class="results">{#each searchResults as card (card.id)}<article><img src={card.image_url_small || ''} alt="" /><div><strong>{card.name}</strong><small>{card.card_type || 'Carta'}</small></div><button on:click={() => addCard(card)}>Agregar</button></article>{/each}</div>
        {/if}
        <div class="totals"><span>Main: {sectionTotals.main}</span><span>Extra: {sectionTotals.extra}</span><span>Side: {sectionTotals.side}</span></div>
        <div class="entries">
          {#each draftEntries as entry (entry.card_id)}
            <article><img src={entry.card.image_url_small || ''} alt="" /><div class="entry-name"><strong>{entry.card.name}</strong><select value={entry.section} on:change={(event) => updateEntry(entry.card_id, { section: event.currentTarget.value as Section })}><option value="main">Main Deck</option><option value="extra">Extra Deck</option><option value="side">Side Deck</option></select></div><label class="quantity">Copias<input type="number" min="1" max="3" value={entry.quantity} on:change={(event) => updateEntry(entry.card_id, { quantity: Math.max(1, Math.min(3, Number(event.currentTarget.value) || 1)) })} /></label><label class="print">Impresión<select value={entry.preferred_print_id ?? ''} on:change={(event) => updateEntry(entry.card_id, { preferred_print_id: event.currentTarget.value ? Number(event.currentTarget.value) : null })}><option value="">Cualquiera</option>{#each entry.card.prints as print (print.id)}<option value={print.id}>{print.set_code} · {print.rarity || 'Sin rareza'}</option>{/each}</select></label><button class="remove" on:click={() => removeEntry(entry.card_id)}>×</button></article>
          {/each}
          {#if draftEntries.length === 0}<p class="empty-list">Busca y agrega cartas al deck.</p>{/if}
        </div>
        <button class="save" on:click={saveDeck} disabled={isSaving}>{isSaving ? 'Guardando...' : 'Guardar deck'}</button>
      </section>
    </section>
  </AppShell>
{/if}

<style>
  .page-head,.editor-head{display:flex;align-items:end;justify-content:space-between;gap:18px;margin-bottom:28px}.page-head h1{font-size:clamp(44px,6vw,76px);letter-spacing:-.08em;margin:8px 0}.page-head h1 span,.eyebrow{color:#d9573b}.eyebrow{font:11px 'DM Mono',monospace;text-transform:uppercase;letter-spacing:.08em}.create,.save{border:0;background:#17211b;color:#fff;padding:14px 18px;cursor:pointer}.workspace{display:grid;grid-template-columns:250px minmax(0,1fr);gap:20px;max-width:1150px}.deck-list,.editor{background:#fffdf7;border:1px solid #dbe1d8;padding:18px}.deck-list{display:grid;align-content:start;gap:8px}.deck-list button{display:grid;gap:5px;text-align:left;border:1px solid #dbe1d8;background:#fff;padding:14px;cursor:pointer}.deck-list button.chosen{background:#17211b;color:#fff;border-color:#17211b}.deck-list small,.hint,.empty-list{color:#637064;font:11px 'DM Mono',monospace}.editor{display:grid;gap:16px}.editor h2{margin:5px 0 0;font-size:28px}.editor label{display:grid;gap:7px;color:#536257;font:11px 'DM Mono',monospace;text-transform:uppercase}.editor input,.editor textarea,.editor select{font:14px 'Space Grotesk',sans-serif;border:1px solid #ccd5c8;padding:10px;background:#fff}.editor textarea{min-height:65px;resize:vertical}.search{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px;align-items:end}.search button,.results button,.remove,.delete{border:0;padding:11px;background:#d9573b;color:#fff;cursor:pointer}.search .secondary{background:#657565}.results,.entries{display:grid;gap:8px}.results article,.entries article{display:flex;align-items:center;gap:10px;border:1px solid #e0e5dc;padding:8px}.results img,.entries img{width:38px;height:54px;object-fit:cover;background:#e6e9e2}.results div,.entry-name{display:grid;gap:4px;flex:1}.results small{font-size:12px;color:#637064}.entries article{flex-wrap:wrap}.quantity{width:65px}.quantity input{width:100%}.print{min-width:180px}.remove{background:#7b2f26}.totals{display:flex;gap:12px;font:11px 'DM Mono',monospace;color:#637064}.save{justify-self:end;background:#d9573b}.delete{background:#7b2f26}.error{background:#fde8e4;color:#9d2819;padding:14px}@media(max-width:800px){.workspace{grid-template-columns:1fr}.search{grid-template-columns:1fr}.print{width:100%}.page-head{align-items:start;flex-direction:column}}
</style>
