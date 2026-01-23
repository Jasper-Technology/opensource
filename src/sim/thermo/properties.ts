/**
 * Thermodynamic Property Calculations
 *
 * This module provides basic thermodynamic property calculations.
 * For production use, integrate with libraries like:
 * - CoolProp (via WASM)
 * - Cantera
 * - DWSIM's thermodynamics engine
 */

// Re-export from the expanded component database
import {
  COMPONENT_DATABASE as EXPANDED_DATABASE,
  type ComponentData,
  getComponentList,
  getComponentsByCategory,
  getComponentById,
  searchComponents,
} from './componentDatabase';

// Re-export for external use
export {
  getComponentList,
  getComponentsByCategory,
  getComponentById,
  searchComponents,
  type ComponentData,
};

// Legacy Component interface for backward compatibility
export interface Component {
  name: string;
  MW: number; // Molecular weight (g/mol)
  Tc: number; // Critical temperature (K)
  Pc: number; // Critical pressure (bar)
  omega: number; // Acentric factor
  Tb: number; // Normal boiling point (K)
  Hf: number; // Heat of formation (kJ/mol)
  Cp_coef: number[]; // Heat capacity coefficients [a, b, c, d, e] for Cp = a + bT + cT^2 + dT^3 + eT^4
}

/**
 * Component database - now using expanded database with 70+ components
 * Maintains backward compatibility with existing code
 */
export const COMPONENT_DATABASE: Record<string, Component> = Object.fromEntries(
  Object.entries(EXPANDED_DATABASE).map(([key, data]) => [
    key,
    {
      name: data.name,
      MW: data.MW,
      Tc: data.Tc,
      Pc: data.Pc,
      omega: data.omega,
      Tb: data.Tb,
      Hf: data.Hf,
      Cp_coef: [...data.Cp_coef],
    },
  ])
);

/**
 * Calculate ideal gas heat capacity (J/mol/K)
 */
export function idealGasCp(component: Component, T: number): number {
  const [a, b, c, d, e] = component.Cp_coef;
  return a + b*T + c*T**2 + d*T**3 + e*T**4;
}

/**
 * Calculate ideal gas enthalpy (kJ/mol)
 * H = Hf + ∫Cp dT from 298.15K to T
 */
export function idealGasEnthalpy(component: Component, T: number): number {
  const T0 = 298.15;
  const [a, b, c, d, e] = component.Cp_coef;
  
  // Integrate Cp from T0 to T
  const deltaH_J = (
    a * (T - T0) +
    (b/2) * (T**2 - T0**2) +
    (c/3) * (T**3 - T0**3) +
    (d/4) * (T**4 - T0**4) +
    (e/5) * (T**5 - T0**5)
  );
  
  return component.Hf + deltaH_J / 1000; // Convert J to kJ
}

/**
 * Calculate mixture enthalpy (kJ/mol)
 */
export function mixtureEnthalpy(
  composition: Record<string, number>, // mole fractions
  T: number,
  _P: number
): number {
  let H_mix = 0;
  
  for (const [compName, moleFrac] of Object.entries(composition)) {
    const comp = COMPONENT_DATABASE[compName];
    if (comp) {
      H_mix += moleFrac * idealGasEnthalpy(comp, T);
    }
  }
  
  return H_mix;
}

/**
 * Calculate vapor pressure using Clausius-Clapeyron equation
 * Returns vapor pressure in Pascal (Pa)
 */
export function vaporPressure(component: Component, T_K: number): number {
  // Clausius-Clapeyron equation:
  // ln(P2/P1) = (Hvap/R) * (1/T1 - 1/T2)
  // At T = Tb, P = 1 atm = 101325 Pa
  const R = 8.314; // J/mol/K
  const T_ref = component.Tb;
  const P_ref = 101325; // Pa (1 atm at boiling point)

  // Trouton's rule: Hvap ≈ 85 J/(mol·K) * Tb
  // More accurate than 40.7 * MW
  const Hvap = 85 * T_ref; // J/mol

  // Calculate vapor pressure in Pa
  const P_vap_Pa = P_ref * Math.exp((Hvap / R) * (1 / T_ref - 1 / T_K));

  // Clamp to reasonable values
  if (P_vap_Pa < 1) return 1; // Minimum 1 Pa
  if (P_vap_Pa > 1e9) return 1e9; // Maximum 10000 bar

  return P_vap_Pa;
}

/**
 * Calculate K-values (vapor-liquid equilibrium)
 * K_i = y_i / x_i = P_vap_i / P_total (Raoult's Law for ideal)
 * P is in Pascal (Pa)
 */
export function calculateKValues(
  components: string[],
  T: number,
  P: number // Pressure in Pascal
): Record<string, number> {
  const K_values: Record<string, number> = {};

  for (const compName of components) {
    const comp = COMPONENT_DATABASE[compName];
    if (comp) {
      const P_vap = vaporPressure(comp, T); // Returns Pa
      K_values[compName] = P_vap / P; // Both in Pa, so K is dimensionless
    } else {
      // Default K for unknown components (assume moderately volatile)
      K_values[compName] = 1.0;
    }
  }

  return K_values;
}

