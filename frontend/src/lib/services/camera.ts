import { apiUrl } from '$lib/services/api';

const cameraTokenKey = 'duel_camera_session';

export interface CameraDeckCard {
  card_id: number;
  name: string;
  section: 'main' | 'extra' | 'side';
  quantity: number;
  preferred_print_id: number | null;
  image_url_small: string | null;
}

export interface CameraSession {
  expires_at: string;
  duel_id: number;
  duel_code: string;
  player_id: number;
  player_username: string;
  deck_cards: CameraDeckCard[];
}

export interface CameraBoardCard {
  id: number;
  player_id: number;
  zone: string;
  position: number | null;
  hidden: boolean;
}

export function getCameraToken(): string | null {
  return localStorage.getItem(cameraTokenKey);
}

export function saveCameraToken(token: string): void {
  localStorage.setItem(cameraTokenKey, token);
}

export function clearCameraToken(): void {
  localStorage.removeItem(cameraTokenKey);
}

export async function redeemCameraPairing(pairingToken: string): Promise<{ camera_token: string } & CameraSession> {
  const response = await fetch(`${apiUrl}/api/camera-pairings/redeem`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pairing_token: pairingToken })
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || 'No se pudo vincular la cámara. Genera un QR nuevo desde el tablero.');
  }
  return payload;
}

export async function loadCameraSession(): Promise<CameraSession> {
  const response = await cameraFetch('/api/camera-session');
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || 'La vinculación de cámara expiró o fue revocada.');
  }
  return payload;
}

export async function loadCameraBoardCards(): Promise<CameraBoardCard[]> {
  const response = await cameraFetch('/api/camera-session/cards');
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || 'No se pudieron cargar las posiciones ocupadas.');
  return payload;
}

export async function cameraFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getCameraToken();
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  return fetch(`${apiUrl}${path}`, { ...init, headers });
}
