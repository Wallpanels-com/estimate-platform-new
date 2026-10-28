/** Isolate formatter cost; this is not a browser page-load benchmark. */
import { performance } from "node:perf_hooks";
import { writeFile, mkdir } from "node:fs/promises";
const options = {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
};
const baseline = (value) =>
  new Intl.NumberFormat("en-US", options).format(value);
const formatter = new Intl.NumberFormat("en-US", options);
const optimized = (value) => formatter.format(value);
const results = {
  operation: "10,000 USD display formats; 5 runs; Node, same machine",
  before: [],
  after: [],
};
for (const [key, fn] of [
  ["before", baseline],
  ["after", optimized],
]) {
  for (let run = 0; run < 5; run++) {
    const start = performance.now();
    for (let i = 0; i < 10000; i++) fn(i + 0.25);
    results[key].push(Number((performance.now() - start).toFixed(2)));
  }
}
results.before_median_ms = [...results.before].sort((a, b) => a - b)[2];
results.after_median_ms = [...results.after].sort((a, b) => a - b)[2];
await mkdir(".local/audit", { recursive: true });
await writeFile(
  ".local/audit/formatting.json",
  JSON.stringify(results, null, 2),
);
console.log(JSON.stringify(results, null, 2));
