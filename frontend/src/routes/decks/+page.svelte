<script lang="ts">
  import { onMount } from 'svelte';
  import AppShell from '$lib/components/AppShell.svelte';
  import { apiFetch, requireAuthenticatedUser } from '$lib/services/api';

  type Section = 'main' | 'extra' | 'side';
  type FilterCategory = 'all' | 'monster' | 'spell' | 'trap' | 'extra';

  interface Print {
    id: number;
    set_name: string;
    set_code: string;
    language: string | null;
    rarity: string | null;
  }

  interface Card {
    id: number;
    ygoprodeck_id: number;
    name: string;
    card_type: string | null;
    description: string | null;
    atk: number | null;
    def_: number | null;
    level: number | null;
    race: string | null;
    attribute: string | null;
    human_readable_card_type: string | null;
    frame_type: string | null;
    archetype: string | null;
    image_url: string | null;
    image_url_small: string | null;
    prints: Print[];
  }

  interface DeckEntry {
    card_id: number;
    quantity: number;
    section: Section;
    preferred_print_id: number | null;
    card: Card;
  }

  interface Deck {
    id: number;
    name: string;
    description: string | null;
    card_entries: DeckEntry[];
  }

  interface Player {
    username: string;
    is_admin: boolean;
  }

  let player: Player | null = null;
  let decks: Deck[] = [];
  let selectedDeck: Deck | null = null;

  // Estado del deck actual en edición
  let deckName = '';
  let deckDescription = '';
  let draftEntries: DeckEntry[] = [];

  // Pestañas y paneles
  let rightTab: 'catalog' | 'inspector' | 'testHand' = 'catalog';
  let activeSectionView: 'all' | 'main' | 'extra' | 'side' = 'all';
  let inspectingCard: Card | null = null;
  let testHand: Card[] = [];

  // Búsqueda en catálogo
  let search = '';
  let searchResults: Card[] = [];
  let filterCategory: FilterCategory = 'all';
  let searchMessage = '';
  let isSearching = false;

  // Estados de carga y feedback
  let isLoading = true;
  let isSaving = false;
  let error = '';
  let successNotification = '';

  // Estado del modal de importación
  let isImportModalOpen = false;
  let importName = '';
  let importContent = '';
  let isImporting = false;

  // Cálculos reactivos del deck
  $: mainEntries = draftEntries.filter((e) => e.section === 'main');
  $: extraEntries = draftEntries.filter((e) => e.section === 'extra');
  $: sideEntries = draftEntries.filter((e) => e.section === 'side');

  $: mainTotal = mainEntries.reduce((acc, e) => acc + e.quantity, 0);
  $: extraTotal = extraEntries.reduce((acc, e) => acc + e.quantity, 0);
  $: sideTotal = sideEntries.reduce((acc, e) => acc + e.quantity, 0);
  $: totalCards = mainTotal + extraTotal + sideTotal;

  $: mainMonsters = mainEntries
    .filter((e) => getCategory(e.card) === 'monster')
    .reduce((acc, e) => acc + e.quantity, 0);
  $: mainSpells = mainEntries
    .filter((e) => getCategory(e.card) === 'spell')
    .reduce((acc, e) => acc + e.quantity, 0);
  $: mainTraps = mainEntries
    .filter((e) => getCategory(e.card) === 'trap')
    .reduce((acc, e) => acc + e.quantity, 0);

  $: inspectingEntry = inspectingCard
    ? draftEntries.find((e) => (e.card_id ?? e.card?.id) === inspectingCard?.id) || null
    : null;

  $: filteredSearchResults = searchResults.filter((card) => {
    if (filterCategory === 'all') return true;
    if (filterCategory === 'extra') return isExtraDeckCard(card);
    return getCategory(card) === filterCategory;
  });

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

  async function loadDecks(preferredId?: number) {
    try {
      decks = await readJson<Deck[]>(await apiFetch('/api/decks'));
      if (preferredId) {
        const found = decks.find((d) => d.id === preferredId);
        if (found) {
          selectDeck(found);
          return;
        }
      }
      if (decks.length > 0 && !selectedDeck) {
        selectDeck(decks[0]);
      } else if (decks.length === 0) {
        initNewDeck();
      }
    } catch (caught) {
      error = caught instanceof Error ? caught.message : 'No fue posible cargar tus decks.';
    }
  }

  function selectDeck(deck: Deck) {
    selectedDeck = deck;
    deckName = deck.name;
    deckDescription = deck.description || '';
    draftEntries = deck.card_entries.map((entry) => ({
      ...entry,
      card_id: entry.card_id ?? entry.card?.id
    }));
    error = '';
    successNotification = '';
    if (draftEntries.length > 0) {
      inspectCard(draftEntries[0].card);
    } else {
      inspectingCard = null;
    }
  }

  function initNewDeck() {
    selectedDeck = null;
    deckName = 'Nuevo Deck';
    deckDescription = '';
    draftEntries = [];
    inspectingCard = null;
    rightTab = 'catalog';
    error = '';
    successNotification = '';
  }

  function isExtraDeckCard(card: Card): boolean {
    const t = (card.card_type || '').toLowerCase();
    const frame = (card.frame_type || '').toLowerCase();
    return (
      t.includes('fusion') ||
      t.includes('synchro') ||
      t.includes('xyz') ||
      t.includes('link') ||
      frame === 'fusion' ||
      frame === 'synchro' ||
      frame === 'xyz' ||
      frame === 'link'
    );
  }

  function getCategory(card: Card): 'monster' | 'spell' | 'trap' {
    const t = (card.card_type || '').toLowerCase();
    if (t.includes('spell')) return 'spell';
    if (t.includes('trap')) return 'trap';
    return 'monster';
  }

  function getCardFrameClass(card: Card): string {
    const frame = (card.frame_type || '').toLowerCase();
    const t = (card.card_type || '').toLowerCase();
    if (frame === 'spell' || t.includes('spell')) return 'frame-spell';
    if (frame === 'trap' || t.includes('trap')) return 'frame-trap';
    if (frame === 'fusion' || t.includes('fusion')) return 'frame-fusion';
    if (frame === 'synchro' || t.includes('synchro')) return 'frame-synchro';
    if (frame === 'xyz' || t.includes('xyz')) return 'frame-xyz';
    if (frame === 'link' || t.includes('link')) return 'frame-link';
    if (frame === 'ritual' || t.includes('ritual')) return 'frame-ritual';
    return 'frame-monster';
  }

  function inspectCard(card: Card) {
    inspectingCard = card;
    rightTab = 'inspector';
  }

  function addCard(card: Card, targetSection?: Section) {
    const cardId = card.id;
    const existing = draftEntries.find((e) => (e.card_id ?? e.card?.id) === cardId);

    if (existing) {
      if (existing.quantity < 3) {
        existing.quantity += 1;
        draftEntries = [...draftEntries];
        showFlash(`+1 copia agregada (${existing.quantity}/3)`);
      } else {
        showFlash('Límite de 3 copias alcanzado para esta carta.', true);
      }
    } else {
      const section: Section = targetSection ?? (isExtraDeckCard(card) ? 'extra' : 'main');
      const newEntry: DeckEntry = {
        card_id: cardId,
        quantity: 1,
        section,
        preferred_print_id: card.prints?.[0]?.id ?? null,
        card
      };
      draftEntries = [...draftEntries, newEntry];
      showFlash(`"${card.name}" agregada al ${section.toUpperCase()} Deck`);
    }

    inspectCard(card);
  }

  function adjustQuantity(cardId: number, delta: number) {
    const entry = draftEntries.find((e) => (e.card_id ?? e.card?.id) === cardId);
    if (!entry) return;

    const newQty = entry.quantity + delta;
    if (newQty <= 0) {
      removeCard(cardId);
    } else if (newQty > 3) {
      showFlash('Máximo 3 copias permitidas por carta.', true);
    } else {
      entry.quantity = newQty;
      draftEntries = [...draftEntries];
    }
  }

  function moveCardSection(cardId: number, newSection: Section) {
    const entry = draftEntries.find((e) => (e.card_id ?? e.card?.id) === cardId);
    if (!entry) return;
    entry.section = newSection;
    draftEntries = [...draftEntries];
    showFlash(`Movida a ${newSection.toUpperCase()} Deck`);
  }

  function updatePreferredPrint(cardId: number, printId: number | null) {
    const entry = draftEntries.find((e) => (e.card_id ?? e.card?.id) === cardId);
    if (!entry) return;
    entry.preferred_print_id = printId;
    draftEntries = [...draftEntries];
  }

  function removeCard(cardId: number) {
    draftEntries = draftEntries.filter((e) => (e.card_id ?? e.card?.id) !== cardId);
    showFlash('Carta retirada del deck');
  }

  function showFlash(msg: string, isErr = false) {
    if (isErr) {
      error = msg;
      setTimeout(() => (error = ''), 3500);
    } else {
      successNotification = msg;
      setTimeout(() => (successNotification = ''), 2500);
    }
  }

  async function findCards(importMissing = false) {
    const term = search.trim();
    if (!term) {
      searchMessage = 'Escribe el nombre o arquetipo de una carta.';
      return;
    }
    isSearching = true;
    searchMessage = '';
    try {
      let response = await apiFetch(`/api/cards?search=${encodeURIComponent(term)}`);
      searchResults = uniqueCards(await readJson<Card[]>(response));
      if (searchResults.length === 0 && importMissing) {
        await readJson(
          await apiFetch(`/api/cards/import?search=${encodeURIComponent(term)}&limit=25`, {
            method: 'POST'
          })
        );
        response = await apiFetch(`/api/cards?search=${encodeURIComponent(term)}`);
        searchResults = uniqueCards(await readJson<Card[]>(response));
      }
      if (searchResults.length === 0) {
        searchMessage = importMissing
          ? 'No se encontraron cartas en YGOProDeck con ese término.'
          : 'No está en tu catálogo local. Haz clic en "Importar de YGOProDeck".';
      }
    } catch (caught) {
      searchMessage = caught instanceof Error ? caught.message : 'Error al buscar cartas.';
    } finally {
      isSearching = false;
    }
  }

  function uniqueCards(cards: Card[]) {
    return [...new Map(cards.map((c) => [c.id, c])).values()];
  }

  function drawTestHand() {
    const pool: Card[] = [];
    draftEntries
      .filter((e) => e.section === 'main')
      .forEach((e) => {
        for (let i = 0; i < e.quantity; i++) {
          pool.push(e.card);
        }
      });

    if (pool.length < 5) {
      showFlash('El Main Deck necesita al menos 5 cartas para probar mano.', true);
      return;
    }

    // Shuffle Fisher-Yates
    for (let i = pool.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [pool[i], pool[j]] = [pool[j], pool[i]];
    }

    testHand = pool.slice(0, 5);
    rightTab = 'testHand';
  }

  async function saveDeck() {
    if (!deckName.trim()) {
      showFlash('Por favor escribe un nombre para el deck.', true);
      return;
    }
    isSaving = true;
    error = '';
    const body = JSON.stringify({
      name: deckName.trim(),
      description: deckDescription.trim() || null,
      cards: draftEntries.map((e) => ({
        card_id: e.card_id ?? e.card.id,
        quantity: e.quantity,
        section: e.section,
        preferred_print_id: e.preferred_print_id
      }))
    });

    try {
      const response = selectedDeck
        ? await apiFetch(`/api/decks/${selectedDeck.id}`, { method: 'PUT', body })
        : await apiFetch('/api/decks', { method: 'POST', body });
      const saved = await readJson<Deck>(response);
      await loadDecks(saved.id);
      showFlash('Deck guardado exitosamente.');
    } catch (caught) {
      showFlash(caught instanceof Error ? caught.message : 'Error al guardar el deck.', true);
    } finally {
      isSaving = false;
    }
  }

  async function deleteDeck() {
    if (!selectedDeck || !confirm(`¿Estás seguro de eliminar "${selectedDeck.name}"?`)) return;
    try {
      const response = await apiFetch(`/api/decks/${selectedDeck.id}`, { method: 'DELETE' });
      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload.detail || 'No fue posible eliminar el deck.');
      }
      selectedDeck = null;
      await loadDecks();
      showFlash('Deck eliminado.');
    } catch (caught) {
      showFlash(caught instanceof Error ? caught.message : 'Error al eliminar el deck.', true);
    }
  }

  async function handleImportDeck() {
    if (!importContent.trim()) {
      showFlash('Pega el código YDKe, archivo .ydk o JSON para importar.', true);
      return;
    }
    isImporting = true;
    error = '';
    try {
      const response = await apiFetch('/api/decks/import', {
        method: 'POST',
        body: JSON.stringify({
          name: importName.trim() || null,
          content: importContent.trim()
        })
      });
      const newDeck = await readJson<Deck>(response);
      isImportModalOpen = false;
      importContent = '';
      importName = '';
      await loadDecks(newDeck.id);
      selectDeck(newDeck);
      showFlash(`¡Deck "${newDeck.name}" importado con éxito!`);
    } catch (caught) {
      showFlash(caught instanceof Error ? caught.message : 'No fue posible importar el deck.', true);
    } finally {
      isImporting = false;
    }
  }

  function handleFileUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    if (!importName) {
      importName = file.name.replace(/\.[^/.]+$/, '');
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      importContent = (e.target?.result as string) || '';
    };
    reader.readAsText(file);
  }
