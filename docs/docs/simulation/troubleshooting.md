---
sidebar_position: 3
---

# Troubleshooting

Common issues when running rigorous mode simulations and how to resolve them.

## "Backend unavailable"

**Cause:** The Railway container is sleeping or restarting (cold start).

**Fix:**
1. Wait approximately 30 seconds.
2. Press **Run** again.
3. If the issue persists after 60 seconds, check [Railway status](https://status.railway.app/).

:::info
The container auto-wakes on the first request. Subsequent requests within the active window respond in 2-10 seconds.
:::

## "Degrees of freedom != 0"

**Cause:** The flowsheet is under-specified (DOF > 0) or over-specified (DOF < 0).

**Fix:**
- **DOF > 0 (under-specified):** Add missing specifications. Common omissions:
  - Feed stream temperature, pressure, or flow rate
  - Feed composition (must be specified for all components)
  - Unit operation parameters (flash temperature, heat duty, split fraction)
- **DOF < 0 (over-specified):** Remove redundant specifications. For example, specifying both outlet temperature and heat duty on a heater over-constrains the system.

```
Example: Flash drum with 3-component feed
  Required specs: T_feed, P_feed, flow, x1, x2 (x3 = 1 - x1 - x2), T_flash, P_flash
  DOF = 0 ✓
```

## "Solver did not converge"

**Cause:** IPOPT could not find a feasible solution within the iteration limit or tolerance.

**Fix (in order of likelihood):**

1. **Check initial guesses.** Poor initial values for temperature and pressure cause the solver to diverge. Ensure feed conditions are physically reasonable.
2. **Reduce complexity.** Solve a simpler sub-flowsheet first (e.g., just the feed and first unit), then add blocks incrementally.
3. **Increase iterations.** Set `max_iterations` to 200 or 500 for large flowsheets.
4. **Try a different property package.** Some models are more robust for certain chemical systems. SRK and PR generally converge more reliably than activity coefficient models.
5. **Check for impossible specifications.** A heater cannot cool below ambient if duty is constrained positive. A flash at conditions outside the two-phase envelope will produce trivial solutions.

:::warning
If the solver reports "infeasible," the specifications are likely physically inconsistent. Review your feed conditions and unit parameters before increasing iterations.
:::

## "Rate limit exceeded"

**Cause:** More than 10 simulation submissions in the last 60 seconds from your IP.

**Fix:** Wait 1 minute. The rolling window resets automatically.

:::tip
Use Quick mode for rapid iteration and topology validation. Switch to Rigorous mode only for final solves.
:::

## Validation Errors

These errors are caught **before** the solver runs.

### Disconnected blocks

```
Error: Block "Heater-1" has no inlet connection
```

Every unit operation (except Feed blocks) must have at least one connected inlet. Check that all arcs are properly connected in the flowsheet editor.

### Missing specifications

```
Error: Feed "Feed-1" missing required specification: pressure
```

All Feed blocks require temperature, pressure, total flow, and composition for every component in the system.

### Compositions do not sum to 1

```
Error: Feed "Feed-1" mole fractions sum to 0.95, expected 1.0
```

Mole fractions for all components in a feed must sum to exactly 1.0 (within floating-point tolerance of 1e-6). Adjust component fractions so they total 1.0.

### Unknown component

```
Error: Component "CustomChem" not found in database
```

Rigorous mode draws from a database of 70+ validated components. Custom or misspelled component names are rejected. Check the component selector for available species.

## Still Stuck?

If none of the above resolves your issue:

1. Open the browser developer console (`F12` > Console) and check for network errors.
2. Verify your flowsheet solves in Quick mode first — this validates topology independently of the backend.
3. Simplify the flowsheet to the minimum reproducing case.
