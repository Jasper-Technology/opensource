---
sidebar_position: 2
---

# Mixer / Splitter

Mixer combines streams. Splitter divides a stream.

## Mixer

```typescript
export function solveMixer(inlets: StreamData[]): StreamData {
  const totalFlow = inlets.reduce((sum, s) => sum + s.flow, 0);
  
  const composition: Record<string, number> = {};
  for (const stream of inlets) {
    for (const [compId, frac] of Object.entries(stream.composition)) {
      composition[compId] = (composition[compId] || 0) + 
        (stream.flow / totalFlow) * frac;
    }
  }
  
  return { flow: totalFlow, composition };
}
```

## Splitter

| Parameter | Type | Description |
|-----------|------|-------------|
| splitRatio | Number | Fraction to first outlet (0-1) |

```typescript
export function solveSplitter(inlet: StreamData, splitRatio: number) {
  return {
    out1: { ...inlet, flow: inlet.flow * splitRatio },
    out2: { ...inlet, flow: inlet.flow * (1 - splitRatio) }
  };
}
```
