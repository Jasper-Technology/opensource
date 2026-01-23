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
4. Add tests if applicable
5. Run existing tests to ensure nothing is broken
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
- Peng-Robinson equation of state implementation
- NRTL activity coefficient model
- UNIQUAC model
- Steam tables / IAPWS-IF97

**Unit Operations**
- Rigorous distillation column model
- Absorption column model
- Heat exchanger network synthesis
- Reactor kinetics models

**Property Database**
- Adding more chemicals with accurate property data
- Binary interaction parameters for activity coefficient models
- Critical properties for equation of state calculations

**Documentation**
- API documentation
- Tutorial examples
- Validation against published data

## Questions?

Open an issue with the "question" label or reach out through our website at [jaspertech.org](https://jaspertech.org).
