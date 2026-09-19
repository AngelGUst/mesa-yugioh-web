import { goto } from '$app/navigation';

const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function getSessionToken(): string | null {
  return localStorage.getItem('duel_session');
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getSessionToken();
  const headers = new Headers(init.headers);

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${apiUrl}${path}`, { ...init, headers });
  if (response.status === 401) {
    localStorage.removeItem('duel_session');
    goto('/login');
  }
  return response;
}

export async function requireAuthenticatedUser<T extends { username: string }>(): Promise<T | null> {
  if (!getSessionToken()) {
    await goto('/login');
    return null;
  }

  try {
    const response = await apiFetch('/api/auth/me');
    if (!response.ok) {
      return null;
    }
    return response.json() as Promise<T>;
  } catch {
    return null;
  }
}
