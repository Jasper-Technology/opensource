/**
 * Sandboxed arithmetic evaluator for agent-defined sizing formulas.
 *
 * Deliberately NOT `eval`/`new Function`: a hand-written recursive-descent parser
 * over a fixed grammar (numbers, named variables, the binary operators + - * / %
 * ^, unary minus, parentheses, and a whitelist of math functions). Anything
 * outside the grammar — property access, calls to non-whitelisted names, commas
 * outside a function's args, assignment — throws. This is the security boundary
 * for `CustomSizingSpec.expression`; treat every input as hostile.
 */

const FUNCTIONS: Record<string, (...args: number[]) => number> = {
  sqrt: Math.sqrt,
  cbrt: Math.cbrt,
  abs: Math.abs,
  exp: Math.exp,
  ln: Math.log,
  log: Math.log,
  log10: Math.log10,
  pow: (a, b) => a ** b,
  min: Math.min,
  max: Math.max,
};

const CONSTANTS: Record<string, number> = { pi: Math.PI, e: Math.E };

type Token =
  | { t: 'num'; v: number }
  | { t: 'id'; v: string }
  | { t: 'op'; v: string }
  | { t: 'lparen' }
  | { t: 'rparen' }
  | { t: 'comma' };

function tokenize(src: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (c === ' ' || c === '\t' || c === '\n' || c === '\r') { i++; continue; }
    if (c >= '0' && c <= '9' || (c === '.' && src[i + 1] >= '0' && src[i + 1] <= '9')) {
      let j = i;
      while (j < src.length && /[0-9.eE+-]/.test(src[j])) {
        // allow exponent sign only right after e/E
        if ((src[j] === '+' || src[j] === '-') && !(src[j - 1] === 'e' || src[j - 1] === 'E')) break;
        j++;
      }
      const num = Number(src.slice(i, j));
      if (!Number.isFinite(num)) throw new Error(`invalid number "${src.slice(i, j)}"`);
      tokens.push({ t: 'num', v: num });
      i = j;
      continue;
    }
    if (/[a-zA-Z_]/.test(c)) {
      let j = i;
      while (j < src.length && /[a-zA-Z0-9_]/.test(src[j])) j++;
      tokens.push({ t: 'id', v: src.slice(i, j) });
      i = j;
      continue;
    }
    if ('+-*/%^'.includes(c)) { tokens.push({ t: 'op', v: c }); i++; continue; }
    if (c === '(') { tokens.push({ t: 'lparen' }); i++; continue; }
    if (c === ')') { tokens.push({ t: 'rparen' }); i++; continue; }
    if (c === ',') { tokens.push({ t: 'comma' }); i++; continue; }
    throw new Error(`unexpected character "${c}"`);
  }
  return tokens;
}

/**
 * Evaluate `expression` against a variable map. Unknown identifiers, unknown
 * functions, or malformed syntax throw — callers must catch and flag.
 */
export function safeEval(expression: string, vars: Record<string, number>): number {
  const tokens = tokenize(expression);
  let pos = 0;

  const peek = (): Token | undefined => tokens[pos];
  const next = (): Token => {
    const tk = tokens[pos++];
    if (!tk) throw new Error('unexpected end of expression');
    return tk;
  };

  // expr := term (('+' | '-') term)*
  function parseExpr(): number {
    let value = parseTerm();
    for (let tk = peek(); tk && tk.t === 'op' && (tk.v === '+' || tk.v === '-'); tk = peek()) {
      next();
      const rhs = parseTerm();
      value = tk.v === '+' ? value + rhs : value - rhs;
    }
    return value;
  }

  // term := factor (('*' | '/' | '%') factor)*
  function parseTerm(): number {
    let value = parseFactor();
    for (let tk = peek(); tk && tk.t === 'op' && (tk.v === '*' || tk.v === '/' || tk.v === '%'); tk = peek()) {
      next();
      const rhs = parseFactor();
      if (tk.v === '*') value *= rhs;
      else if (tk.v === '/') value /= rhs;
      else value %= rhs;
    }
    return value;
  }

  // factor := unary ('^' factor)?   (right-associative power)
  function parseFactor(): number {
    const base = parseUnary();
    const tk = peek();
    if (tk && tk.t === 'op' && tk.v === '^') {
      next();
      return base ** parseFactor();
    }
    return base;
  }

  // unary := ('-' | '+') unary | primary
  function parseUnary(): number {
    const tk = peek();
    if (tk && tk.t === 'op' && (tk.v === '-' || tk.v === '+')) {
      next();
      const v = parseUnary();
      return tk.v === '-' ? -v : v;
    }
    return parsePrimary();
  }

  // primary := num | id | id '(' args ')' | '(' expr ')'
  function parsePrimary(): number {
    const tk = next();
    if (tk.t === 'num') return tk.v;
    if (tk.t === 'lparen') {
      const v = parseExpr();
      const close = next();
      if (close.t !== 'rparen') throw new Error('expected ")"');
      return v;
    }
    if (tk.t === 'id') {
      // function call?
      if (peek()?.t === 'lparen') {
        const fn = FUNCTIONS[tk.v];
        if (!fn) throw new Error(`unknown function "${tk.v}"`);
        next(); // consume '('
        const args: number[] = [];
        if (peek()?.t !== 'rparen') {
          args.push(parseExpr());
          while (peek()?.t === 'comma') { next(); args.push(parseExpr()); }
        }
        const close = next();
        if (close.t !== 'rparen') throw new Error('expected ")"');
        return fn(...args);
      }
      if (tk.v in CONSTANTS) return CONSTANTS[tk.v];
      if (tk.v in vars && Number.isFinite(vars[tk.v])) return vars[tk.v];
      throw new Error(`unknown variable "${tk.v}"`);
    }
    throw new Error('unexpected token');
  }

  const result = parseExpr();
  if (pos !== tokens.length) throw new Error('unexpected trailing tokens');
  if (!Number.isFinite(result)) throw new Error('expression did not evaluate to a finite number');
  return result;
}

/** The variable names a sizing formula may reference (for docs + agent prompts). */
export const SIZING_FORMULA_VARS = [
  'duty', 'work', 'flow_mol', 'flow_vol', 'density_l', 'density_v', 'T', 'P',
] as const;
