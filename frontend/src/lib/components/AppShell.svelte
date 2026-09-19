<script lang="ts">
  import { goto } from '$app/navigation';

  export let active = 'home';
  export let username = 'Jugador';
  export let isAdmin = false;

  function logout() {
    localStorage.removeItem('duel_session');
    goto('/login');
  }
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
    <div class="profile-mini"><span class="avatar">{username.slice(0, 1).toUpperCase()}</span><span><b>{username}</b><small>{isAdmin ? 'Administrador' : 'Jugador'}</small></span><button on:click={logout} aria-label="Salir">↗</button></div>
  </aside>
  <main class="content"><slot /></main>
</div>
