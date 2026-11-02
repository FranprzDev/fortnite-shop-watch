import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const PELE_PATH = join(dirname(fileURLToPath(import.meta.url)), "vendor", "pele", "pele.global.js");

function fail(message) {
  process.stderr.write(`render_chart: ${message}\n`);
  process.exit(1);
}

function loadPele() {
  let source;
  try {
    source = readFileSync(PELE_PATH, "utf8");
  } catch (error) {
    fail(`cannot read ${PELE_PATH}: ${error.message}`);
  }
  eval(`${source}\n;globalThis.__pele=pele;`);
  if (!globalThis.__pele || typeof globalThis.__pele.render !== "function") {
    fail("vendored pele did not expose render()");
  }
  return globalThis.__pele;
}

const FALLBACK_PATTERN = /var\((--[A-Za-z0-9_-]+),([^()]*)\)/g;
const REFERENCE_PATTERN = /var\((--[A-Za-z0-9_-]+)\)/g;

function collectDefinitions(svg) {
  const definitions = new Map();
  for (const match of svg.matchAll(/--([A-Za-z0-9_-]+)\s*:\s*([^;"]+)/g)) {
    const value = match[2].trim();
    definitions.set(`--${match[1]}`, value);
  }
  return definitions;
}

function resolveValue(value, definitions) {
  let current = value.trim();
  for (let depth = 0; depth < 8; depth += 1) {
    const fallback = current.match(/^var\((--[A-Za-z0-9_-]+)(?:,([^()]*))?\)$/);
    if (!fallback) {
      break;
    }
    const defined = definitions.get(fallback[1]);
    if (defined !== undefined) {
      current = defined;
    } else if (fallback[2]) {
      current = fallback[2].trim();
    } else {
      break;
    }
  }
  return current;
}

function replaceCssVars(svg) {
  const definitions = collectDefinitions(svg);
  const withFallbacks = svg.replace(FALLBACK_PATTERN, (_, name, fallback) => fallback.trim());
  return withFallbacks.replace(REFERENCE_PATTERN, (whole, name) => resolveValue(whole, definitions));
}

function main(argv) {
  if (argv.length !== 3) {
    fail("usage: node tools/render_chart.js <source.mmd> <output.svg>");
  }
  const [, sourcePath, outputPath] = argv;
  let source;
  try {
    source = readFileSync(sourcePath, "utf8");
  } catch (error) {
    fail(`cannot read ${sourcePath}: ${error.message}`);
  }
  const pele = loadPele();
  let rendered;
  try {
    rendered = pele.render(source);
  } catch (error) {
    fail(`pele.render failed for ${sourcePath}: ${error.message}`);
  }
  if (!rendered || typeof rendered.svg !== "string") {
    fail(`pele.render returned no svg for ${sourcePath}`);
  }
  const svg = replaceCssVars(rendered.svg);
  try {
    writeFileSync(outputPath, svg, "utf8");
  } catch (error) {
    fail(`cannot write ${outputPath}: ${error.message}`);
  }
  process.stdout.write(`chart written: ${outputPath}\n`);
}

main(process.argv.slice(1));
