# Contributing to Jasper

Thank you for your interest in contributing to Jasper!

## How to Contribute

### Reporting Issues

- Use GitHub Issues to report bugs or suggest features
- Include as much detail as possible (steps to reproduce, expected vs actual behavior)
- For simulation accuracy issues, include the flowsheet configuration and expected results

### Code Contributions

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Run `npx tsc --noEmit` to verify types
5. Run `npx tsx src/sim/thermo/__tests__/quickmode-parity.test.ts` to verify correctness
6. Commit with clear messages
7. Push to your fork
8. Open a Pull Request

### Code Style

- TypeScript with strict mode
- Use meaningful variable names
- Add JSDoc comments for public functions
- Keep functions focused and reasonably sized

### Areas We Need Help

**Thermodynamics**
- Wilson/UNIQUAC activity coefficient models
- UNIFAC group contribution method
- Henry's Law for dissolved gases
- Steam tables (IAPWS-IF97)

**Separation Operations**
- Rigorous stage-by-stage distillation (MESH equations)
- Packed column HETP correlations
- Reactive distillation

**Property Database**
- Expand NRTL BIP database beyond ~20 pairs
- Add more chemicals beyond 70 components
- Validate against DECHEMA VLE data

**Documentation**
- Tutorial examples for common systems
- Validation against published data
- Video walkthroughs

### Completed (no longer needed)

- ~~Peng-Robinson EOS~~ — `pengRobinson.ts`
- ~~NRTL activity coefficients~~ — `nrtl.ts` + `bipDatabase.ts`
- ~~Shortcut distillation~~ — Fenske-Underwood-Gilliland in `blockSolver.ts`
- ~~Reactor heat of reaction~~ — `heatOfReaction()` in `properties.ts`
- ~~Recycle convergence~~ — Wegstein acceleration in `blockSolver.ts`
- ~~Kremser absorber/stripper~~ — in `blockSolver.ts`

## Questions?

Open an issue with the "question" label or reach out through our website at [jaspertech.org](https://jaspertech.org).
