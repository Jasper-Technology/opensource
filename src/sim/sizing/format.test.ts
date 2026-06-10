/**
 * Sizing display formatting + SI↔US unit conversion.
 */
import { describe, expect, it } from 'vitest';
import { sizeRows, summarizeSize } from './format';
import type { EquipmentSize } from './types';

const vessel: EquipmentSize = {
  unitId: 'v', unitType: 'Flash', sizeBasis: 'volume',
  sizes: { volume: 10, diameter: 2, height: 6 },
  assumptions: ['K=0.107'], method: 'Souders-Brown', source: 'GPSA', inRange: true,
};
const cooler: EquipmentSize = {
  unitId: 'c', unitType: 'Cooler', sizeBasis: 'area',
  sizes: { area: 100 }, assumptions: [], method: 'Q/(U·LMTD)', source: 'Towler', inRange: true,
};

describe('sizeRows unit conversion', () => {
  it('SI is the native basis', () => {
    const rows = sizeRows(vessel, 'SI');
    expect(rows.find((r) => r.label === 'Volume')).toEqual({ label: 'Volume', value: '10', unit: 'm³' });
    expect(rows.find((r) => r.label === 'Diameter')!.unit).toBe('m');
  });

  it('US converts m³→ft³ and m→ft', () => {
    const rows = sizeRows(vessel, 'US');
    const vol = rows.find((r) => r.label === 'Volume')!;
    expect(vol.unit).toBe('ft³');
    expect(Number(vol.value)).toBeCloseTo(353.147, -1); // 10 m³ (3 sig figs)
    const dia = rows.find((r) => r.label === 'Diameter')!;
    expect(dia.unit).toBe('ft');
    expect(Number(dia.value)).toBeCloseTo(6.56, 1); // 2 m
  });

  it('US converts area m²→ft²', () => {
    const rows = sizeRows(cooler, 'US');
    const area = rows[0];
    expect(area.unit).toBe('ft²');
    expect(Number(area.value)).toBeCloseTo(1076.39, -1); // 100 m² (3 sig figs)
  });

  it('summarizeSize honors the unit system', () => {
    expect(summarizeSize(cooler, 'SI')).toContain('m²');
    expect(summarizeSize(cooler, 'US')).toContain('ft²');
  });
});
