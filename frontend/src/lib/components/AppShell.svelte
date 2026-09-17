<script lang="ts">
  export let active = 'home';
</script>

<div class="app-shell">
  <aside class="sidebar">
    <a class="brand" href="/" aria-label="Duel Assistant">
      <span class="brand-mark">DA</span>
      <span>Duel<br /><b>Assistant</b></span>
    </a>
    <div class="side-label">Mesa de juego</div>
    <nav>
      <a class:active={active === 'home'} href="/">⌂ <span>Inicio</span></a>
      <a class:active={active === 'duels'} href="/duel/new">＋ <span>Nuevo duelo</span></a>
      <a class:active={active === 'decks'} href="/decks">▣ <span>Mis decks</span></a>
    </nav>
    <div class="side-spacer"></div>
    <div class="profile-mini"><span class="avatar">A</span><span><b>angel</b><small>Jugador local</small></span><a href="/login" aria-label="Salir">↗</a></div>
  </aside>
  <main class="content"><slot /></main>
</div>
