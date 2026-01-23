/**
 * Block Functions Registry
 *
 * All block functions are pure functions that take inputs and params
 * and return outputs. Each block type is implemented in its own file.
 */

import type { BlockFunction } from '../../core/schema-v2';
import { feedBlock } from './feed';
import { mixerBlock } from './mixer';
import { splitterBlock } from './splitter';
import { heaterBlock } from './heater';
import { coolerBlock } from './cooler';
import { flashBlock } from './flash';
import { pumpBlock } from './pump';

/**
 * Registry of all block functions
 * Add new block types here
 */
export const BLOCK_FUNCTIONS: Record<string, BlockFunction> = {
  Feed: feedBlock,
  Mixer: mixerBlock,
  Splitter: splitterBlock,
  Heater: heaterBlock,
  Cooler: coolerBlock,
  Flash: flashBlock,
  Pump: pumpBlock,

  // TODO: Implement these
  Compressor: notImplemented('Compressor'),
  Valve: notImplemented('Valve'),
  HeatExchanger: notImplemented('HeatExchanger'),
  Absorber: notImplemented('Absorber'),
  Stripper: notImplemented('Stripper'),
  DistillationColumn: notImplemented('DistillationColumn'),
  Reactor: notImplemented('Reactor'),
  Separator: notImplemented('Separator'),
  Sink: sinkBlock,
  TextBox: notImplemented('TextBox'),
};

/**
 * Placeholder for unimplemented blocks
 */
function notImplemented(blockType: string): BlockFunction {
  return () => {
    throw new Error(`Block type "${blockType}" not yet implemented in V2 engine`);
  };
}

/**
 * Sink block (does nothing, just accepts input)
 */
function sinkBlock(): ReturnType<BlockFunction> {
  return { outputs: {} };
}
