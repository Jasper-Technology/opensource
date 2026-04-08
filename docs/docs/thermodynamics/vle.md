---
sidebar_position: 3
---

# Vapor-Liquid Equilibrium

VLE calculations determine phase splits and compositions. Jasper supports three VLE models through the PropertyPackage interface.

## Property Methods

### Ideal (Raoult's Law)

```
Ki = Psat_i(T) / P
```

Best for: ideal mixtures at low to moderate pressure (benzene-toluene, light hydrocarbons near atmospheric).

### Peng-Robinson (Phi-Phi)

```
Ki = φL_i / φV_i
```

The PR EOS solves a cubic equation for compressibility Z, then computes fugacity coefficients for each phase. The flash iterates K-values until fugacity equality is satisfied.

Best for: hydrocarbons, gases, high-pressure systems, cryogenic separations.

### NRTL (Gamma-Phi)

```
Ki = γi · Psat_i(T) / P
```

Activity coefficients γ are calculated from binary interaction parameters (BIPs). The flash iterates K-values with composition-dependent γ.

Best for: polar/non-ideal liquid mixtures — ethanol-water, amine-water, acetone-chloroform.

## Vapor Pressure (Lee-Kesler)

Replaces the previous Clausius-Clapeyron/Trouton's rule with the Lee-Kesler correlation:

```
ln(Pr) = f0(Tr) + ω · f1(Tr)
```

Where:
- `Tr = T/Tc` (reduced temperature)
- `ω` = acentric factor
- Anchored to boiling point (Pvap = 1 atm at Tb exactly)

Accuracy: 1-3% across the full range, vs 10-15% for the old Trouton's rule.

## Flash Calculation

### Rachford-Rice Equation

```
Σ zi(Ki - 1) / (1 + V(Ki - 1)) = 0
```

Solved via Newton-Raphson iteration (max 50 iterations, tolerance 1e-6).

### PR Flash Algorithm

1. Initialize K from Wilson correlation: `Ki = exp(5.373(1+ω)(1-1/Tr)) / Pr`
2. Solve Rachford-Rice for vapor fraction V
3. Compute liquid (x) and vapor (y) compositions
4. Solve PR cubic for ZL (liquid) and ZV (vapor)
5. Compute fugacity coefficients for each phase
6. Update: `Ki = φL_i / φV_i`
7. Repeat until max |ΔK/K| < 1e-6

### NRTL Flash Algorithm

1. Initialize K from Raoult's Law
2. Solve Rachford-Rice for V
3. Compute liquid compositions x
4. Evaluate γ = nrtlGamma(components, x, T)
5. Update: `Ki = γi · Psat_i / P`
6. Repeat until max |ΔK/K| < 1e-6

## BIP Database

The NRTL model includes ~20 common binary pairs:

| System | Example Pairs |
|--------|--------------|
| Water-Alcohol | H2O/EtOH, H2O/MeOH |
| Water-Organic | H2O/Acetone, H2O/Acetic acid |
| Amine-Water | MEA/H2O, DEA/H2O, MDEA/H2O |
| Hydrocarbon | Benzene/Cyclohexane, Benzene/Toluene |
| Organic-Organic | Acetone/Chloroform, EtOH/Benzene |

Pairs without BIP data fall back to ideal behavior (γ = 1).

## Azeotrope Prediction

With NRTL, Jasper correctly predicts minimum-boiling azeotropes:
- Ethanol-water at ~89 mol% ethanol, 78.1°C
- The vapor is enriched in ethanol at low concentrations (γ_EtOH > 5 at dilute)
