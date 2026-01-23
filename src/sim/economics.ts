import type { SimulationRun, EconomicConfig } from '../core/schema';

// Re-export sizing functions for convenience
export {
  sizeHeatExchanger,
  sizePump,
  sizeCompressor,
  sizeVessel,
  estimateFlashVolume,
  calculateEquipmentCAPEX,
  convertBlocksToResults,
} from './sizing';

export type { EquipmentSize, BlockResult, CAPEXResult } from './sizing';

/**
 * Compute Cost of Manufacturing (COM) from simulation results
 *
 * Uses utility consumption and emissions data to calculate operating costs.
 * This is a simplified operating cost estimate.
 *
 * @param run - Simulation run with KPIs
 * @param economics - Economic configuration with utility prices
 * @returns Annual operating cost in $/year
 */
export function computeCOM(run: SimulationRun, economics?: EconomicConfig): number {
  const steam = (typeof run.kpis.steam === 'number' ? run.kpis.steam : 0);
  const electricity = (typeof run.kpis.electricity === 'number' ? run.kpis.electricity : 0);
  const co2Emissions = (typeof run.kpis.CO2_emissions === 'number' ? run.kpis.CO2_emissions : 0);
  const capexProxy = (typeof run.kpis.CAPEX_proxy === 'number' ? run.kpis.CAPEX_proxy : 0);

  const steamPrice = economics?.steamPrice || 10; // $/GJ
  const electricityPrice = economics?.electricityPrice || 0.1; // $/kWh
  const co2Price = economics?.co2Price || 50; // $/ton
  const capexFactor = economics?.capexFactor || 0.1;

  return (
    steam * steamPrice +
    electricity * electricityPrice +
    co2Emissions * co2Price +
    capexProxy * capexFactor
  );
}

// ============================================================================
// EXTENDED ECONOMIC CONFIGURATION
// ============================================================================

export interface ExtendedEconomicConfig extends EconomicConfig {
  // CAPEX parameters
  annualizationFactor?: number; // For converting CAPEX to annual cost (default: 0.15)
  installationFactor?: number; // Lang factor for installed cost (default: 3.0)
  contingencyFactor?: number; // Contingency percentage (default: 0.15)

  // Operating parameters
  operatingHours?: number; // Hours per year (default: 8000)
  laborCost?: number; // $/year per operator (default: 75000)
  operatorsPerShift?: number; // Number of operators (default: 2)
  maintenanceFactor?: number; // Maintenance as fraction of CAPEX (default: 0.03)
}

// ============================================================================
// TOTAL ANNUAL COST CALCULATION
// ============================================================================

/**
 * Calculate Total Annual Cost (TAC) including CAPEX and OPEX
 *
 * TAC = Annualized CAPEX + Annual Operating Cost
 *
 * Annualized CAPEX = CAPEX × Installation Factor × (1 + Contingency) × Annualization Factor
 *
 * Annual Operating Cost = Utility Costs + Labor + Maintenance
 *
 * @param run - Simulation run with KPIs
 * @param equipmentCAPEX - Total equipment purchase cost from sizing (USD)
 * @param economics - Extended economic configuration
 * @returns Object with detailed cost breakdown
 */
export function calculateTotalAnnualCost(
  run: SimulationRun,
  equipmentCAPEX: number,
  economics?: ExtendedEconomicConfig
): {
  annualizedCAPEX: number;
  utilityCost: number;
  laborCost: number;
  maintenanceCost: number;
  totalOpex: number;
  totalAnnualCost: number;
  installedCAPEX: number;
} {
  // Default economic parameters
  const config = {
    annualizationFactor: economics?.annualizationFactor ?? 0.15,
    installationFactor: economics?.installationFactor ?? 3.0,
    contingencyFactor: economics?.contingencyFactor ?? 0.15,
    operatingHours: economics?.operatingHours ?? 8000,
    laborCost: economics?.laborCost ?? 75000,
    operatorsPerShift: economics?.operatorsPerShift ?? 2,
    maintenanceFactor: economics?.maintenanceFactor ?? 0.03,
  };

  // Calculate installed CAPEX (including installation and contingency)
  const installedCAPEX =
    equipmentCAPEX * config.installationFactor * (1 + config.contingencyFactor);

  // Annualized CAPEX
  const annualizedCAPEX = installedCAPEX * config.annualizationFactor;

  // Utility costs (annual)
  const steam = (typeof run.kpis.steam === 'number' ? run.kpis.steam : 0);
  const electricity = (typeof run.kpis.electricity === 'number' ? run.kpis.electricity : 0);
  const cooling = (typeof run.kpis.cooling === 'number' ? run.kpis.cooling : 0);

  const steamPrice = economics?.steamPrice ?? 10; // $/GJ
  const electricityPrice = economics?.electricityPrice ?? 0.1; // $/kWh
  const coolingPrice = 2; // $/GJ (cooling water is cheaper than steam)

  // Utility cost = rate × price × operating hours
  // Steam and cooling are in GJ/h, electricity in kW
  const utilityCost =
    steam * steamPrice * config.operatingHours +
    electricity * electricityPrice * config.operatingHours +
    cooling * coolingPrice * config.operatingHours;

  // Labor cost (4.8 operators for 24/7 operation with 3 shifts)
  const laborCost = config.operatorsPerShift * 4.8 * config.laborCost;

  // Maintenance cost (fraction of installed CAPEX)
  const maintenanceCost = installedCAPEX * config.maintenanceFactor;

  // Total operating cost
  const totalOpex = utilityCost + laborCost + maintenanceCost;

  // Total Annual Cost
  const totalAnnualCost = annualizedCAPEX + totalOpex;

  return {
    annualizedCAPEX,
    utilityCost,
    laborCost,
    maintenanceCost,
    totalOpex,
    totalAnnualCost,
    installedCAPEX,
  };
}

/**
 * Calculate simple payback period
 *
 * @param installedCAPEX - Total installed capital cost (USD)
 * @param annualSavings - Annual savings or revenue (USD/year)
 * @returns Payback period in years
 */
export function calculatePaybackPeriod(
  installedCAPEX: number,
  annualSavings: number
): number {
  if (annualSavings <= 0) {
    return Infinity;
  }
  return installedCAPEX / annualSavings;
}

/**
 * Calculate Net Present Value (NPV)
 *
 * @param installedCAPEX - Total installed capital cost (USD)
 * @param annualCashFlow - Annual net cash flow (USD/year)
 * @param discountRate - Discount rate (e.g., 0.10 for 10%)
 * @param projectLife - Project lifetime in years
 * @returns NPV in USD
 */
export function calculateNPV(
  installedCAPEX: number,
  annualCashFlow: number,
  discountRate: number = 0.10,
  projectLife: number = 20
): number {
  let npv = -installedCAPEX;

  for (let year = 1; year <= projectLife; year++) {
    npv += annualCashFlow / Math.pow(1 + discountRate, year);
  }

  return npv;
}