</script>

<svelte:head>
  <title>Constructor de Decks | Duel Assistant</title>
</svelte:head>

{#if !isLoading && player}
  <AppShell active="decks" username={player.username} isAdmin={player.is_admin}>
    <!-- BARRA SUPERIOR / DECK MASTER BAR -->
    <header class="builder-bar">
      <div class="deck-selector-area">
        <select
          value={selectedDeck?.id ?? ''}
          on:change={(e) => {
            const id = Number(e.currentTarget.value);
            const found = decks.find((d) => d.id === id);
            if (found) selectDeck(found);
            else initNewDeck();
          }}
        >
          <option value="" disabled selected={!selectedDeck}>-- Seleccionar Deck --</option>
          {#each decks as deck (deck.id)}
            <option value={deck.id}>{deck.name} ({deck.card_entries.reduce((acc, c) => acc + c.quantity, 0)} cartas)</option>
          {/each}
        </select>
        <button class="btn-new" on:click={initNewDeck} title="Crear un deck desde cero">＋ Nuevo</button>
        <button class="btn-import" on:click={() => (isImportModalOpen = true)} title="Importar código YDKe, archivo .ydk o JSON">📥 Importar</button>
      </div>

      <div class="deck-title-area">
        <input
          class="deck-name-input"
          bind:value={deckName}
          placeholder="Nombre del deck..."
          maxlength="80"
        />
      </div>

      <div class="deck-stats-area">
        <div class="stat-pill" class:valid={mainTotal >= 40 && mainTotal <= 60} class:invalid={mainTotal < 40 || mainTotal > 60} title="Mínimo 40, Máximo 60">
          <span class="label">MAIN</span>
          <span class="count">{mainTotal}</span><span class="limit">/60</span>
        </div>
        <div class="stat-pill extra" class:invalid={extraTotal > 15} title="Máximo 15 cartas">
          <span class="label">EXTRA</span>
          <span class="count">{extraTotal}</span><span class="limit">/15</span>
        </div>
        <div class="stat-pill side" class:invalid={sideTotal > 15} title="Máximo 15 cartas">
          <span class="label">SIDE</span>
          <span class="count">{sideTotal}</span><span class="limit">/15</span>
        </div>
      </div>

      <div class="deck-actions-area">
        <button class="btn-test" on:click={drawTestHand} title="Probar mano inicial de 5 cartas">
          🃏 Mano
        </button>
        <button class="btn-save" on:click={saveDeck} disabled={isSaving}>
          {isSaving ? 'Guardando...' : '💾 Guardar'}
        </button>
        {#if selectedDeck}
          <button class="btn-delete" on:click={deleteDeck} title="Eliminar este deck">
            🗑️
          </button>
        {/if}
      </div>
    </header>

    <!-- NOTIFICACIONES TOAST -->
    {#if successNotification}
      <div class="toast success">{successNotification}</div>
    {/if}
    {#if error}
      <div class="toast error">{error}</div>
    {/if}

    <!-- ÁREA DE TRABAJO PRINCIPAL (SPLIT 2 PANELES) -->
    <main class="builder-workspace">
      <!-- PANEL IZQUIERDO: EL TAPETE / BANDEJA DE CARTAS -->
      <section class="deck-tray">
        <div class="tray-tabs">
          <button class:active={activeSectionView === 'all'} on:click={() => (activeSectionView = 'all')}>
            Todo ({totalCards})
          </button>
          <button class:active={activeSectionView === 'main'} on:click={() => (activeSectionView = 'main')}>
            Main Deck ({mainTotal})
          </button>
          <button class:active={activeSectionView === 'extra'} on:click={() => (activeSectionView = 'extra')}>
            Extra ({extraTotal})
          </button>
          <button class:active={activeSectionView === 'side'} on:click={() => (activeSectionView = 'side')}>
            Side ({sideTotal})
          </button>
        </div>

        <div class="tray-content">
          <!-- MAIN DECK -->
          {#if activeSectionView === 'all' || activeSectionView === 'main'}
            <div class="section-block">
              <div class="section-title">
                <h4>MAIN DECK <span>({mainTotal} cartas)</span></h4>
                <div class="category-summary">
                  <span class="badge mon">Monstruos: {mainMonsters}</span>
                  <span class="badge spell">Magias: {mainSpells}</span>
                  <span class="badge trap">Trampas: {mainTraps}</span>
                </div>
              </div>

              {#if mainEntries.length === 0}
                <div class="empty-zone">
                  <p>Arrastra o agrega cartas desde el catálogo a tu Main Deck (mínimo 40).</p>
                </div>
              {:else}
                <div class="cards-visual-grid">
                  {#each mainEntries as entry, index (`main-${entry.card_id ?? entry.card.id}-${index}`)}
                    <div
                      class="visual-card-wrapper {getCardFrameClass(entry.card)}"
                      class:selected={inspectingCard?.id === (entry.card_id ?? entry.card.id)}
                      on:click={() => inspectCard(entry.card)}
                      on:keydown={(e) => e.key === 'Enter' && inspectCard(entry.card)}
                      tabindex="0"
                      role="button"
                    >
                      <img src={entry.card.image_url_small || ''} alt={entry.card.name} loading="lazy" />
                      <span class="qty-badge">x{entry.quantity}</span>
                      <div class="quick-hover-controls">
                        <button on:click|stopPropagation={() => adjustQuantity(entry.card_id ?? entry.card.id, 1)} title="+1 copia">＋</button>
                        <button on:click|stopPropagation={() => adjustQuantity(entry.card_id ?? entry.card.id, -1)} title="-1 copia">−</button>
                        <button class="btn-side-move" on:click|stopPropagation={() => moveCardSection(entry.card_id ?? entry.card.id, 'side')} title="Mover a Side">S</button>
                      </div>
                      <span class="card-name-tooltip">{entry.card.name}</span>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}

          <!-- EXTRA DECK -->
          {#if activeSectionView === 'all' || activeSectionView === 'extra'}
            <div class="section-block extra-block">
              <div class="section-title">
                <h4>EXTRA DECK <span>({extraTotal} cartas / max 15)</span></h4>
                <span class="subtitle">Fusiones, Sincronías, Xyz y Enlace</span>
              </div>

              {#if extraEntries.length === 0}
                <div class="empty-zone">
                  <p>No hay cartas en el Extra Deck.</p>
                </div>
              {:else}
                <div class="cards-visual-grid">
                  {#each extraEntries as entry, index (`extra-${entry.card_id ?? entry.card.id}-${index}`)}
                    <div
                      class="visual-card-wrapper {getCardFrameClass(entry.card)}"
                      class:selected={inspectingCard?.id === (entry.card_id ?? entry.card.id)}
                      on:click={() => inspectCard(entry.card)}
                      on:keydown={(e) => e.key === 'Enter' && inspectCard(entry.card)}
                      tabindex="0"
                      role="button"
                    >
                      <img src={entry.card.image_url_small || ''} alt={entry.card.name} loading="lazy" />
                      <span class="qty-badge extra">x{entry.quantity}</span>
                      <div class="quick-hover-controls">
                        <button on:click|stopPropagation={() => adjustQuantity(entry.card_id ?? entry.card.id, 1)}>+</button>
                        <button on:click|stopPropagation={() => adjustQuantity(entry.card_id ?? entry.card.id, -1)}>−</button>
                        <button class="btn-side-move" on:click|stopPropagation={() => moveCardSection(entry.card_id ?? entry.card.id, 'side')} title="Mover a Side">S</button>
                      </div>
                      <span class="card-name-tooltip">{entry.card.name}</span>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}

          <!-- SIDE DECK -->
          {#if activeSectionView === 'all' || activeSectionView === 'side'}
            <div class="section-block side-block">
              <div class="section-title">
                <h4>SIDE DECK <span>({sideTotal} cartas / max 15)</span></h4>
                <span class="subtitle">Banquillo para rondas 2 y 3</span>
              </div>

              {#if sideEntries.length === 0}
                <div class="empty-zone">
                  <p>No hay cartas en el Side Deck.</p>
                </div>
              {:else}
                <div class="cards-visual-grid">
                  {#each sideEntries as entry, index (`side-${entry.card_id ?? entry.card.id}-${index}`)}
                    <div
                      class="visual-card-wrapper {getCardFrameClass(entry.card)}"
                      class:selected={inspectingCard?.id === (entry.card_id ?? entry.card.id)}
                      on:click={() => inspectCard(entry.card)}
                      on:keydown={(e) => e.key === 'Enter' && inspectCard(entry.card)}
                      tabindex="0"
                      role="button"
                    >
                      <img src={entry.card.image_url_small || ''} alt={entry.card.name} loading="lazy" />
                      <span class="qty-badge side">x{entry.quantity}</span>
                      <div class="quick-hover-controls">
                        <button on:click|stopPropagation={() => adjustQuantity(entry.card_id ?? entry.card.id, 1)}>+</button>
                        <button on:click|stopPropagation={() => adjustQuantity(entry.card_id ?? entry.card.id, -1)}>−</button>
                        <button class="btn-main-move" on:click|stopPropagation={() => moveCardSection(entry.card_id ?? entry.card.id, isExtraDeckCard(entry.card) ? 'extra' : 'main')} title="Mover a Main/Extra">M</button>
                      </div>
                      <span class="card-name-tooltip">{entry.card.name}</span>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        </div>
      </section>

      <!-- PANEL DERECHO: BUSCADOR / INSPECTOR / MANO -->
      <aside class="right-drawer">
        <div class="drawer-header-tabs">
          <button class:active={rightTab === 'catalog'} on:click={() => (rightTab = 'catalog')}>
            🔍 Catálogo
          </button>
          <button class:active={rightTab === 'inspector'} on:click={() => (rightTab = 'inspector')}>
            👁️ Inspector
          </button>
          <button class:active={rightTab === 'testHand'} on:click={() => (rightTab = 'testHand')}>
            🃏 Mano de prueba
          </button>
        </div>

        <div class="drawer-body">
          <!-- PESTAÑA 1: CATÁLOGO Y BÚSQUEDA -->
          {#if rightTab === 'catalog'}
            <div class="search-section">
              <div class="search-bar">
                <input
                  bind:value={search}
                  on:keydown={(e) => e.key === 'Enter' && findCards()}
                  placeholder="Escribe nombre o arquetipo..."
                />
                <button class="btn-search-local" on:click={() => findCards()} disabled={isSearching}>
                  {isSearching ? '...' : 'Buscar'}
                </button>
                <button class="btn-import-ygo" on:click={() => findCards(true)} disabled={isSearching} title="Buscar e importar desde YGOProDeck">
                  + Web
                </button>
              </div>

              <!-- FILTROS RÁPIDOS -->
              <div class="filter-pills">
                <button class:active={filterCategory === 'all'} on:click={() => (filterCategory = 'all')}>Todos</button>
                <button class:active={filterCategory === 'monster'} on:click={() => (filterCategory = 'monster')}>Monstruos</button>
                <button class:active={filterCategory === 'spell'} on:click={() => (filterCategory = 'spell')}>Magias</button>
                <button class:active={filterCategory === 'trap'} on:click={() => (filterCategory = 'trap')}>Trampas</button>
                <button class:active={filterCategory === 'extra'} on:click={() => (filterCategory = 'extra')}>Extra</button>
              </div>

              {#if searchMessage}
                <p class="search-hint">{searchMessage}</p>
              {/if}

              <!-- RESULTADOS DE BÚSQUEDA -->
              <div class="catalog-results-grid">
                {#each filteredSearchResults as card, index (`res-${card.id}-${index}`)}
                  <article class="catalog-card-item">
                    <img
                      src={card.image_url_small || ''}
                      alt={card.name}
                      on:click={() => inspectCard(card)}
                      on:keydown={(e) => e.key === 'Enter' && inspectCard(card)}
                      tabindex="0"
                      role="button"
                    />
                    <div class="catalog-card-info">
                      <strong title={card.name} on:click={() => inspectCard(card)}>{card.name}</strong>
                      <small>{card.card_type || 'Carta'}</small>
                      <div class="catalog-btn-group">
                        <button class="btn-add-main" on:click={() => addCard(card, isExtraDeckCard(card) ? 'extra' : 'main')}>
                          + {isExtraDeckCard(card) ? 'Extra' : 'Main'}
                        </button>
                        <button class="btn-add-side" on:click={() => addCard(card, 'side')} title="Agregar al Side Deck">
                          + Side
                        </button>
                      </div>
                    </div>
                  </article>
                {/each}

                {#if searchResults.length === 0 && !isSearching}
                  <div class="no-results">
                    <p>Usa la barra de arriba para buscar cartas en tu base local o importar de YGOProDeck.</p>
                  </div>
                {/if}
              </div>
            </div>

          <!-- PESTAÑA 2: INSPECTOR DE CARTA Y EDICIONES FÍSICAS -->
          {:else if rightTab === 'inspector'}
            {#if inspectingCard}
              <div class="inspector-section">
                <div class="inspector-card-view">
                  <img
                    src={inspectingCard.image_url || inspectingCard.image_url_small || ''}
                    alt={inspectingCard.name}
                    class="inspector-big-img"
                  />

                  <div class="inspector-details">
                    <h3>{inspectingCard.name}</h3>
                    <div class="meta-row">
                      {#if inspectingCard.attribute}
                        <span class="badge-attr">{inspectingCard.attribute}</span>
                      {/if}
                      {#if inspectingCard.level}
                        <span class="badge-level">⭐ {inspectingCard.level}</span>
                      {/if}
                      <span class="badge-type">{inspectingCard.card_type}</span>
                    </div>

                    {#if inspectingCard.atk !== null && inspectingCard.atk !== undefined}
                      <div class="stats-row">
                        <span>ATK: <strong>{inspectingCard.atk}</strong></span>
                        {#if inspectingCard.def_ !== null && inspectingCard.def_ !== undefined}
                          <span>DEF: <strong>{inspectingCard.def_}</strong></span>
                        {/if}
                      </div>
                    {/if}

                    <div class="desc-box">
                      <p>{inspectingCard.description || 'Sin descripción.'}</p>
                    </div>

                    <!-- CONTROL EN EL DECK ACTUAL -->
                    <div class="deck-control-card">
                      {#if inspectingEntry}
                        <div class="entry-status">
                          <span>En el deck: <strong>{inspectingEntry.quantity}x</strong> ({inspectingEntry.section.toUpperCase()} DECK)</span>
                        </div>

                        <div class="control-buttons">
                          <button on:click={() => adjustQuantity(inspectingCard.id, 1)} disabled={inspectingEntry.quantity >= 3}>+1 Copia</button>
                          <button on:click={() => adjustQuantity(inspectingCard.id, -1)}>-1 Copia</button>
                          <button class="btn-danger" on:click={() => removeCard(inspectingCard.id)}>Quitar</button>
                        </div>

                        <!-- SELECTOR DE IMPRESIÓN FÍSICA -->
                        <div class="prints-selector">
                          <label>Impresión física preferida:</label>
                          <select
                            value={inspectingEntry.preferred_print_id ?? ''}
                            on:change={(e) => updatePreferredPrint(inspectingCard.id, e.currentTarget.value ? Number(e.currentTarget.value) : null)}
                          >
                            <option value="">Cualquier edición</option>
                            {#each inspectingCard.prints as print (print.id)}
                              <option value={print.id}>{print.set_code} · {print.rarity || 'Sin rareza'} {print.price ? `($${print.price})` : ''}</option>
                            {/each}
                          </select>
                        </div>
                      {:else}
                        <div class="not-in-deck">
                          <p>Esta carta no está en tu deck actual.</p>
                          <button class="btn-primary-add" on:click={() => addCard(inspectingCard)}>
                            ＋ Agregar a {isExtraDeckCard(inspectingCard) ? 'Extra Deck' : 'Main Deck'}
                          </button>
                        </div>
                      {/if}
                    </div>
                  </div>
                </div>
              </div>
            {:else}
              <div class="empty-inspector">
                <p>Haz clic en cualquier carta de tu deck o del catálogo para inspeccionar su efecto, estadísticas y elegir su edición física.</p>
              </div>
            {/if}

          <!-- PESTAÑA 3: MANO DE PRUEBA -->
          {:else if rightTab === 'testHand'}
            <div class="test-hand-section">
              <div class="test-hand-header">
                <h4>Mano Inicial (5 cartas)</h4>
                <button class="btn-mulligan" on:click={drawTestHand}>🔄 Barajar y robar otra</button>
              </div>

              {#if testHand.length === 0}
                <div class="empty-zone">
                  <p>Presiona "Barajar y robar" para probar una mano de 5 cartas de tu Main Deck.</p>
                </div>
              {:else}
                <div class="test-hand-cards">
                  {#each testHand as card, idx (`hand-${card.id}-${idx}`)}
                    <button type="button" class="hand-card" on:click={() => inspectCard(card)}>
                      <img src={card.image_url || card.image_url_small} alt={card.name} />
                      <strong>{card.name}</strong>
                    </button>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        </div>
      </aside>
    </main>

    <!-- MODAL DE IMPORTACIÓN -->
    {#if isImportModalOpen}
      <div class="modal-overlay" on:click={() => (isImportModalOpen = false)} role="presentation">
        <div class="modal-card" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div class="modal-head">
            <h3 id="modal-title">📥 Importar Deck</h3>
            <button class="btn-close" on:click={() => (isImportModalOpen = false)}>×</button>
          </div>
          <p class="modal-lead">
            Pega directamente un código <strong>YDKe</strong> (<code>ydke://...</code>), el texto de un archivo <strong>.YDK</strong> o un <strong>JSON</strong> de YGOPRODeck / DuelingBook / Master Duel. Las cartas que no existan en tu base de datos se descargarán automáticamente con sus imágenes y rarezas.
          </p>

          <label class="modal-label">
            <span>Nombre del deck (opcional):</span>
            <input bind:value={importName} placeholder="Ej. Branded Despia" />
          </label>

          <label class="modal-label">
            <span>O subir archivo (.ydk o .json):</span>
            <input type="file" accept=".ydk,.json,.txt" on:change={handleFileUpload} />
          </label>

          <label class="modal-label">
            <span>Código YDKe o texto del deck:</span>
            <textarea
              bind:value={importContent}
              placeholder="Pega aquí tu código ydke://... o el contenido de tu deck"
              rows="6"
            ></textarea>
          </label>

          <div class="modal-actions">
            <button class="btn-cancel" on:click={() => (isImportModalOpen = false)} disabled={isImporting}>Cancelar</button>
            <button class="btn-submit-import" on:click={handleImportDeck} disabled={isImporting}>
              {isImporting ? 'Descargando cartas e importando...' : 'Importar Deck'}
            </button>
          </div>
        </div>
      </div>
    {/if}
  </AppShell>
{/if}

<style>
  /* MODAL DE IMPORTACIÓN */
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(8, 14, 10, 0.85);
    display: grid;
    place-items: center;
    z-index: 1200;
    padding: 20px;
  }
  .modal-card {
    background: #17221a;
    border: 1px solid #364d3b;
    width: 100%;
    max-width: 580px;
    padding: 24px;
    border-radius: 6px;
    box-shadow: 0 16px 40px rgba(0,0,0,0.6);
    display: grid;
    gap: 16px;
  }
  .modal-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #283a2c;
    padding-bottom: 12px;
  }
  .modal-head h3 {
    margin: 0;
    font-size: 18px;
    font-family: 'DM Mono', monospace;
    color: #eef2e8;
  }
  .btn-close {
    background: transparent;
    border: 0;
    color: #8c9e8e;
    font-size: 20px;
    cursor: pointer;
  }
  .btn-close:hover { color: #fff; }
  .modal-lead {
    font-size: 12px;
    color: #a2b5a4;
    line-height: 1.5;
    margin: 0;
  }
  .modal-lead strong { color: #f5bb68; }
  .modal-lead code { background: #0f1611; padding: 2px 5px; border-radius: 3px; color: #d9573b; font-family: 'DM Mono', monospace; }
  .modal-label {
    display: grid;
    gap: 6px;
    font: 11px 'DM Mono', monospace;
    color: #8fa391;
    text-transform: uppercase;
  }
  .modal-label input, .modal-label textarea {
    background: #101812;
    border: 1px solid #2c4232;
    color: #fff;
    padding: 10px;
    font: 13px 'Space Grotesk', sans-serif;
  }
  .modal-label textarea {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    resize: vertical;
  }
  .modal-label input:focus, .modal-label textarea:focus {
    outline: none;
    border-color: #d9573b;
  }
  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 8px;
  }
  .btn-cancel {
    background: transparent;
    border: 1px solid #374f3d;
    color: #8da190;
    padding: 10px 16px;
    cursor: pointer;
    font: 12px 'DM Mono', monospace;
  }
  .btn-submit-import {
    background: #d9573b;
    border: 0;
    color: #fff;
    padding: 10px 20px;
    cursor: pointer;
    font: 12px 'DM Mono', monospace;
    font-weight: 700;
  }
  .btn-submit-import:disabled { opacity: 0.6; cursor: wait; }
  .btn-import {
    background: #2b3d30;
    color: #f5bb68;
    border: 1px solid #435e4a;
    padding: 8px 12px;
    font: 12px 'DM Mono', monospace;
    cursor: pointer;
    font-weight: 600;
  }
  .btn-import:hover { background: #385240; color: #fff; }
  /* BARRA SUPERIOR DEL BUILDER */
  .builder-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 16px;
    background: #101812;
    padding: 14px 22px;
    border-bottom: 2px solid #283a2c;
    color: #eef2e8;
    box-shadow: 0 4px 18px rgba(0,0,0,0.3);
  }

  .deck-selector-area {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .deck-selector-area select {
    background: #1a261e;
    color: #eef2e8;
    border: 1px solid #334a38;
    padding: 8px 12px;
    font: 13px 'DM Mono', monospace;
    max-width: 220px;
    cursor: pointer;
  }

  .btn-new {
    background: #233428;
    color: #92b896;
    border: 1px solid #334a38;
    padding: 8px 12px;
    font: 12px 'DM Mono', monospace;
    cursor: pointer;
    font-weight: 600;
  }
  .btn-new:hover { background: #2f4736; color: #fff; }

  .deck-title-area {
    flex: 1;
    min-width: 220px;
  }

  .deck-name-input {
    width: 100%;
    background: transparent;
    border: 0;
    border-bottom: 2px solid #3d5442;
    color: #fff;
    font-size: 20px;
    font-weight: 700;
    font-family: 'Space Grotesk', sans-serif;
    padding: 4px 6px;
    transition: border-color .2s;
  }
  .deck-name-input:focus {
    outline: none;
    border-color: #d9573b;
  }

  .deck-stats-area {
    display: flex;
    gap: 8px;
  }

  .stat-pill {
    display: flex;
    align-items: baseline;
    gap: 4px;
    background: #17211b;
    border: 1px solid #334a38;
    padding: 5px 10px;
    border-radius: 4px;
    font-family: 'DM Mono', monospace;
  }
  .stat-pill .label { font-size: 10px; color: #879989; font-weight: 700; }
  .stat-pill .count { font-size: 16px; font-weight: 700; color: #fff; }
  .stat-pill .limit { font-size: 11px; color: #617363; }
  .stat-pill.valid .count { color: #58c772; }
  .stat-pill.invalid { border-color: #a83428; }
  .stat-pill.invalid .count { color: #ff6854; }
  .stat-pill.extra .label { color: #bb86dc; }
  .stat-pill.side .label { color: #72afdd; }

  .deck-actions-area {
    display: flex;
    gap: 8px;
  }

  .btn-test {
    background: #253328;
    color: #d0ded1;
    border: 1px solid #3c5441;
    padding: 8px 14px;
    cursor: pointer;
    font: 12px 'DM Mono', monospace;
    font-weight: 600;
  }
  .btn-test:hover { background: #324737; color: #fff; }

  .btn-save {
    background: #d9573b;
    color: #fff;
    border: 0;
    padding: 8px 18px;
    cursor: pointer;
    font: 12px 'DM Mono', monospace;
    font-weight: 700;
    text-transform: uppercase;
  }
  .btn-save:hover { background: #c2462c; }
  .btn-save:disabled { opacity: 0.6; cursor: wait; }

  .btn-delete {
    background: #471d18;
    color: #f79d92;
    border: 1px solid #6b2b23;
    padding: 8px 12px;
    cursor: pointer;
  }
  .btn-delete:hover { background: #69241c; color: #fff; }

  /* NOTIFICACIONES TOAST */
  .toast {
    position: fixed;
    top: 75px;
    right: 25px;
    z-index: 1000;
    padding: 12px 18px;
    font: 12px 'DM Mono', monospace;
    border-radius: 4px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    animation: fadeIn .2s ease;
  }
  .toast.success { background: #1c4224; color: #b7e8c1; border: 1px solid #2e693b; }
  .toast.error { background: #571714; color: #fcc2bc; border: 1px solid #852b27; }

  /* WORKSPACE GRID */
  .builder-workspace {
    display: grid;
    grid-template-columns: 1fr 380px;
    gap: 0;
    min-height: calc(100vh - 140px);
    background: #141c16;
  }

  /* PANEL IZQUIERDO: BANDEJA DE CARTAS */
  .deck-tray {
    padding: 20px;
    border-right: 1px solid #28382c;
    overflow-y: auto;
  }

  .tray-tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
    border-bottom: 1px solid #28382c;
    padding-bottom: 12px;
  }

  .tray-tabs button {
    background: #1a261e;
    color: #8c9e8e;
    border: 1px solid #28382c;
    padding: 8px 14px;
    cursor: pointer;
    font: 12px 'DM Mono', monospace;
  }
  .tray-tabs button.active {
    background: #d9573b;
    color: #fff;
    border-color: #d9573b;
    font-weight: 700;
  }

  .section-block {
    margin-bottom: 30px;
    background: #18221a;
    border: 1px solid #263628;
    padding: 16px;
    border-radius: 6px;
  }
  .section-block.extra-block { border-top: 3px solid #8a58a6; }
  .section-block.side-block { border-top: 3px solid #3e7ca6; }

  .section-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #263628;
    padding-bottom: 10px;
    margin-bottom: 14px;
  }

  .section-title h4 {
    margin: 0;
    font-size: 15px;
    font-family: 'DM Mono', monospace;
    letter-spacing: .05em;
    color: #eef2e8;
  }
  .section-title h4 span { color: #f5bb68; font-weight: normal; }
  .subtitle { font: 11px 'DM Mono', monospace; color: #7f9181; }

  .category-summary {
    display: flex;
    gap: 6px;
  }
  .category-summary .badge {
    font: 10px 'DM Mono', monospace;
    padding: 2px 7px;
    border-radius: 2px;
  }
  .badge.mon { background: #3b2814; color: #ebb27a; }
  .badge.spell { background: #133827; color: #78e0ab; }
  .badge.trap { background: #3b1427; color: #e880b4; }

  .empty-zone {
    padding: 30px;
    text-align: center;
    border: 1px dashed #304233;
    color: #697a6c;
    font: 12px 'DM Mono', monospace;
    border-radius: 4px;
  }

  /* GRID DE MINIATURAS VISUALES */
  .cards-visual-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(78px, 1fr));
    gap: 10px;
  }

  .visual-card-wrapper {
    position: relative;
    aspect-ratio: 42 / 60;
    border-radius: 3px;
    cursor: pointer;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.4);
    transition: transform .15s ease, box-shadow .15s ease, border-color .15s;
    border: 2px solid transparent;
  }
  .visual-card-wrapper:hover {
    transform: translateY(-4px) scale(1.05);
    z-index: 10;
    box-shadow: 0 6px 14px rgba(0,0,0,0.6);
  }
  .visual-card-wrapper.selected {
    border-color: #f5bb68;
    box-shadow: 0 0 10px #f5bb6899;
  }

  .visual-card-wrapper img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    background: #1e2a21;
  }

  .qty-badge {
    position: absolute;
    top: 4px;
    right: 4px;
    background: #d9573b;
    color: #fff;
    font: 700 11px 'DM Mono', monospace;
    padding: 1px 5px;
    border-radius: 2px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.7);
    pointer-events: none;
  }
  .qty-badge.extra { background: #8a58a6; }
  .qty-badge.side { background: #3e7ca6; }

  /* BORDES TEMÁTICOS */
  .frame-monster { border-color: #7d4d23; }
  .frame-spell { border-color: #1a6e4d; }
  .frame-trap { border-color: #8c2555; }
  .frame-fusion { border-color: #633085; }
  .frame-synchro { border-color: #c9c9c9; }
  .frame-xyz { border-color: #1c1c1c; }
  .frame-link { border-color: #1a4f80; }

  .quick-hover-controls {
    position: absolute;
    inset: 0;
    background: rgba(16, 24, 18, 0.85);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 4px;
    opacity: 0;
    transition: opacity .15s ease;
  }
  .visual-card-wrapper:hover .quick-hover-controls {
    opacity: 1;
  }

  .quick-hover-controls button {
    background: #2d4233;
    color: #fff;
    border: 1px solid #4a6651;
    width: 28px;
    height: 24px;
    font: 13px 'DM Mono', monospace;
    cursor: pointer;
    border-radius: 2px;
    display: grid;
    place-items: center;
  }
  .quick-hover-controls button:hover { background: #d9573b; border-color: #d9573b; }
  .quick-hover-controls .btn-side-move { background: #2b4961; border-color: #437194; font-size: 10px; }
  .quick-hover-controls .btn-main-move { background: #4a3424; border-color: #70523b; font-size: 10px; }

  .card-name-tooltip {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(0,0,0,0.85);
    color: #fff;
    font-size: 8px;
    padding: 2px 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    pointer-events: none;
  }

  /* PANEL DERECHO / DRAWER */
  .right-drawer {
    background: #111a14;
    border-left: 1px solid #28382c;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }

  .drawer-header-tabs {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    border-bottom: 1px solid #28382c;
  }

  .drawer-header-tabs button {
    background: #17211b;
    color: #8c9e8e;
    border: 0;
    border-bottom: 2px solid transparent;
    padding: 12px 6px;
    cursor: pointer;
    font: 11px 'DM Mono', monospace;
    transition: all .2s;
  }
  .drawer-header-tabs button.active {
    background: #1e2c22;
    color: #f5bb68;
    border-bottom-color: #f5bb68;
    font-weight: 700;
  }

  .drawer-body {
    padding: 16px;
    flex: 1;
  }

  /* BUSCADOR Y CATÁLOGO */
  .search-bar {
    display: flex;
    gap: 6px;
    margin-bottom: 12px;
  }

  .search-bar input {
    flex: 1;
    background: #1a261e;
    border: 1px solid #314535;
    color: #fff;
    padding: 9px 12px;
    font-size: 13px;
  }
  .search-bar input:focus { outline: none; border-color: #d9573b; }

  .btn-search-local {
    background: #d9573b;
    color: #fff;
    border: 0;
    padding: 0 12px;
    cursor: pointer;
    font: 11px 'DM Mono', monospace;
    font-weight: 600;
  }
  .btn-import-ygo {
    background: #2f4736;
    color: #b5dab8;
    border: 1px solid #43664c;
    padding: 0 10px;
    cursor: pointer;
    font: 11px 'DM Mono', monospace;
  }

  .filter-pills {
    display: flex;
    gap: 4px;
    margin-bottom: 14px;
    overflow-x: auto;
    padding-bottom: 4px;
  }
  .filter-pills button {
    background: #1a261e;
    color: #7b8e7d;
    border: 1px solid #28382c;
    padding: 4px 8px;
    font: 10px 'DM Mono', monospace;
    cursor: pointer;
    white-space: nowrap;
  }
  .filter-pills button.active {
    background: #394f3e;
    color: #fff;
    border-color: #55755c;
  }

  .search-hint {
    color: #d1b87d;
    font: 11px 'DM Mono', monospace;
    background: #2a281c;
    padding: 8px;
    margin-bottom: 12px;
    border-left: 2px solid #f5bb68;
  }

  .catalog-results-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: calc(100vh - 280px);
    overflow-y: auto;
  }

  .catalog-card-item {
    display: flex;
    align-items: center;
    gap: 10px;
    background: #17211b;
    border: 1px solid #2a3a2d;
    padding: 6px 8px;
    border-radius: 4px;
  }
  .catalog-card-item img {
    width: 38px;
    height: 55px;
    object-fit: cover;
    background: #253327;
    cursor: pointer;
    flex-shrink: 0;
  }
  .catalog-card-info {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .catalog-card-info strong {
    font-size: 12px;
    color: #eef2e8;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    cursor: pointer;
  }
  .catalog-card-info strong:hover { color: #f5bb68; }
  .catalog-card-info small {
    font-size: 10px;
    color: #829484;
  }

  .catalog-btn-group {
    display: flex;
    gap: 6px;
    margin-top: 4px;
  }
  .btn-add-main, .btn-add-side {
    padding: 3px 8px;
    font: 10px 'DM Mono', monospace;
    border: 0;
    cursor: pointer;
  }
  .btn-add-main { background: #d9573b; color: #fff; font-weight: 600; }
  .btn-add-side { background: #2f4736; color: #b7e0bb; }
  .no-results {
    text-align: center;
    color: #697a6c;
    padding: 30px;
    font: 12px 'DM Mono', monospace;
  }

  /* INSPECTOR DE CARTA */
  .inspector-card-view {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
  }
  .inspector-big-img {
    width: 170px;
    aspect-ratio: 42 / 60;
    object-fit: cover;
    box-shadow: 0 8px 24px rgba(0,0,0,0.6);
    border: 2px solid #384d3c;
    border-radius: 4px;
  }
  .inspector-details {
    width: 100%;
  }
  .inspector-details h3 {
    margin: 0 0 6px;
    font-size: 16px;
    color: #fff;
  }
  .meta-row {
    display: flex;
    gap: 6px;
    margin-bottom: 10px;
    flex-wrap: wrap;
  }
  .badge-attr, .badge-level, .badge-type {
    font: 10px 'DM Mono', monospace;
    padding: 2px 6px;
    background: #202d24;
    color: #c9dbc9;
    border-radius: 2px;
  }
  .badge-level { color: #f5bb68; font-weight: 700; }

  .stats-row {
    display: flex;
    gap: 14px;
    font: 12px 'DM Mono', monospace;
    color: #a4b5a6;
    margin-bottom: 10px;
    background: #17211b;
    padding: 6px 10px;
    border-left: 2px solid #d9573b;
  }
  .stats-row strong { color: #fff; font-size: 14px; }

  .desc-box {
    max-height: 150px;
    overflow-y: auto;
    background: #151e17;
    border: 1px solid #233125;
    padding: 10px;
    font-size: 12px;
    line-height: 1.4;
    color: #b7c4b8;
    margin-bottom: 14px;
    border-radius: 4px;
  }

  .deck-control-card {
    background: #1a261e;
    border: 1px solid #2f4433;
    padding: 12px;
    border-radius: 4px;
  }
  .entry-status {
    font: 11px 'DM Mono', monospace;
    color: #d1ded2;
    margin-bottom: 8px;
  }
  .entry-status strong { color: #f5bb68; }

  .control-buttons {
    display: flex;
    gap: 6px;
    margin-bottom: 12px;
  }
  .control-buttons button {
    flex: 1;
    background: #2c3f31;
    color: #fff;
    border: 0;
    padding: 7px 0;
    cursor: pointer;
    font: 11px 'DM Mono', monospace;
  }
  .control-buttons button:hover { background: #3b5442; }
  .control-buttons .btn-danger { background: #571e19; color: #ffa89e; }
  .control-buttons .btn-danger:hover { background: #73261f; }

  .prints-selector {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .prints-selector label {
    font: 10px 'DM Mono', monospace;
    color: #8c9e8e;
    text-transform: uppercase;
  }
  .prints-selector select {
    background: #141c16;
    color: #fff;
    border: 1px solid #334a38;
    padding: 6px;
    font: 11px 'DM Mono', monospace;
  }

  .not-in-deck {
    text-align: center;
    color: #88998a;
    font: 11px 'DM Mono', monospace;
  }
  .btn-primary-add {
    width: 100%;
    margin-top: 8px;
    background: #d9573b;
    color: #fff;
    border: 0;
    padding: 10px;
    cursor: pointer;
    font: 12px 'DM Mono', monospace;
    font-weight: 700;
  }

  .empty-inspector {
    padding: 40px 20px;
    text-align: center;
    color: #697a6c;
    font: 12px 'DM Mono', monospace;
    line-height: 1.6;
  }

  /* TEST HAND SIMULATOR */
  .test-hand-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
  }
  .test-hand-header h4 { margin: 0; font-size: 14px; font-family: 'DM Mono', monospace; color: #fff; }
  .btn-mulligan {
    background: #283a2d;
    color: #a6c9ab;
    border: 1px solid #3c5441;
    padding: 6px 10px;
    font: 10px 'DM Mono', monospace;
    cursor: pointer;
  }
  .btn-mulligan:hover { background: #354f3c; color: #fff; }

  .test-hand-cards {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }
  .hand-card {
    background: #17211b;
    border: 1px solid #2b3b2d;
    padding: 6px;
    border-radius: 4px;
    cursor: pointer;
    text-align: center;
  }
  .hand-card img {
    width: 100%;
    aspect-ratio: 42 / 60;
    object-fit: cover;
    margin-bottom: 4px;
  }
  .hand-card strong {
    display: block;
    font-size: 10px;
    color: #eef2e8;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  @media(max-width: 950px) {
    .builder-workspace {
      grid-template-columns: 1fr;
    }
    .right-drawer {
      border-left: 0;
      border-top: 1px solid #28382c;
      max-height: 500px;
    }
    .builder-bar {
      flex-direction: column;
      align-items: stretch;
    }
    .deck-stats-area {
      justify-content: space-between;
    }
  }
</style>
