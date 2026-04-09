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
 * Calculate vapor pressure using Lee-Kesler correlation
 * ln(Pr) = f0(Tr) + omega * f1(Tr)
 * Uses Tc, Pc, omega from database. Error ~1-3% vs 10-15% for Trouton's rule.
 * Returns vapor pressure in Pascal (Pa)
 */
export function vaporPressure(component: Component, T_K: number): number {
  // Guard: T must be positive and finite
  if (!Number.isFinite(T_K) || T_K <= 0) return 1; // minimum vapor pressure
  if (component.Tc <= 0 || component.Pc <= 0) return 1;
  const Tr = T_K / component.Tc;

  // Lee-Kesler correlation
  const f0 = 5.92714 - 6.09648 / Tr - 1.28862 * Math.log(Tr) + 0.169347 * Tr ** 6;
  const f1 = 15.2518 - 15.6875 / Tr - 13.4721 * Math.log(Tr) + 0.43577 * Tr ** 6;

  const lnPr = f0 + component.omega * f1;
  const Pc_Pa = component.Pc * 1e5; // bar -> Pa

  // Anchor correction: at Tb, Pvap should equal 101325 Pa
  // Compute LK prediction at Tb and apply multiplicative correction
  const Tr_b = component.Tb / component.Tc;
  const f0_b = 5.92714 - 6.09648 / Tr_b - 1.28862 * Math.log(Tr_b) + 0.169347 * Tr_b ** 6;
  const f1_b = 15.2518 - 15.6875 / Tr_b - 13.4721 * Math.log(Tr_b) + 0.43577 * Tr_b ** 6;
  const lnPr_b = f0_b + component.omega * f1_b;
  const P_at_Tb = Pc_Pa * Math.exp(lnPr_b);
  const correction = P_at_Tb > 0 && Number.isFinite(P_at_Tb) ? 101325 / P_at_Tb : 1; // anchors Pvap(Tb) = 1 atm exactly

  const P_vap_Pa = Pc_Pa * Math.exp(lnPr) * correction;

  // Clamp to reasonable values (also catches NaN/Infinity)
  if (!Number.isFinite(P_vap_Pa) || P_vap_Pa < 1) return 1;
  if (P_vap_Pa > 1e9) return 1e9;

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
  const K_values: Record<string, number> = Object.create(null);

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
    
    // Newton step — guard against singular Jacobian
    if (Math.abs(df) < 1e-30) break;
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
  const vapor: Record<string, number> = Object.create(null);
  const liquid: Record<string, number> = Object.create(null);
  
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
    // Liquid: Rackett equation
    // Vs = (R*Tc/Pc) * Zra^(1 + (1-Tr)^(2/7))
    // Zra = 0.29056 - 0.08775*omega
    const R_gas = 8.314;
    let rho_mix = 0;
    let totalFrac = 0;
    for (const [comp, frac] of Object.entries(composition)) {
      const component = COMPONENT_DATABASE[comp];
      if (!component || frac <= 0) continue;
      const Tr = Math.min(T / component.Tc, 0.999); // clamp below Tc
      // Use modified Rackett with component-specific Zra where available
      // Water (Zra=0.2338) is anomalous due to hydrogen bonding
      const Zra = component.name === 'Water' ? 0.2338 : 0.29056 - 0.08775 * component.omega;
      const Pc_Pa = component.Pc * 1e5;
      const Vs = (R_gas * component.Tc / Pc_Pa) * Math.pow(Math.max(Zra, 0.1), 1 + Math.pow(1 - Tr, 2 / 7)); // m3/mol
      const rho_i = component.MW / (Vs * 1e6); // kg/m3 (MW g/mol, Vs m3/mol -> g/m3 -> /1000 = kg/m3... let me redo)
      // Vs in m3/mol, MW in g/mol -> density = MW/1000 / Vs = kg/m3
      const rho_comp = (component.MW / 1000) / Vs; // kg/m3
      rho_mix += frac / rho_comp; // inverse mixing (volume additivity)
      totalFrac += frac;
    }
    if (rho_mix <= 0 || totalFrac <= 0) return 800; // fallback
    return totalFrac / rho_mix; // harmonic mean density
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

/**
 * Calculate ideal gas entropy (J/mol/K) relative to reference state (298.15 K, 1 atm)
 * S = S_ref + integral(Cp/T dT, T0 to T) - R*ln(P/P_ref)
 */
export function idealGasEntropy(component: Component, T: number, P_Pa: number): number {
  if (!Number.isFinite(T) || T <= 0) return 0;
  if (!Number.isFinite(P_Pa) || P_Pa <= 0) return 0;
  const T0 = 298.15;
  const P_ref = 101325; // 1 atm
  const R = 8.314;
  const [a, b, c, d, e] = component.Cp_coef;

  const integral = a * Math.log(T / T0)
    + b * (T - T0)
    + (c / 2) * (T * T - T0 * T0)
    + (d / 3) * (T ** 3 - T0 ** 3)
    + (e / 4) * (T ** 4 - T0 ** 4);

  return integral - R * Math.log(P_Pa / P_ref);
}

/**
 * Calculate heat of reaction at temperature T (kJ/mol of reaction extent)
 * deltaH_rxn(T) = sum(nu_i * Hf_i) + integral(sum(nu_i * Cp_i) dT, 298.15 to T)
 */
export function heatOfReaction(
  stoichiometry: Record<string, number>,
  T: number,
): number {
  const T0 = 298.15;
  let deltaHf = 0;
  let deltaCp_a = 0, deltaCp_b = 0, deltaCp_c = 0, deltaCp_d = 0, deltaCp_e = 0;

  for (const [compName, nu] of Object.entries(stoichiometry)) {
    const comp = COMPONENT_DATABASE[compName];
    if (!comp) continue;
    deltaHf += nu * comp.Hf; // kJ/mol
    deltaCp_a += nu * comp.Cp_coef[0];
    deltaCp_b += nu * comp.Cp_coef[1];
    deltaCp_c += nu * comp.Cp_coef[2];
    deltaCp_d += nu * comp.Cp_coef[3];
    deltaCp_e += nu * comp.Cp_coef[4];
  }

  // Integral of deltaCp from T0 to T (J/mol)
  const deltaCp_integral =
    deltaCp_a * (T - T0)
    + (deltaCp_b / 2) * (T * T - T0 * T0)
    + (deltaCp_c / 3) * (T ** 3 - T0 ** 3)
    + (deltaCp_d / 4) * (T ** 4 - T0 ** 4)
    + (deltaCp_e / 5) * (T ** 5 - T0 ** 5);

  return deltaHf + deltaCp_integral / 1000; // kJ/mol
}

