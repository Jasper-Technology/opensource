/**
 * Splitter Block
 *
 * Splits one inlet into multiple outlets with specified fractions.
 * Extracted from blockSolver.ts lines 337-364
 */

import type { BlockFunction } from '../../core/schema-v2';

export const splitterBlock: BlockFunction = (inputs, params, _components) => {
  const inlet = inputs.in;

  if (!inlet) {
    throw new Error('Splitter has no inlet stream');
  }

  // Get split fraction (default to 50/50)
  const split1 = (params.split1 as number) ?? 0.5;
  const split2 = 1.0 - split1;

  if (split1 < 0 || split1 > 1) {
    throw new Error(`Invalid split fraction: ${split1} (must be between 0 and 1)`);
  }

  return {
    outputs: {
      out1: {
        ...inlet,
        flow: inlet.flow * split1,
        H: inlet.H, // Splitter doesn't change enthalpy
      },
      out2: {
        ...inlet,
        flow: inlet.flow * split2,
        H: inlet.H, // Splitter doesn't change enthalpy
      },
    },
  };
};
