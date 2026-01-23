/**
 * Chemical Component Database
 *
 * Comprehensive database of chemical components with accurate thermodynamic properties.
 * Data sourced from DIPPR, NIST, and Perry's Chemical Engineers' Handbook.
 *
 * Cp coefficients are for the DIPPR polynomial form:
 * Cp = a + bT + cT^2 + dT^3 + eT^4 (J/mol/K)
 * Valid temperature range: approximately 200-1500 K for gases
 */

export interface ComponentData {
  id: string;
  name: string;
  formula: string;
  cas: string;
  MW: number; // g/mol
  Tc: number; // K (critical temperature)
  Pc: number; // bar (critical pressure)
  omega: number; // acentric factor
  Tb: number; // K (normal boiling point at 1 atm)
  Hf: number; // kJ/mol (standard heat of formation at 298.15 K)
  Cp_coef: [number, number, number, number, number]; // Cp = a + bT + cT^2 + dT^3 + eT^4
  category: 'gas' | 'hydrocarbon' | 'alcohol' | 'amine' | 'acid' | 'organic' | 'inorganic';
}

export const COMPONENT_DATABASE: Record<string, ComponentData> = {
  // ============================================================================
  // LIGHT GASES
  // ============================================================================

  H2: {
    id: 'H2',
    name: 'Hydrogen',
    formula: 'H2',
    cas: '1333-74-0',
    MW: 2.016,
    Tc: 33.19,
    Pc: 13.13,
    omega: -0.216,
    Tb: 20.28,
    Hf: 0.0,
    Cp_coef: [27.14, 9.274e-3, -1.381e-5, 7.645e-9, 0],
    category: 'gas',
  },

  He: {
    id: 'He',
    name: 'Helium',
    formula: 'He',
    cas: '7440-59-7',
    MW: 4.003,
    Tc: 5.19,
    Pc: 2.27,
    omega: -0.39,
    Tb: 4.22,
    Hf: 0.0,
    Cp_coef: [20.786, 0, 0, 0, 0], // Monatomic - constant Cp
    category: 'gas',
  },

  Ar: {
    id: 'Ar',
    name: 'Argon',
    formula: 'Ar',
    cas: '7440-37-1',
    MW: 39.948,
    Tc: 150.86,
    Pc: 48.98,
    omega: 0.0,
    Tb: 87.30,
    Hf: 0.0,
    Cp_coef: [20.786, 0, 0, 0, 0], // Monatomic - constant Cp
    category: 'gas',
  },

  CH4: {
    id: 'CH4',
    name: 'Methane',
    formula: 'CH4',
    cas: '74-82-8',
    MW: 16.043,
    Tc: 190.56,
    Pc: 45.99,
    omega: 0.011,
    Tb: 111.66,
    Hf: -74.52,
    Cp_coef: [19.25, 5.213e-2, 1.197e-5, -1.132e-8, 0],
    category: 'gas',
  },

  C2H6: {
    id: 'C2H6',
    name: 'Ethane',
    formula: 'C2H6',
    cas: '74-84-0',
    MW: 30.070,
    Tc: 305.32,
    Pc: 48.72,
    omega: 0.099,
    Tb: 184.55,
    Hf: -83.82,
    Cp_coef: [6.90, 1.730e-1, -6.406e-5, 7.285e-9, 0],
    category: 'gas',
  },

  C2H4: {
    id: 'C2H4',
    name: 'Ethylene',
    formula: 'C2H4',
    cas: '74-85-1',
    MW: 28.054,
    Tc: 282.34,
    Pc: 50.41,
    omega: 0.087,
    Tb: 169.42,
    Hf: 52.47,
    Cp_coef: [3.95, 1.564e-1, -8.348e-5, 1.755e-8, 0],
    category: 'gas',
  },

  C3H8: {
    id: 'C3H8',
    name: 'Propane',
    formula: 'C3H8',
    cas: '74-98-6',
    MW: 44.097,
    Tc: 369.83,
    Pc: 42.48,
    omega: 0.152,
    Tb: 231.02,
    Hf: -104.68,
    Cp_coef: [-4.22, 3.063e-1, -1.586e-4, 3.215e-8, 0],
    category: 'gas',
  },

  C3H6: {
    id: 'C3H6',
    name: 'Propylene',
    formula: 'C3H6',
    cas: '115-07-1',
    MW: 42.081,
    Tc: 364.90,
    Pc: 46.00,
    omega: 0.142,
    Tb: 225.45,
    Hf: 19.71,
    Cp_coef: [3.71, 2.345e-1, -1.160e-4, 2.205e-8, 0],
    category: 'gas',
  },

  // ============================================================================
  // AIR COMPONENTS
  // ============================================================================

  N2: {
    id: 'N2',
    name: 'Nitrogen',
    formula: 'N2',
    cas: '7727-37-9',
    MW: 28.014,
    Tc: 126.20,
    Pc: 33.96,
    omega: 0.037,
    Tb: 77.35,
    Hf: 0.0,
    Cp_coef: [31.15, -1.357e-2, 2.680e-5, -1.168e-8, 0],
    category: 'inorganic',
  },

  O2: {
    id: 'O2',
    name: 'Oxygen',
    formula: 'O2',
    cas: '7782-44-7',
    MW: 31.999,
    Tc: 154.58,
    Pc: 50.43,
    omega: 0.022,
    Tb: 90.20,
    Hf: 0.0,
    Cp_coef: [25.46, 1.520e-2, -7.155e-6, 1.312e-9, 0],
    category: 'inorganic',
  },

  CO2: {
    id: 'CO2',
    name: 'Carbon Dioxide',
    formula: 'CO2',
    cas: '124-38-9',
    MW: 44.010,
    Tc: 304.13,
    Pc: 73.77,
    omega: 0.228,
    Tb: 194.65, // Sublimation point
    Hf: -393.51,
    Cp_coef: [19.80, 7.344e-2, -5.602e-5, 1.715e-8, 0],
    category: 'inorganic',
  },

  H2O: {
    id: 'H2O',
    name: 'Water',
    formula: 'H2O',
    cas: '7732-18-5',
    MW: 18.015,
    Tc: 647.10,
    Pc: 220.64,
    omega: 0.345,
    Tb: 373.15,
    Hf: -241.82,
    Cp_coef: [33.46, 6.880e-3, 7.604e-6, -3.593e-9, 0],
    category: 'inorganic',
  },

  CO: {
    id: 'CO',
    name: 'Carbon Monoxide',
    formula: 'CO',
    cas: '630-08-0',
    MW: 28.010,
    Tc: 132.85,
    Pc: 34.94,
    omega: 0.045,
    Tb: 81.65,
    Hf: -110.53,
    Cp_coef: [30.87, -1.285e-2, 2.789e-5, -1.272e-8, 0],
    category: 'inorganic',
  },

  NO: {
    id: 'NO',
    name: 'Nitric Oxide',
    formula: 'NO',
    cas: '10102-43-9',
    MW: 30.006,
    Tc: 180.00,
    Pc: 64.80,
    omega: 0.588,
    Tb: 121.38,
    Hf: 90.25,
    Cp_coef: [29.34, -9.395e-4, 9.747e-6, -4.187e-9, 0],
    category: 'inorganic',
  },

  NO2: {
    id: 'NO2',
    name: 'Nitrogen Dioxide',
    formula: 'NO2',
    cas: '10102-44-0',
    MW: 46.006,
    Tc: 431.00,
    Pc: 101.33,
    omega: 0.834,
    Tb: 294.30,
    Hf: 33.10,
    Cp_coef: [24.89, 6.394e-2, -4.169e-5, 1.009e-8, 0],
    category: 'inorganic',
  },

  SO2: {
    id: 'SO2',
    name: 'Sulfur Dioxide',
    formula: 'SO2',
    cas: '7446-09-5',
    MW: 64.066,
    Tc: 430.80,
    Pc: 78.84,
    omega: 0.251,
    Tb: 263.00,
    Hf: -296.83,
    Cp_coef: [25.72, 5.786e-2, -3.812e-5, 8.612e-9, 0],
    category: 'inorganic',
  },

  H2S: {
    id: 'H2S',
    name: 'Hydrogen Sulfide',
    formula: 'H2S',
    cas: '7783-06-4',
    MW: 34.082,
    Tc: 373.53,
    Pc: 89.63,
    omega: 0.094,
    Tb: 212.84,
    Hf: -20.60,
    Cp_coef: [31.94, 1.436e-3, 2.432e-5, -1.176e-8, 0],
    category: 'inorganic',
  },

  // ============================================================================
  // HYDROCARBONS
  // ============================================================================

  'n-C4H10': {
    id: 'n-C4H10',
    name: 'n-Butane',
    formula: 'C4H10',
    cas: '106-97-8',
    MW: 58.123,
    Tc: 425.12,
    Pc: 37.96,
    omega: 0.200,
    Tb: 272.65,
    Hf: -125.79,
    Cp_coef: [-7.91, 4.161e-1, -2.302e-4, 4.999e-8, 0],
    category: 'hydrocarbon',
  },

  'i-C4H10': {
    id: 'i-C4H10',
    name: 'Isobutane',
    formula: 'C4H10',
    cas: '75-28-5',
    MW: 58.123,
    Tc: 407.80,
    Pc: 36.40,
    omega: 0.186,
    Tb: 261.40,
    Hf: -134.18,
    Cp_coef: [-1.39, 3.847e-1, -1.846e-4, 2.895e-8, 0],
    category: 'hydrocarbon',
  },

  'n-C5H12': {
    id: 'n-C5H12',
    name: 'n-Pentane',
    formula: 'C5H12',
    cas: '109-66-0',
    MW: 72.150,
    Tc: 469.70,
    Pc: 33.70,
    omega: 0.251,
    Tb: 309.22,
    Hf: -146.76,
    Cp_coef: [-12.30, 5.216e-1, -2.962e-4, 6.653e-8, 0],
    category: 'hydrocarbon',
  },

  'n-C6H14': {
    id: 'n-C6H14',
    name: 'n-Hexane',
    formula: 'C6H14',
    cas: '110-54-3',
    MW: 86.177,
    Tc: 507.60,
    Pc: 30.25,
    omega: 0.301,
    Tb: 341.88,
    Hf: -167.19,
    Cp_coef: [-16.52, 6.293e-1, -3.635e-4, 8.279e-8, 0],
    category: 'hydrocarbon',
  },

  'n-C7H16': {
    id: 'n-C7H16',
    name: 'n-Heptane',
    formula: 'C7H16',
    cas: '142-82-5',
    MW: 100.204,
    Tc: 540.20,
    Pc: 27.40,
    omega: 0.350,
    Tb: 371.58,
    Hf: -187.78,
    Cp_coef: [-20.74, 7.376e-1, -4.311e-4, 9.920e-8, 0],
    category: 'hydrocarbon',
  },

  'n-C8H18': {
    id: 'n-C8H18',
    name: 'n-Octane',
    formula: 'C8H18',
    cas: '111-65-9',
    MW: 114.231,
    Tc: 568.70,
    Pc: 24.90,
    omega: 0.399,
    Tb: 398.82,
    Hf: -208.45,
    Cp_coef: [-24.95, 8.458e-1, -4.986e-4, 1.156e-7, 0],
    category: 'hydrocarbon',
  },

  'n-C9H20': {
    id: 'n-C9H20',
    name: 'n-Nonane',
    formula: 'C9H20',
    cas: '111-84-2',
    MW: 128.258,
    Tc: 594.60,
    Pc: 22.90,
    omega: 0.443,
    Tb: 423.97,
    Hf: -228.23,
    Cp_coef: [-29.16, 9.540e-1, -5.661e-4, 1.320e-7, 0],
    category: 'hydrocarbon',
  },

  'n-C10H22': {
    id: 'n-C10H22',
    name: 'n-Decane',
    formula: 'C10H22',
    cas: '124-18-5',
    MW: 142.285,
    Tc: 617.70,
    Pc: 21.10,
    omega: 0.492,
    Tb: 447.30,
    Hf: -249.66,
    Cp_coef: [-33.38, 1.063, -6.337e-4, 1.483e-7, 0],
    category: 'hydrocarbon',
  },

  C6H6: {
    id: 'C6H6',
    name: 'Benzene',
    formula: 'C6H6',
    cas: '71-43-2',
    MW: 78.114,
    Tc: 562.05,
    Pc: 48.98,
    omega: 0.210,
    Tb: 353.24,
    Hf: 49.08,
    Cp_coef: [-36.19, 4.840e-1, -3.142e-4, 7.659e-8, 0],
    category: 'hydrocarbon',
  },

  C7H8: {
    id: 'C7H8',
    name: 'Toluene',
    formula: 'C7H8',
    cas: '108-88-3',
    MW: 92.141,
    Tc: 591.75,
    Pc: 41.08,
    omega: 0.264,
    Tb: 383.78,
    Hf: 12.00,
    Cp_coef: [-43.33, 5.853e-1, -3.827e-4, 9.335e-8, 0],
    category: 'hydrocarbon',
  },

  'mC8H10': {
    id: 'mC8H10',
    name: 'm-Xylene',
    formula: 'C8H10',
    cas: '108-38-3',
    MW: 106.167,
    Tc: 617.00,
    Pc: 35.41,
    omega: 0.327,
    Tb: 412.27,
    Hf: -25.42,
    Cp_coef: [-50.10, 6.839e-1, -4.501e-4, 1.106e-7, 0],
    category: 'hydrocarbon',
  },

  'oC8H10': {
    id: 'oC8H10',
    name: 'o-Xylene',
    formula: 'C8H10',
    cas: '95-47-6',
    MW: 106.167,
    Tc: 630.33,
    Pc: 37.32,
    omega: 0.310,
    Tb: 417.58,
    Hf: -24.44,
    Cp_coef: [-48.89, 6.739e-1, -4.421e-4, 1.083e-7, 0],
    category: 'hydrocarbon',
  },

  'pC8H10': {
    id: 'pC8H10',
    name: 'p-Xylene',
    formula: 'C8H10',
    cas: '106-42-3',
    MW: 106.167,
    Tc: 616.20,
    Pc: 35.11,
    omega: 0.322,
    Tb: 411.51,
    Hf: -24.44,
    Cp_coef: [-49.85, 6.809e-1, -4.479e-4, 1.098e-7, 0],
    category: 'hydrocarbon',
  },

  C10H8: {
    id: 'C10H8',
    name: 'Naphthalene',
    formula: 'C10H8',
    cas: '91-20-3',
    MW: 128.174,
    Tc: 748.40,
    Pc: 40.51,
    omega: 0.302,
    Tb: 491.14,
    Hf: 78.53,
    Cp_coef: [-68.27, 8.175e-1, -5.570e-4, 1.414e-7, 0],
    category: 'hydrocarbon',
  },

  C6H12: {
    id: 'C6H12',
    name: 'Cyclohexane',
    formula: 'C6H12',
    cas: '110-82-7',
    MW: 84.161,
    Tc: 553.58,
    Pc: 40.73,
    omega: 0.211,
    Tb: 353.87,
    Hf: -123.14,
    Cp_coef: [-54.47, 6.111e-1, -3.789e-4, 9.082e-8, 0],
    category: 'hydrocarbon',
  },

  // ============================================================================
  // ALCOHOLS
  // ============================================================================

  CH3OH: {
    id: 'CH3OH',
    name: 'Methanol',
    formula: 'CH3OH',
    cas: '67-56-1',
    MW: 32.042,
    Tc: 512.64,
    Pc: 80.97,
    omega: 0.565,
    Tb: 337.69,
    Hf: -200.66,
    Cp_coef: [21.15, 7.092e-2, 2.587e-5, -2.852e-8, 0],
    category: 'alcohol',
  },

  C2H5OH: {
    id: 'C2H5OH',
    name: 'Ethanol',
    formula: 'C2H5OH',
    cas: '64-17-5',
    MW: 46.069,
    Tc: 513.92,
    Pc: 61.48,
    omega: 0.644,
    Tb: 351.44,
    Hf: -234.95,
    Cp_coef: [9.01, 2.141e-1, -8.390e-5, 1.373e-9, 0],
    category: 'alcohol',
  },

  'C3H7OH-1': {
    id: 'C3H7OH-1',
    name: '1-Propanol',
    formula: 'C3H7OH',
    cas: '71-23-8',
    MW: 60.096,
    Tc: 536.78,
    Pc: 51.70,
    omega: 0.620,
    Tb: 370.30,
    Hf: -255.20,
    Cp_coef: [2.47, 3.325e-1, -1.855e-4, 4.296e-8, 0],
    category: 'alcohol',
  },

  'C3H7OH-2': {
    id: 'C3H7OH-2',
    name: '2-Propanol',
    formula: 'C3H7OH',
    cas: '67-63-0',
    MW: 60.096,
    Tc: 508.30,
    Pc: 47.62,
    omega: 0.665,
    Tb: 355.41,
    Hf: -272.70,
    Cp_coef: [6.08, 3.063e-1, -1.680e-4, 3.649e-8, 0],
    category: 'alcohol',
  },

  'C4H9OH-1': {
    id: 'C4H9OH-1',
    name: '1-Butanol',
    formula: 'C4H9OH',
    cas: '71-36-3',
    MW: 74.123,
    Tc: 563.05,
    Pc: 44.23,
    omega: 0.590,
    Tb: 390.88,
    Hf: -274.60,
    Cp_coef: [-4.41, 4.401e-1, -2.627e-4, 6.409e-8, 0],
    category: 'alcohol',
  },

  EG: {
    id: 'EG',
    name: 'Ethylene Glycol',
    formula: 'C2H6O2',
    cas: '107-21-1',
    MW: 62.068,
    Tc: 719.00,
    Pc: 77.00,
    omega: 0.487,
    Tb: 470.45,
    Hf: -392.20,
    Cp_coef: [35.54, 2.509e-1, -1.228e-4, 2.361e-8, 0],
    category: 'alcohol',
  },

  Glycerol: {
    id: 'Glycerol',
    name: 'Glycerol',
    formula: 'C3H8O3',
    cas: '56-81-5',
    MW: 92.094,
    Tc: 850.00,
    Pc: 75.00,
    omega: 0.513,
    Tb: 563.15,
    Hf: -577.90,
    Cp_coef: [48.20, 3.850e-1, -2.100e-4, 4.500e-8, 0],
    category: 'alcohol',
  },

  // ============================================================================
  // AMINES
  // ============================================================================

  NH3: {
    id: 'NH3',
    name: 'Ammonia',
    formula: 'NH3',
    cas: '7664-41-7',
    MW: 17.031,
    Tc: 405.40,
    Pc: 113.53,
    omega: 0.256,
    Tb: 239.82,
    Hf: -45.94,
    Cp_coef: [27.31, 2.383e-2, 1.707e-5, -1.185e-8, 0],
    category: 'amine',
  },

  MEA: {
    id: 'MEA',
    name: 'Monoethanolamine',
    formula: 'C2H7NO',
    cas: '141-43-5',
    MW: 61.084,
    Tc: 678.20,
    Pc: 80.00,
    omega: 0.545,
    Tb: 443.45,
    Hf: -302.50,
    Cp_coef: [61.50, 2.800e-1, -1.600e-4, 3.500e-8, 0],
    category: 'amine',
  },

  DEA: {
    id: 'DEA',
    name: 'Diethanolamine',
    formula: 'C4H11NO2',
    cas: '111-42-2',
    MW: 105.137,
    Tc: 736.60,
    Pc: 42.70,
    omega: 0.953,
    Tb: 541.50,
    Hf: -496.10,
    Cp_coef: [47.20, 4.950e-1, -2.850e-4, 6.500e-8, 0],
    category: 'amine',
  },

  MDEA: {
    id: 'MDEA',
    name: 'Methyldiethanolamine',
    formula: 'C5H13NO2',
    cas: '105-59-9',
    MW: 119.164,
    Tc: 741.90,
    Pc: 38.70,
    omega: 0.628,
    Tb: 520.15,
    Hf: -380.00,
    Cp_coef: [52.30, 5.420e-1, -3.120e-4, 7.100e-8, 0],
    category: 'amine',
  },

  PZ: {
    id: 'PZ',
    name: 'Piperazine',
    formula: 'C4H10N2',
    cas: '110-85-0',
    MW: 86.137,
    Tc: 638.00,
    Pc: 55.30,
    omega: 0.310,
    Tb: 419.15,
    Hf: -45.80,
    Cp_coef: [38.50, 3.650e-1, -2.100e-4, 4.800e-8, 0],
    category: 'amine',
  },

  TEA: {
    id: 'TEA',
    name: 'Triethanolamine',
    formula: 'C6H15NO3',
    cas: '102-71-6',
    MW: 149.190,
    Tc: 787.00,
    Pc: 32.40,
    omega: 1.284,
    Tb: 608.55,
    Hf: -664.20,
    Cp_coef: [55.80, 6.850e-1, -3.950e-4, 9.000e-8, 0],
    category: 'amine',
  },

  DGA: {
    id: 'DGA',
    name: 'Diglycolamine',
    formula: 'C4H11NO2',
    cas: '929-06-6',
    MW: 105.137,
    Tc: 696.00,
    Pc: 44.50,
    omega: 0.845,
    Tb: 494.15,
    Hf: -365.00,
    Cp_coef: [48.50, 4.780e-1, -2.750e-4, 6.250e-8, 0],
    category: 'amine',
  },

  Methylamine: {
    id: 'Methylamine',
    name: 'Methylamine',
    formula: 'CH5N',
    cas: '74-89-5',
    MW: 31.058,
    Tc: 430.05,
    Pc: 74.60,
    omega: 0.281,
    Tb: 266.82,
    Hf: -22.97,
    Cp_coef: [28.20, 8.950e-2, -3.450e-5, 5.200e-9, 0],
    category: 'amine',
  },

  Dimethylamine: {
    id: 'Dimethylamine',
    name: 'Dimethylamine',
    formula: 'C2H7N',
    cas: '124-40-3',
    MW: 45.084,
    Tc: 437.65,
    Pc: 53.40,
    omega: 0.302,
    Tb: 280.03,
    Hf: -18.83,
    Cp_coef: [22.50, 1.720e-1, -8.500e-5, 1.600e-8, 0],
    category: 'amine',
  },

  // ============================================================================
  // ACIDS
  // ============================================================================

  HCOOH: {
    id: 'HCOOH',
    name: 'Formic Acid',
    formula: 'HCOOH',
    cas: '64-18-6',
    MW: 46.026,
    Tc: 588.00,
    Pc: 58.10,
    omega: 0.473,
    Tb: 373.90,
    Hf: -378.70,
    Cp_coef: [11.02, 1.213e-1, -6.178e-5, 1.158e-8, 0],
    category: 'acid',
  },

  CH3COOH: {
    id: 'CH3COOH',
    name: 'Acetic Acid',
    formula: 'CH3COOH',
    cas: '64-19-7',
    MW: 60.052,
    Tc: 591.95,
    Pc: 57.86,
    omega: 0.467,
    Tb: 391.05,
    Hf: -432.80,
    Cp_coef: [8.00, 2.008e-1, -1.095e-4, 2.206e-8, 0],
    category: 'acid',
  },

  HCl: {
    id: 'HCl',
    name: 'Hydrogen Chloride',
    formula: 'HCl',
    cas: '7647-01-0',
    MW: 36.461,
    Tc: 324.70,
    Pc: 83.10,
    omega: 0.132,
    Tb: 188.15,
    Hf: -92.31,
    Cp_coef: [29.13, -2.215e-3, 9.456e-6, -4.186e-9, 0],
    category: 'acid',
  },

  HNO3: {
    id: 'HNO3',
    name: 'Nitric Acid',
    formula: 'HNO3',
    cas: '7697-37-2',
    MW: 63.013,
    Tc: 520.00,
    Pc: 68.90,
    omega: 0.714,
    Tb: 356.15,
    Hf: -133.90,
    Cp_coef: [26.80, 1.050e-1, -6.200e-5, 1.400e-8, 0],
    category: 'acid',
  },

  // ============================================================================
  // OTHER ORGANICS
  // ============================================================================

  CH3COCH3: {
    id: 'CH3COCH3',
    name: 'Acetone',
    formula: 'C3H6O',
    cas: '67-64-1',
    MW: 58.080,
    Tc: 508.20,
    Pc: 47.01,
    omega: 0.307,
    Tb: 329.22,
    Hf: -217.15,
    Cp_coef: [6.30, 2.606e-1, -1.253e-4, 2.038e-8, 0],
    category: 'organic',
  },

  CH3CHO: {
    id: 'CH3CHO',
    name: 'Acetaldehyde',
    formula: 'C2H4O',
    cas: '75-07-0',
    MW: 44.053,
    Tc: 466.00,
    Pc: 55.70,
    omega: 0.291,
    Tb: 293.25,
    Hf: -166.19,
    Cp_coef: [7.71, 1.820e-1, -9.240e-5, 1.837e-8, 0],
    category: 'organic',
  },

  EO: {
    id: 'EO',
    name: 'Ethylene Oxide',
    formula: 'C2H4O',
    cas: '75-21-8',
    MW: 44.053,
    Tc: 469.15,
    Pc: 71.90,
    omega: 0.200,
    Tb: 283.60,
    Hf: -52.63,
    Cp_coef: [-10.30, 2.210e-1, -1.337e-4, 3.205e-8, 0],
    category: 'organic',
  },

  DME: {
    id: 'DME',
    name: 'Dimethyl Ether',
    formula: 'C2H6O',
    cas: '115-10-6',
    MW: 46.069,
    Tc: 400.10,
    Pc: 53.70,
    omega: 0.200,
    Tb: 248.31,
    Hf: -184.10,
    Cp_coef: [17.02, 1.791e-1, -5.234e-5, -1.919e-9, 0],
    category: 'organic',
  },

  HCHO: {
    id: 'HCHO',
    name: 'Formaldehyde',
    formula: 'HCHO',
    cas: '50-00-0',
    MW: 30.026,
    Tc: 408.00,
    Pc: 65.90,
    omega: 0.282,
    Tb: 254.05,
    Hf: -108.57,
    Cp_coef: [23.48, 4.695e-2, 9.837e-6, -1.371e-8, 0],
    category: 'organic',
  },

  C2H3Cl: {
    id: 'C2H3Cl',
    name: 'Vinyl Chloride',
    formula: 'C2H3Cl',
    cas: '75-01-4',
    MW: 62.499,
    Tc: 432.00,
    Pc: 56.70,
    omega: 0.100,
    Tb: 259.25,
    Hf: 28.45,
    Cp_coef: [5.94, 1.560e-1, -9.550e-5, 2.230e-8, 0],
    category: 'organic',
  },

  CHCl3: {
    id: 'CHCl3',
    name: 'Chloroform',
    formula: 'CHCl3',
    cas: '67-66-3',
    MW: 119.378,
    Tc: 536.40,
    Pc: 54.72,
    omega: 0.222,
    Tb: 334.32,
    Hf: -103.14,
    Cp_coef: [24.00, 1.888e-1, -1.841e-4, 6.657e-8, 0],
    category: 'organic',
  },

  CCl4: {
    id: 'CCl4',
    name: 'Carbon Tetrachloride',
    formula: 'CCl4',
    cas: '56-23-5',
    MW: 153.823,
    Tc: 556.35,
    Pc: 45.60,
    omega: 0.193,
    Tb: 349.79,
    Hf: -95.98,
    Cp_coef: [40.92, 2.064e-1, -2.277e-4, 9.020e-8, 0],
    category: 'organic',
  },

  THF: {
    id: 'THF',
    name: 'Tetrahydrofuran',
    formula: 'C4H8O',
    cas: '109-99-9',
    MW: 72.107,
    Tc: 540.15,
    Pc: 51.90,
    omega: 0.225,
    Tb: 339.12,
    Hf: -184.10,
    Cp_coef: [-29.35, 4.198e-1, -2.605e-4, 6.297e-8, 0],
    category: 'organic',
  },

  NMP: {
    id: 'NMP',
    name: 'N-Methyl-2-pyrrolidone',
    formula: 'C5H9NO',
    cas: '872-50-4',
    MW: 99.133,
    Tc: 721.80,
    Pc: 45.20,
    omega: 0.355,
    Tb: 475.15,
    Hf: -262.00,
    Cp_coef: [-15.20, 5.520e-1, -3.420e-4, 8.350e-8, 0],
    category: 'organic',
  },

  DMSO: {
    id: 'DMSO',
    name: 'Dimethyl Sulfoxide',
    formula: 'C2H6OS',
    cas: '67-68-5',
    MW: 78.133,
    Tc: 729.00,
    Pc: 56.50,
    omega: 0.281,
    Tb: 462.15,
    Hf: -203.40,
    Cp_coef: [25.30, 2.165e-1, -1.050e-4, 1.850e-8, 0],
    category: 'organic',
  },

  DiethylEther: {
    id: 'DiethylEther',
    name: 'Diethyl Ether',
    formula: 'C4H10O',
    cas: '60-29-7',
    MW: 74.123,
    Tc: 466.70,
    Pc: 36.40,
    omega: 0.281,
    Tb: 307.58,
    Hf: -252.20,
    Cp_coef: [16.50, 3.420e-1, -1.890e-4, 4.050e-8, 0],
    category: 'organic',
  },

  MethylAcetate: {
    id: 'MethylAcetate',
    name: 'Methyl Acetate',
    formula: 'C3H6O2',
    cas: '79-20-9',
    MW: 74.079,
    Tc: 506.55,
    Pc: 47.50,
    omega: 0.326,
    Tb: 330.02,
    Hf: -411.50,
    Cp_coef: [15.40, 2.850e-1, -1.650e-4, 3.750e-8, 0],
    category: 'organic',
  },

  EthylAcetate: {
    id: 'EthylAcetate',
    name: 'Ethyl Acetate',
    formula: 'C4H8O2',
    cas: '141-78-6',
    MW: 88.106,
    Tc: 523.30,
    Pc: 38.80,
    omega: 0.366,
    Tb: 350.21,
    Hf: -443.90,
    Cp_coef: [12.80, 3.680e-1, -2.150e-4, 4.950e-8, 0],
    category: 'organic',
  },

  Styrene: {
    id: 'Styrene',
    name: 'Styrene',
    formula: 'C8H8',
    cas: '100-42-5',
    MW: 104.152,
    Tc: 636.00,
    Pc: 38.40,
    omega: 0.297,
    Tb: 418.31,
    Hf: 103.80,
    Cp_coef: [-38.50, 6.250e-1, -4.180e-4, 1.050e-7, 0],
    category: 'organic',
  },

  Aniline: {
    id: 'Aniline',
    name: 'Aniline',
    formula: 'C6H7N',
    cas: '62-53-3',
    MW: 93.129,
    Tc: 699.00,
    Pc: 53.10,
    omega: 0.382,
    Tb: 457.32,
    Hf: 31.09,
    Cp_coef: [-42.80, 5.650e-1, -3.750e-4, 9.450e-8, 0],
    category: 'organic',
  },

  Phenol: {
    id: 'Phenol',
    name: 'Phenol',
    formula: 'C6H6O',
    cas: '108-95-2',
    MW: 94.113,
    Tc: 694.25,
    Pc: 61.30,
    omega: 0.444,
    Tb: 455.02,
    Hf: -96.40,
    Cp_coef: [-35.20, 5.380e-1, -3.580e-4, 9.050e-8, 0],
    category: 'organic',
  },

  MEK: {
    id: 'MEK',
    name: 'Methyl Ethyl Ketone',
    formula: 'C4H8O',
    cas: '78-93-3',
    MW: 72.107,
    Tc: 535.50,
    Pc: 41.50,
    omega: 0.323,
    Tb: 352.79,
    Hf: -238.50,
    Cp_coef: [9.20, 3.450e-1, -1.920e-4, 4.200e-8, 0],
    category: 'organic',
  },

  // ============================================================================
  // ADDITIONAL INORGANICS
  // ============================================================================

  Cl2: {
    id: 'Cl2',
    name: 'Chlorine',
    formula: 'Cl2',
    cas: '7782-50-5',
    MW: 70.906,
    Tc: 417.15,
    Pc: 77.10,
    omega: 0.069,
    Tb: 239.11,
    Hf: 0.0,
    Cp_coef: [33.95, 1.230e-2, -1.234e-5, 4.862e-9, 0],
    category: 'inorganic',
  },

  F2: {
    id: 'F2',
    name: 'Fluorine',
    formula: 'F2',
    cas: '7782-41-4',
    MW: 37.997,
    Tc: 144.41,
    Pc: 52.15,
    omega: 0.054,
    Tb: 85.03,
    Hf: 0.0,
    Cp_coef: [31.30, 7.400e-3, -5.400e-6, 1.350e-9, 0],
    category: 'inorganic',
  },

  N2O: {
    id: 'N2O',
    name: 'Nitrous Oxide',
    formula: 'N2O',
    cas: '10024-97-2',
    MW: 44.013,
    Tc: 309.57,
    Pc: 72.45,
    omega: 0.141,
    Tb: 184.67,
    Hf: 82.05,
    Cp_coef: [21.62, 7.281e-2, -5.778e-5, 1.831e-8, 0],
    category: 'inorganic',
  },

  COS: {
    id: 'COS',
    name: 'Carbonyl Sulfide',
    formula: 'COS',
    cas: '463-58-1',
    MW: 60.075,
    Tc: 378.80,
    Pc: 63.49,
    omega: 0.099,
    Tb: 222.87,
    Hf: -138.41,
    Cp_coef: [29.17, 6.075e-2, -4.381e-5, 1.218e-8, 0],
    category: 'inorganic',
  },

  CS2: {
    id: 'CS2',
    name: 'Carbon Disulfide',
    formula: 'CS2',
    cas: '75-15-0',
    MW: 76.143,
    Tc: 552.00,
    Pc: 79.00,
    omega: 0.109,
    Tb: 319.37,
    Hf: 89.70,
    Cp_coef: [29.57, 7.200e-2, -5.580e-5, 1.630e-8, 0],
    category: 'inorganic',
  },

  HF: {
    id: 'HF',
    name: 'Hydrogen Fluoride',
    formula: 'HF',
    cas: '7664-39-3',
    MW: 20.006,
    Tc: 461.00,
    Pc: 64.80,
    omega: 0.372,
    Tb: 292.67,
    Hf: -273.30,
    Cp_coef: [29.10, -5.200e-4, 6.200e-6, -2.800e-9, 0],
    category: 'inorganic',
  },

  HBr: {
    id: 'HBr',
    name: 'Hydrogen Bromide',
    formula: 'HBr',
    cas: '10035-10-6',
    MW: 80.912,
    Tc: 363.20,
    Pc: 85.50,
    omega: 0.070,
    Tb: 206.43,
    Hf: -36.29,
    Cp_coef: [29.14, -1.100e-3, 7.800e-6, -3.500e-9, 0],
    category: 'inorganic',
  },
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Get all components as an array
 * @returns Array of all component data objects
 */
export function getComponentList(): ComponentData[] {
  return Object.values(COMPONENT_DATABASE);
}

/**
 * Get components filtered by category
 * @param category - The category to filter by
 * @returns Array of component data objects matching the category
 */
export function getComponentsByCategory(
  category: 'gas' | 'hydrocarbon' | 'alcohol' | 'amine' | 'acid' | 'organic' | 'inorganic'
): ComponentData[] {
  return Object.values(COMPONENT_DATABASE).filter((c) => c.category === category);
}

/**
 * Get a component by its ID
 * @param id - Component ID (e.g., 'H2O', 'CO2')
 * @returns Component data or undefined if not found
 */
export function getComponentById(id: string): ComponentData | undefined {
  return COMPONENT_DATABASE[id];
}

/**
 * Get a component by its CAS number
 * @param cas - CAS registry number (e.g., '7732-18-5')
 * @returns Component data or undefined if not found
 */
export function getComponentByCAS(cas: string): ComponentData | undefined {
  return Object.values(COMPONENT_DATABASE).find((c) => c.cas === cas);
}

/**
 * Search components by name (case-insensitive partial match)
 * @param searchTerm - Search string to match against component names
 * @returns Array of matching component data objects
 */
export function searchComponentsByName(searchTerm: string): ComponentData[] {
  const lowerSearch = searchTerm.toLowerCase();
  return Object.values(COMPONENT_DATABASE).filter((c) =>
    c.name.toLowerCase().includes(lowerSearch)
  );
}

/**
 * Calculate ideal gas heat capacity at temperature T
 * @param component - Component data object
 * @param T - Temperature in Kelvin
 * @returns Heat capacity in J/(mol*K)
 */
export function calculateCp(component: ComponentData, T: number): number {
  const [a, b, c, d, e] = component.Cp_coef;
  return a + b * T + c * T ** 2 + d * T ** 3 + e * T ** 4;
}

/**
 * Calculate reduced properties for equation of state calculations
 * @param component - Component data object
 * @param T - Temperature in Kelvin
 * @param P - Pressure in bar
 * @returns Object with reduced temperature and pressure
 */
export function getReducedProperties(
  component: ComponentData,
  T: number,
  P: number
): { Tr: number; Pr: number } {
  return {
    Tr: T / component.Tc,
    Pr: P / component.Pc,
  };
}

/**
 * Get available categories in the database
 * @returns Array of unique category strings
 */
export function getCategories(): Array<ComponentData['category']> {
  const categories = new Set(
    Object.values(COMPONENT_DATABASE).map((c) => c.category)
  );
  return Array.from(categories);
}

/**
 * Get component count by category
 * @returns Object with category names as keys and counts as values
 */
export function getComponentCountByCategory(): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const component of Object.values(COMPONENT_DATABASE)) {
    counts[component.category] = (counts[component.category] || 0) + 1;
  }
  return counts;
}

// Type for component categories
export type ComponentCategory = ComponentData['category'];

// Category labels for UI display
export const CATEGORY_LABELS: Record<ComponentCategory, string> = {
  gas: 'Gases',
  hydrocarbon: 'Hydrocarbons',
  alcohol: 'Alcohols',
  amine: 'Amines',
  acid: 'Acids',
  organic: 'Other Organics',
  inorganic: 'Inorganics',
};

// Ordered list of categories for consistent UI display
export const CATEGORY_ORDER: ComponentCategory[] = [
  'gas',
  'hydrocarbon',
  'alcohol',
  'amine',
  'acid',
  'organic',
  'inorganic',
];

/**
 * Search components by name, formula, or CAS number
 * @param searchTerm - Search string to match
 * @returns Array of matching component data objects
 */
export function searchComponents(searchTerm: string): ComponentData[] {
  const lowerSearch = searchTerm.toLowerCase();
  return Object.values(COMPONENT_DATABASE).filter(
    (c) =>
      c.name.toLowerCase().includes(lowerSearch) ||
      c.formula.toLowerCase().includes(lowerSearch) ||
      c.cas.includes(searchTerm)
  );
}
