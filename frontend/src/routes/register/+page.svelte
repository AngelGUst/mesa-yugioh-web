<script lang="ts">
  import { goto } from '$app/navigation';

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  let username = '';
  let email = '';
  let password = '';
  let confirmPassword = '';
  let error = '';
  let isSubmitting = false;

  async function createAccount() {
    error = '';

    if (password !== confirmPassword) {
      error = 'Las contraseñas no coinciden.';
      return;
    }

    isSubmitting = true;

    try {
      const registerResponse = await fetch(`${apiUrl}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password })
      });
      const registerPayload = await registerResponse.json();

      if (!registerResponse.ok) {
        error = registerPayload.detail || 'No fue posible crear la cuenta.';
        return;
      }

      const loginResponse = await fetch(`${apiUrl}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const loginPayload = await loginResponse.json();

      if (!loginResponse.ok) {
        error = 'La cuenta fue creada, pero no fue posible iniciar sesion. Intentalo desde la pantalla de acceso.';
        return;
      }

      localStorage.setItem('duel_session', loginPayload.access_token);
      goto('/');
    } catch {
      error = 'No fue posible conectar con el servidor. Intentalo de nuevo.';
    } finally {
      isSubmitting = false;
    }
  }
</script>

<svelte:head><title>Crear cuenta | Duel Assistant</title></svelte:head>

<div class="auth-page">
  <div class="auth-art"><a class="auth-brand" href="/">DA / DUEL ASSISTANT</a><div><p class="eyebrow">Tu mesa. Tu registro. Tu duelo.</p><h1>Prepara tu deck.<br /><em>Inicia tu historia.</em></h1></div><span class="art-note">01 / NUEVO JUGADOR</span></div>
  <form class="auth-form" on:submit|preventDefault={createAccount}>
    <div><p class="eyebrow">Nueva cuenta</p><h2>Crear cuenta</h2><p class="muted">Tu cuenta se crea con el rol de jugador.</p></div>
    <label>Usuario<input bind:value={username} type="text" autocomplete="username" minlength="3" maxlength="50" placeholder="angel" required /></label>
    <label>Email<input bind:value={email} type="email" autocomplete="email" placeholder="tu@email.com" required /></label>
    <label>Contraseña<input bind:value={password} type="password" autocomplete="new-password" minlength="8" maxlength="128" placeholder="Mínimo 8 caracteres" required /></label>
    <label>Confirmar contraseña<input bind:value={confirmPassword} type="password" autocomplete="new-password" minlength="8" maxlength="128" placeholder="Repite tu contraseña" required /></label>
    {#if error}<p class="form-error" role="alert">{error}</p>{/if}
    <button class="button full" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Creando cuenta...' : 'Crear cuenta'} <span>↗</span></button>
    <p class="switch">¿Ya tienes cuenta? <a href="/login">Inicia sesion</a></p>
  </form>
</div>

<style>
  .auth-page{min-height:100vh;display:grid;grid-template-columns:1.15fr .85fr;background:#f2f3ed}.auth-art{padding:34px clamp(28px,7vw,100px);display:flex;flex-direction:column;justify-content:space-between;background:#17211b;color:#f6f4e9}.auth-brand{font:500 12px 'DM Mono',monospace;letter-spacing:.12em}.auth-art h1{font-size:clamp(48px,6vw,92px);line-height:.94;letter-spacing:-.07em;margin:18px 0}.auth-art em{color:#e66b4e;font-style:normal}.auth-art .eyebrow{color:#aab9a2}.art-note{font:11px 'DM Mono',monospace;color:#829181}.auth-form{width:min(390px,calc(100% - 48px));margin:auto;display:grid;gap:20px}.auth-form h2{font-size:48px;letter-spacing:-.06em;margin:0 0 8px}.muted{color:#68766a;margin:0;line-height:1.5}.auth-form label{display:grid;gap:8px;color:#536257;font:11px 'DM Mono',monospace;text-transform:uppercase;letter-spacing:.06em}.auth-form input{width:100%;border:1px solid #ccd5c8;background:#fff;padding:15px;font:15px 'Space Grotesk',sans-serif;outline:none}.auth-form input:focus{border-color:#d9573b}.button{display:flex;justify-content:space-between;background:#d9573b;color:#fff;padding:16px 18px;border:0;cursor:pointer}.button:hover:not(:disabled){background:#17211b}.button:disabled{cursor:wait;opacity:.7}.form-error{margin:0;color:#b22d1c;font-size:13px}.switch{text-align:center;color:#68766a;font-size:13px;margin:4px 0}.switch a{color:#d9573b}.eyebrow{color:#d9573b;font:500 11px 'DM Mono',monospace;text-transform:uppercase;letter-spacing:.08em}@media(max-width:720px){.auth-page{grid-template-columns:1fr}.auth-art{min-height:310px}.auth-art h1{font-size:52px}.auth-form{padding:55px 0}}
</style>
