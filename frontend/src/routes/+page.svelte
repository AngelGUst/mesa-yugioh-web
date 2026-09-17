<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import AppShell from '$lib/components/AppShell.svelte';

  onMount(() => {
    if (!localStorage.getItem('duel_session')) {
      goto('/login');
    }
  });
</script>

<svelte:head><title>Inicio | Duel Assistant</title></svelte:head>

<AppShell active="home">
  <header class="page-head"><div><p class="eyebrow">Mi mesa · 17 sep 2026</p><h1>Hola, Ángel<span>.</span></h1></div><span class="online"><i></i> API conectada</span></header>
  <section class="welcome"><div><p class="eyebrow">Panel de juego</p><h2>Tu partida,<br /><em>bajo control.</em></h2><p>Registra puntos de vida, turnos y acciones sin perder el ritmo del duelo físico.</p></div><a class="start" href="/duel/new">＋ Crear nuevo duelo <span>→</span></a></section>
  <div class="section-title"><h3>Mis duelos activos</h3><a href="/duel/new">Ver todos →</a></div>
  <section class="duel-list"><article class="duel-card active-card"><div class="card-top"><span class="live"><i></i> En curso</span><small>hace 4 min</small></div><div class="match"><div><strong>Ángel</strong><b>6,500 LP</b></div><span>VS</span><div><strong>Axel</strong><b>7,200 LP</b></div></div><div class="card-bottom"><span>Turno 8 · Main Phase 1</span><a href="/duel/demo">Continuar duelo <span>→</span></a></div></article><article class="duel-card waiting-card"><div class="card-top"><span class="waiting">Esperando oponente</span><small>hace 12 min</small></div><div class="waiting-body"><strong>DUEL-4P9X</strong><p>Comparte el codigo para comenzar.</p></div><div class="card-bottom"><span>Sala privada</span><a href="/duel/new">Ver sala <span>→</span></a></div></article></section>
  <div class="section-title"><h3>Resumen</h3><a href="/decks">Gestionar decks →</a></div>
  <section class="stats"><article><small>Victorias</small><strong>0</strong><span>Primera partida pendiente</span></article><article><small>Duelo mas reciente</small><strong>—</strong><span>Aun no hay historial</span></article><article class="warm"><small>Mis decks</small><strong>2</strong><span>Listos para jugar</span></article></section>
</AppShell>

<style>
  .content{background:#f2f3ed}.page-head{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:35px}.page-head h1{font-size:clamp(40px,5vw,66px);letter-spacing:-.07em;margin:8px 0 0}.page-head h1 span,.welcome em{color:#d9573b;font-style:normal}.eyebrow{color:#d9573b;font:11px 'DM Mono',monospace;text-transform:uppercase;letter-spacing:.08em;margin:0}.online{font:10px 'DM Mono',monospace;color:#637064}.online i,.live i{display:inline-block;width:7px;height:7px;border-radius:50%;background:#569b62;margin-right:7px}.welcome{display:flex;justify-content:space-between;align-items:end;background:#17211b;color:#f7f4e9;padding:34px 38px;margin-bottom:40px;min-height:220px}.welcome h2{font-size:clamp(38px,5vw,62px);letter-spacing:-.07em;line-height:.92;margin:12px 0}.welcome p:not(.eyebrow){max-width:380px;color:#b2c0b0;line-height:1.5;margin-bottom:0}.start,.duel-card a{background:#d9573b;color:#fff;padding:14px 17px;font-size:13px}.start span,.duel-card a span{margin-left:20px}.section-title{display:flex;justify-content:space-between;align-items:center;margin:0 0 15px}.section-title h3{font-size:18px;margin:0}.section-title a{color:#d9573b;font:11px 'DM Mono',monospace}.duel-list,.stats{display:grid;grid-template-columns:1.35fr 1fr;gap:13px;margin-bottom:40px}.duel-card{padding:20px;background:#fffdf7;border:1px solid #dbe1d8}.active-card{background:#17211b;color:#f7f4e9;border:0}.card-top,.card-bottom{display:flex;justify-content:space-between;align-items:center;font:10px 'DM Mono',monospace;color:#899789}.active-card .card-top{color:#a6b5a4}.live{color:#70bd7a}.waiting{color:#d9573b}.match{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;text-align:center;gap:15px;padding:27px 0}.match div:first-child{text-align:left}.match div:last-child{text-align:right}.match strong{display:block;font-size:17px}.match b{display:block;color:#e66b4e;font:17px 'DM Mono',monospace;margin-top:6px}.match>span{color:#f0b75f;font:11px 'DM Mono',monospace}.card-bottom{border-top:1px solid #35443a;padding-top:15px}.card-bottom a{padding:0;background:none;color:#e66b4e}.waiting-card .card-bottom{border-color:#dbe1d8}.waiting-body{padding:27px 0}.waiting-body strong{font:22px 'DM Mono',monospace;letter-spacing:.05em}.waiting-body p{color:#637064;font-size:13px}.stats{grid-template-columns:repeat(3,1fr)}.stats article{background:#fffdf7;border:1px solid #dbe1d8;padding:20px;min-height:130px}.stats .warm{background:#f1e4d1;border-color:#e4d3bb}.stats small,.stats span{display:block;color:#637064;font:10px 'DM Mono',monospace}.stats strong{display:block;font:44px 'DM Mono',monospace;margin:16px 0 5px}@media(max-width:720px){.welcome{display:block;padding:26px}.start{display:inline-block;margin-top:25px}.duel-list,.stats{grid-template-columns:1fr}.page-head{align-items:start;gap:15px;flex-direction:column}}
</style>
