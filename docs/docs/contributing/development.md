---
sidebar_position: 1
---

# Development Setup

Guide to contributing to Jasper.

## Prerequisites

- Node.js 18+
- npm or yarn

## Clone

```bash
git clone https://github.com/Jasper-Technology/opensource.git
cd opensource
```

## Project Structure

```
opensource/
├── src/
│   ├── core/
│   │   └── schema.ts
│   └── sim/
│       ├── engine-v2.ts
│       ├── blocks/
│       └── thermo/
├── docs/
└── README.md
```

## Making Changes

1. Create a feature branch
2. Make changes and add tests
3. Submit a pull request

## Areas for Contribution

**High Priority:**
- Peng-Robinson EOS
- NRTL activity coefficients
- More unit operations

**Medium Priority:**
- Property database expansion
- Documentation improvements
