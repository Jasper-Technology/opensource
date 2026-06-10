/**
 * Presentation helpers for EquipmentSize — shared by the console unit table and
 * the NodePanel sizing section so both render sizes identically. Pure string
 * formatting; no rounding policy beyond display precision.
 */
import type { EquipmentSize } from './types';

function fmt(n: number, sig = 3): string {
  if (!Number.isFinite(n)) return '—';
  const abs = Math.abs(n);
  if (abs !== 0 && (abs < 1e-2 || abs >= 1e5)) return n.toExponential(2);
  return Number(n.toPrecision(sig)).toString();
}

/** Compact one-line size label, e.g. "Area 124 m²" or "Vol 12.4 m³ · ⌀ 1.8 m". */
export function summarizeSize(size: EquipmentSize, unitSystem: UnitSystem = 'SI'): string {
  if (size.sizeBasis === 'none') return '';
  if (size.note) return size.note;
  const rows = sizeRows(size, unitSystem);
  const find = (label: string) => rows.find((r) => r.label === label);
  const tag = (label: string, prefix: string): string | null => {
    const r = find(label);
    return r ? `${prefix}${r.value}${r.unit ? ` ${r.unit}` : ''}` : null;
  };
  switch (size.sizeBasis) {
    case 'area':
      return tag('Area', 'Area ') ?? '—';
    case 'power':
      return tag('Power', 'Power ') ?? '—';
    case 'heat_duty':
      return tag('Heat duty', 'Duty ') ?? '—';
    case 'volume': {
      const parts = [
        tag('Volume', 'Vol '),
        tag('Diameter', '⌀ '),
        tag('Height', 'H '),
        find('Stages') ? `${find('Stages')!.value} stages` : null,
      ].filter(Boolean) as string[];
      return parts.join(' · ') || '—';
    }
    default:
      return '';
  }
}

/** A size magnitude split into a number and its unit, for labeled display rows. */
export interface SizeRow {
  label: string;
  value: string;
  unit: string;
}

export type UnitSystem = 'SI' | 'US';

/**
 * All non-empty size magnitudes as label/value/unit rows, converted to the given
 * unit system. SI is the native basis; US converts to ft/ft²/ft³/hp/MMBTU·hr⁻¹.
 */
export function sizeRows(size: EquipmentSize, unitSystem: UnitSystem = 'SI'): SizeRow[] {
  const s = size.sizes;
  const us = unitSystem === 'US';
  const rows: SizeRow[] = [];
  // siUnit/usUnit + the SI→US multiplier for that quantity.
  const push = (label: string, v: number | undefined, siUnit: string, usUnit: string, factor: number) => {
    if (v === undefined) return;
    rows.push({ label, value: fmt(us ? v * factor : v), unit: us ? usUnit : siUnit });
  };
  push('Area', s.area, 'm²', 'ft²', 10.7639);
  push('Volume', s.volume, 'm³', 'ft³', 35.3147);
  push('Diameter', s.diameter, 'm', 'ft', 3.28084);
  push('Height', s.height, 'm', 'ft', 3.28084);
  push('Length', s.length, 'm', 'ft', 3.28084);
  push('Power', s.power, 'kW', 'hp', 1.34102);
  push('Heat duty', s.heat_duty, 'kW', 'MMBTU/hr', 0.00341214);
  if (s.nStages !== undefined) rows.push({ label: 'Stages', value: String(s.nStages), unit: '' });
  return rows;
}

/** True when this unit type actually produces a physical size worth showing. */
export function hasSize(size: EquipmentSize | undefined): size is EquipmentSize {
  return !!size && size.sizeBasis !== 'none';
}