/**
 * Rachford-Rice flash calculation
 * Solves: Σ[z_i(K_i - 1)/(1 + V(K_i - 1))] = 0
 * Returns vapor fraction (V)
 */
export function rachfordRiceFlash(
  z: Record<string, number>, // Feed composition
  K: Record<string, number>  // K-values
): number {
  const components = Object.keys(z);
  
  // Initial guess for vapor fraction
  let V = 0.5;
  
  // Newton-Raphson iteration
  for (let iter = 0; iter < 50; iter++) {
    let f = 0;
    let df = 0;
    
    for (const comp of components) {
      const z_i = z[comp];
      const K_i = K[comp];
      const denom = 1 + V * (K_i - 1);
      
      f += z_i * (K_i - 1) / denom;
      df -= z_i * (K_i - 1)**2 / (denom**2);
    }
    
    // Newton step
    const V_new = V - f / df;
    
    // Bounds
    if (V_new < 0) V = 0;
    else if (V_new > 1) V = 1;
    else V = V_new;
    
    // Check convergence
    if (Math.abs(f) < 1e-6) {
      break;
    }
  }
  
  return V;
}

/**
 * Calculate phase compositions from flash
 */
export function flashComposition(
  z: Record<string, number>,
  K: Record<string, number>,
  V: number
): { vapor: Record<string, number>; liquid: Record<string, number> } {
  const vapor: Record<string, number> = {};
  const liquid: Record<string, number> = {};
  
  for (const [comp, z_i] of Object.entries(z)) {
    const K_i = K[comp];
    
    // Rachford-Rice equation rearranged
    liquid[comp] = z_i / (1 + V * (K_i - 1));
    vapor[comp] = K_i * liquid[comp];
  }
  
  return { vapor, liquid };
}

/**
 * Calculate density (kg/m³)
 * Using ideal gas law for vapor, simple correlation for liquid
 * P is in Pascal (Pa)
 */
export function density(
  composition: Record<string, number>,
  T: number,
  P: number, // Pressure in Pascal
  phase: 'V' | 'L'
): number {
  if (phase === 'V') {
    // Ideal gas: ρ = PM/(RT)
    // P in Pa, M in g/mol, R in J/(mol·K), T in K
    // Result: ρ in g/m³, divide by 1000 for kg/m³
    let MW_avg = 0;
    for (const [comp, frac] of Object.entries(composition)) {
      const component = COMPONENT_DATABASE[comp];
      if (component) MW_avg += frac * component.MW;
    }

    const R = 8.314; // J/(mol·K)
    // ρ = PM/(RT) -> [Pa][g/mol] / [J/(mol·K)][K] = [g/m³]
    // Since 1 Pa = 1 J/m³, units work out to g/m³
    return (P * MW_avg) / (R * T * 1000); // kg/m³
  } else {
    // Liquid: use typical liquid densities
    // This is very simplified - should use correlations like Rackett
    return 1000; // kg/m³ (placeholder)
  }
}

/**
 * Determine phase state of a mixture at given T and P
 * Uses flash calculation to determine if all vapor, all liquid, or two-phase
 * Returns: 'V' (all vapor), 'L' (all liquid), or 'VL' (two-phase)
 */
export function determinePhase(
  composition: Record<string, number>,
  T: number,
  P: number // Pressure in Pascal
): 'V' | 'L' | 'VL' {
  const components = Object.keys(composition);

  // Calculate K-values
  const K = calculateKValues(components, T, P);

  // Check bubble point: if all K_i > 1, mixture is superheated vapor
  // Check dew point: if all K_i < 1, mixture is subcooled liquid

  const K_values = Object.values(K);
  const allKGreaterThanOne = K_values.every((k) => k > 1);
  const allKLessThanOne = K_values.every((k) => k < 1);

  if (allKGreaterThanOne) {
    return 'V'; // Superheated vapor (all components want to be vapor)
  }

  if (allKLessThanOne) {
    return 'L'; // Subcooled liquid (all components want to be liquid)
  }

  // Mixed K-values - need to check if we're in two-phase region
  // Use Rachford-Rice to find vapor fraction
  const V = rachfordRiceFlash(composition, K);

  if (V <= 0.001) {
    return 'L'; // Essentially all liquid
  } else if (V >= 0.999) {
    return 'V'; // Essentially all vapor
  } else {
    return 'VL'; // Two-phase
  }
}

/**
 * Calculate vapor fraction for a mixture at given T and P
 * Returns value between 0 (all liquid) and 1 (all vapor)
 */
export function calculateVaporFraction(
  composition: Record<string, number>,
  T: number,
  P: number // Pressure in Pascal
): number {
  const components = Object.keys(composition);
  const K = calculateKValues(components, T, P);

  // Check bounds
  const K_values = Object.values(K);
  if (K_values.every((k) => k > 1)) return 1.0; // All vapor
  if (K_values.every((k) => k < 1)) return 0.0; // All liquid

  return rachfordRiceFlash(composition, K);
}

