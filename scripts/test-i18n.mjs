import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { build } from "esbuild";
import ts from "typescript";

const compiled = await build({
  entryPoints: ["apps/frontend/src/lib/locale.ts"],
  bundle: true,
  platform: "node",
  format: "esm",
  write: false,
});
const locale = await import(
  "data:text/javascript;base64," +
    Buffer.from(compiled.outputFiles[0].text).toString("base64")
);
const stored = new Map();
globalThis.localStorage = {
  getItem: (key) => stored.get(key) ?? null,
  setItem: (key, value) => stored.set(key, value),
};
assert.equal(locale.readLanguage(), "en");
locale.writeLanguage("ru");
assert.equal(locale.readLanguage(), "ru");
assert.equal(locale.translate("Grand total", "ru"), "Общая сумма");
assert.equal(locale.translate("Grand total", "en"), "Grand total");
assert.equal(
  locale.translate("Customer-defined title", "ru"),
  "Customer-defined title",
);
assert.equal(
  locale.translate("Actions for {0}", "ru", "Project $& {1}"),
  "Действия: Project $& {1}",
);
assert.equal(locale.countLabel(1, "items", "ru"), "1 позиция");
assert.equal(locale.countLabel(2, "items", "ru"), "2 позиции");
assert.equal(locale.countLabel(5, "items", "ru"), "5 позиций");
assert.equal(locale.countLabel(11, "estimates", "ru"), "11 смет");
assert.equal(locale.countLabel(21, "estimates", "ru"), "21 смета");
assert.equal(locale.countLabel(1, "line items", "en"), "1 line item");
assert.equal(locale.countLabel(2, "line items", "en"), "2 line items");
stored.set(locale.LANGUAGE_KEY, "de");
assert.equal(locale.readLanguage(), "en");
globalThis.localStorage = {
  getItem() {
    throw Error("storage blocked");
  },
  setItem() {
    throw Error("storage blocked");
  },
};
assert.equal(locale.readLanguage(), "en");
assert.doesNotThrow(() => locale.writeLanguage("ru"));

const root = "apps/frontend/src";
const dict = JSON.parse(readFileSync(`${root}/lib/ru.json`, "utf8"));
for (const [key, value] of Object.entries(dict)) {
  assert.deepEqual(
    [...key.matchAll(/\{\d+\}/g)].map((m) => m[0]).sort(),
    [...value.matchAll(/\{\d+\}/g)].map((m) => m[0]).sort(),
    `Placeholder mismatch: ${key}`,
  );
}
for (const dir of ["pages", "components"])
  for (const file of readdirSync(`${root}/${dir}`, { recursive: true }).filter(
    (f) => f.endsWith(".tsx"),
  )) {
    const source = ts.createSourceFile(
      file,
      readFileSync(`${root}/${dir}/${file}`, "utf8"),
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    );
    function visit(node) {
      if (
        ts.isCallExpression(node) &&
        ts.isIdentifier(node.expression) &&
        node.expression.text === "t" &&
        node.arguments[0] &&
        ts.isStringLiteral(node.arguments[0])
      ) {
        assert.ok(
          node.arguments[0].text in dict,
          `Missing translation in ${file}: ${node.arguments[0].text}`,
        );
      }
      // Data sent to the API must remain independent from display language.
      if (
        ts.isJsxAttribute(node) &&
        ["value", "defaultValue", "name"].includes(node.name.getText(source)) &&
        node.initializer
      ) {
        assert.ok(
          !/\bt\(/.test(node.initializer.getText(source)),
          `Translated data attribute in ${file}`,
        );
      }
      ts.forEachChild(node, visit);
    }
    visit(source);
  }
const lines = readFileSync(`${root}/components/LineItems.tsx`, "utf8");
assert.ok(
  lines.includes('(i.section || "General") === section'),
  "Default section grouping must use its stored English key",
);
const builder = readFileSync(`${root}/pages/Builder.tsx`, "utf8");
assert.ok(builder.includes('["estimate", t("Estimate"), List]'));
assert.ok(builder.includes('["zones", t("Zones & summary"), Layers]'));
console.log(
  "EN/RU tests passed: persistence/fallback, translations, plural forms, placeholders and unchanged API data keys.",
);
