export const CARD_WIDTH_CM = 5.87;
export const CARD_HEIGHT_CM = 8.57;
export const CARD_ASPECT_RATIO = CARD_WIDTH_CM / CARD_HEIGHT_CM;

export const ZONE_SLOTS: Record<string, number> = {
  monster_zone: 5,
  spell_trap_zone: 5,
  extra_monster: 2,
  pendulum: 2,
  field_spell: 1
};

export function slotsForZone(zone: string): number {
  return ZONE_SLOTS[zone] ?? 0;
}

// Tapete de media mitad: solo el lado propio (2 filas x 7 columnas).
// Si en el futuro usas un tapete completo, restaura MAT_ROWS = 5 y el layout completo.
export const MAT_COLUMNS = 7;
export const MAT_ROWS = 2;
export const MAT_WIDTH_CM = MAT_COLUMNS * CARD_WIDTH_CM;
export const MAT_HEIGHT_CM = MAT_ROWS * CARD_HEIGHT_CM;

export interface MatCell {
  zone: string;
  position: number;
  label: string;
}

// Filas vistas desde el jugador que sostiene el teléfono (solo su mitad):
// fila 0 monstruos propios, fila 1 mágicas/trampas propias.
const OWN_MONSTER_ROW: (MatCell | null)[] = [
  { zone: 'field_spell', position: 0, label: 'Campo' },
  { zone: 'monster_zone', position: 0, label: 'Monstruo 1' },
  { zone: 'monster_zone', position: 1, label: 'Monstruo 2' },
  { zone: 'monster_zone', position: 2, label: 'Monstruo 3' },
  { zone: 'monster_zone', position: 3, label: 'Monstruo 4' },
  { zone: 'monster_zone', position: 4, label: 'Monstruo 5' },
  { zone: 'graveyard', position: 0, label: 'Cementerio' }
];

const OWN_SPELL_ROW: (MatCell | null)[] = [
  { zone: 'extra_deck', position: 0, label: 'Deck extra' },
  { zone: 'pendulum', position: 0, label: 'Péndulo azul' },
  { zone: 'spell_trap_zone', position: 1, label: 'Mágica 2' },
  { zone: 'spell_trap_zone', position: 2, label: 'Mágica 3' },
  { zone: 'spell_trap_zone', position: 3, label: 'Mágica 4' },
  { zone: 'pendulum', position: 1, label: 'Péndulo rojo' },
  { zone: 'main_deck', position: 0, label: 'Deck' }
];

export const MAT_LAYOUT: (MatCell | null)[][] = [
  OWN_MONSTER_ROW,
  OWN_SPELL_ROW
];

export function cellAtMatPoint(xCm: number, yCm: number): { row: number; column: number; cell: MatCell | null } | null {
  if (xCm < 0 || yCm < 0 || xCm >= MAT_WIDTH_CM || yCm >= MAT_HEIGHT_CM) return null;
  const column = Math.floor(xCm / CARD_WIDTH_CM);
  const row = Math.floor(yCm / CARD_HEIGHT_CM);
  return { row, column, cell: MAT_LAYOUT[row][column] };
}
