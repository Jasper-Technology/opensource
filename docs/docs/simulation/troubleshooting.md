---
sidebar_position: 6
---

# Troubleshooting

Common issues across the simulation engines (Quick, Rigorous) and agent-driven Optimize, plus how to resolve them.

## "Backend unavailable"

**Cause:** The Railway container hosting the Rigorous (DWSIM) backend or the IDAES optimization backend is sleeping or restarting (cold start).

**Fix:**
1. Wait approximately 30 seconds.
2. Press **Run** again.
3. If the issue persists after 60 seconds, check [Railway status](https://status.railway.app/).

:::info
The container auto-wakes on the first request. Subsequent requests within the active window respond in 2 – 10 seconds.
:::

## Rigorous (DWSIM) errors

### `FileNotFoundException: DWSIM.Automation.dll`

**Cause:** `DWSIM_PATH` environment variable is unset or points at a directory that doesn't contain the DWSIM DLL set. Only relevant when self-hosting the Rigorous backend.

**Fix:** Install DWSIM and set `DWSIM_PATH` to its install directory (e.g. `/usr/local/lib/dwsim`). The directory must contain `DWSIM.Automation.dll` and its transitive dependencies. The assembly resolver in `Program.cs` reads from this path on demand.

### "Compound not found: &lt;name&gt;"

**Cause:** DWSIM couldn't resolve the component via CAS → name → formula fallback.

**Fix:** Add the CAS number to the component in Jasper (most reliable), or check that the name matches DWSIM's compound database casing.

### Rigorous solve timeout (&gt;5 min)

**Cause:** The Rigorous backend caps each job at 5 minutes (`Program.cs`).

**Fix:** Difficult recycles are the most common cause. Tighten tear-stream specifications, simplify the flowsheet, or split it into stages.

### "Rigorous simulation requires Jasper Pro"

**Cause:** Rigorous mode is part of the Jasper Pro tier.

**Fix:** Upgrade to Pro, or stay in Quick mode for screening / ideal systems.

## Optimize (IDAES, agent-driven) errors

:::note
Optimization is invoked through the Jasper agent — ask in chat (e.g. *"minimize H1 duty by varying its outlet temperature between 305 K and 360 K"*). There is no separate Optimize button. Errors below surface either in the agent's tool-call result or in the inline result card.
:::

### "Degrees of freedom != 0"

**Cause:** The flowsheet is under-specified (DOF > 0) or over-specified (DOF < 0). IDAES requires an exactly square system.

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

### "Solver did not converge" (IPOPT)

**Cause:** IPOPT could not find a feasible solution within the iteration limit or tolerance.

**Fix (in order of likelihood):**

1. **Check initial guesses.** Poor initial values for temperature and pressure cause the solver to diverge.
2. **Reduce complexity.** Solve a simpler sub-flowsheet first, then add blocks incrementally.
3. **Increase iterations.** Set `max_iterations` to 200 or 500 for large flowsheets.
4. **Try a different property package.** SRK and PR generally converge more reliably than activity coefficient models.
5. **Check for impossible specifications.** A heater can't cool below ambient with positive duty. A flash outside the two-phase envelope produces trivial solutions.

:::warning
If the solver reports "infeasible," the specifications are likely physically inconsistent. Review your feed conditions and unit parameters before increasing iterations.
:::

### "Rate limit exceeded"

**Cause:** More than 10 simulation submissions in the last 60 seconds from your IP (Optimize backend only).

**Fix:** Wait 1 minute. The rolling window resets automatically.

## Validation errors (all modes)

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

Mole fractions must sum to 1.0 within floating-point tolerance.

### Unknown component

```
Error: Component "CustomChem" not found in database
```

Each mode draws from its own component database. Custom or misspelled names are rejected. Check the component selector for available species.

## Still stuck?

If none of the above resolves your issue:

1. Open the browser developer console (`F12` → Console) and check for network errors.
2. Verify your flowsheet solves in **Quick** mode first — this validates topology independently of any backend.
3. Simplify the flowsheet to the minimum reproducing case.
