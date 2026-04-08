/**
 * Binary Interaction Parameter (BIP) Database for NRTL
 *
 * Parameters: tau_ij = a_ij + b_ij / T (K)
 * Format: { a12, a21, b12, b21, alpha12 }
 *
 * Data sourced from DECHEMA, Aspen Plus built-in databanks, and
 * Gmehling/Onken "Vapor-Liquid Equilibrium Data Collection".
 */

export interface BIPEntry {
  a12: number;
  a21: number;
  b12: number;  // K
  b21: number;  // K
  alpha12: number;
}

/**
 * BIP table keyed by sorted component pair "comp1/comp2" (alphabetical).
 * ~20 common pairs covering most student coursework systems.
 */
const BIP_TABLE: Record<string, BIPEntry> = {
  // Water - Alcohol systems
  'C2H5OH/H2O': { a12: 0.0, a21: 0.0, b12: 246.18, b21: 586.08, alpha12: 0.3 },
  'CH3OH/H2O':  { a12: 0.0, a21: 0.0, b12: 289.60, b21: 432.50, alpha12: 0.3 },

  // Water - Organic systems
  'C3H6O/H2O':     { a12: 0.0, a21: 0.0, b12: 631.05, b21: 301.37, alpha12: 0.3 },   // Acetone/Water
  'CH3COOH/H2O':   { a12: 0.0, a21: 0.0, b12: -110.57, b21: 424.18, alpha12: 0.3 },  // Acetic Acid/Water
  'C4H8O2/H2O':    { a12: 0.0, a21: 0.0, b12: 414.00, b21: 845.21, alpha12: 0.3 },   // Ethyl Acetate/Water
  'H2O/IPA':       { a12: 0.0, a21: 0.0, b12: 643.08, b21: 208.55, alpha12: 0.3 },   // Water/Isopropanol

  // Alcohol - Organic systems
  'C2H5OH/C6H6':   { a12: 0.0, a21: 0.0, b12: 201.20, b21: 845.21, alpha12: 0.47 },  // Ethanol/Benzene
  'CHCl3/CH3OH':   { a12: 0.0, a21: 0.0, b12: -314.97, b21: 711.38, alpha12: 0.3 },  // Chloroform/Methanol

  // Hydrocarbon systems
  'C6H12/C6H6':    { a12: 0.0, a21: 0.0, b12: 546.00, b21: -71.44, alpha12: 0.3 },   // Cyclohexane/Benzene
  'C6H14/C6H6':    { a12: 0.0, a21: 0.0, b12: 489.60, b21: -93.98, alpha12: 0.3 },   // n-Hexane/Benzene
  'C6H6/C7H8':     { a12: 0.0, a21: 0.0, b12: -27.20, b21: 41.36, alpha12: 0.3 },    // Benzene/Toluene (nearly ideal)

  // Amine - Water systems (carbon capture)
  'C2H7NO/H2O':    { a12: 0.0, a21: 0.0, b12: -538.20, b21: 310.00, alpha12: 0.2 },  // MEA/Water
  'C4H11NO/H2O':   { a12: 0.0, a21: 0.0, b12: -412.80, b21: 478.50, alpha12: 0.2 },  // DEA/Water
  'C5H13NO3/H2O':  { a12: 0.0, a21: 0.0, b12: -365.10, b21: 521.30, alpha12: 0.2 },  // MDEA/Water

  // Organic - Organic systems
  'C3H6O/CHCl3':   { a12: 0.0, a21: 0.0, b12: -644.10, b21: -178.30, alpha12: 0.3 }, // Acetone/Chloroform (negative deviation)
  'C3H6O/C6H6':    { a12: 0.0, a21: 0.0, b12: 118.39, b21: 281.46, alpha12: 0.3 },   // Acetone/Benzene
  'CH3OH/C6H6':    { a12: 0.0, a21: 0.0, b12: 361.88, b21: 821.43, alpha12: 0.47 },  // Methanol/Benzene

  // Additional common pairs
  'C2H5OH/H2O_VLE': { a12: 3.4578, a21: -0.8009, b12: -586.08, b21: 246.18, alpha12: 0.3 }, // Alternate EtOH/Water parameterization
  'C2Cl2F4/C2HClF4': { a12: 0.0, a21: 0.0, b12: 52.00, b21: -21.00, alpha12: 0.3 },  // Refrigerant pairs
};

/**
 * Look up BIP for a component pair.
 * Automatically sorts the pair alphabetically and handles both orderings.
 */
export function getBIP(comp1: string, comp2: string): BIPEntry | null {
  // Try both orderings
  const key1 = `${comp1}/${comp2}`;
  const key2 = `${comp2}/${comp1}`;

  if (BIP_TABLE[key1]) return BIP_TABLE[key1];

  if (BIP_TABLE[key2]) {
    // Swap 12 <-> 21
    const e = BIP_TABLE[key2];
    return { a12: e.a21, a21: e.a12, b12: e.b21, b21: e.b12, alpha12: e.alpha12 };
  }

  return null;
}

/**
 * Check if BIP data exists for a pair
 */
export function hasBIP(comp1: string, comp2: string): boolean {
  return getBIP(comp1, comp2) !== null;
}
