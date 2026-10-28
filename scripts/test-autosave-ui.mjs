/** Real React regressions for delayed saves, refreshes, rejection and photo reuse. */
import assert from "node:assert/strict";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { build } from "esbuild";
import { JSDOM } from "jsdom";
const dom = new JSDOM('<div id="root"></div>', { url: "http://localhost" });
for (const key of [
  "window",
  "document",
  "HTMLElement",
  "HTMLInputElement",
  "Event",
  "MouseEvent",
  "KeyboardEvent",
  "Node",
  "localStorage",
])
  globalThis[key] = dom.window[key];
Object.defineProperty(globalThis, "navigator", {
  value: dom.window.navigator,
  configurable: true,
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const dir = await mkdtemp(resolve(".local/autosave-ui-"));
try {
  const bundle = await build({
    stdin: {
      contents: `export {default as Estimates} from './apps/frontend/src/pages/Estimates'; export {MemoryRouter} from 'react-router-dom'; export {default as Autosave} from './apps/frontend/src/components/AutosaveNumber'; export {default as Photo} from './apps/frontend/src/components/ProtectedImage'; export {LanguageProvider} from './apps/frontend/src/lib/i18n'; export {QueryClient, QueryClientProvider} from '@tanstack/react-query'; export {act,createElement} from 'react'; export {createRoot} from 'react-dom/client';`,
      resolveDir: process.cwd(),
      loader: "tsx",
    },
    bundle: true,
    packages: "external",
    platform: "node",
    format: "esm",
    jsx: "automatic",
    write: false,
    define: { "import.meta.env.VITE_API_ORIGIN": '""' },
  });
  await writeFile(resolve(dir, "app.mjs"), bundle.outputFiles[0].contents);
  const {
    Autosave,
    Estimates,
    MemoryRouter,
    Photo,
    LanguageProvider,
    QueryClient,
    QueryClientProvider,
    act,
    createElement: h,
    createRoot,
  } = await import(pathToFileURL(resolve(dir, "app.mjs")));
  const root = createRoot(document.getElementById("root"));
  let saved = [],
    pending = [],
    resolveSave,
    initial = 1;
  const save = async (value) => {
    saved.push(value);
    return new Promise((r) => {
      resolveSave = r;
    });
  };
  const render = () =>
    root.render(
      h(Autosave, {
        initialValue: initial,
        onSave: save,
        onPendingChange: (p) => pending.push(p),
        type: "number",
        min: 0,
        step: ".01",
      }),
    );
  await act(async () => render());
  const input = () => document.querySelector("input");
  const type = async (value) =>
    act(async () => {
      Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      ).set.call(input(), String(value));
      input().dispatchEvent(new Event("input", { bubbles: true }));
    });
  const enter = async () =>
    act(async () =>
      input().dispatchEvent(
        new KeyboardEvent("keydown", { bubbles: true, key: "Enter" }),
      ),
    );
  await type(2);
  await enter();
  assert.deepEqual(saved, [2]);
  assert.equal(pending.at(-1), true);
  // Type and blur/Enter again before the first request resolves.
  await type(3);
  await enter();
  assert.deepEqual(saved, [2]);
  initial = 2;
  await act(async () => render());
  assert.equal(input().value, "3", "refresh must not discard a newer draft");
  await act(async () => resolveSave(true));
  assert.deepEqual(
    saved,
    [2, 3],
    "latest input must be drained after in-flight save",
  );
  await act(async () => resolveSave(true));
  assert.equal(pending.at(-1), false);
  // A clean control must follow another employee's refresh without remounting.
  initial = 9;
  await act(async () => render());
  assert.equal(input().value, "9");
  await type(10);
  await enter();
  await act(async () => resolveSave(false));
  assert.equal(input().value, "10");
  assert.equal(input().getAttribute("aria-invalid"), "true");
  assert.equal(pending.at(-1), true);
  await new Promise((r) => setTimeout(r, 30));
  assert.deepEqual(saved, [2, 3, 10], "rejected writes must not loop");
  await enter();
  await act(async () => resolveSave(true));
  assert.equal(pending.at(-1), false);
  await act(async () => root.unmount());
  let fetches = 0;
  globalThis.fetch = async () => {
    fetches++;
    return new Response(new Blob(["original-photo"], { type: "image/png" }));
  };
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const photoRoot = createRoot(document.getElementById("root"));
  const photos = (count) =>
    photoRoot.render(
      h(
        QueryClientProvider,
        { client },
        h(
          LanguageProvider,
          null,
          Array.from({ length: count }, (_, i) =>
            h(Photo, { key: i, imageId: "same-photo", alt: "Photo" }),
          ),
        ),
      ),
    );
  await act(async () => photos(1));
  await act(async () => new Promise((r) => setTimeout(r, 20)));
  await act(async () => photos(2));
  await act(async () => new Promise((r) => setTimeout(r, 20)));
  assert.equal(
    fetches,
    1,
    "opening the full-size photo must reuse the original",
  );
  assert.equal(document.querySelectorAll("img").length, 2);
  await act(async () => photoRoot.unmount());
  client.clear();
  const projects = Array.from({ length: 121 }, (_, i) => ({
    id: `project-${i}`,
    title: `Residence ${i}`,
    type: "pre",
    client_name: "Client",
    status: "draft",
    created_by: "Employee",
    updated_at: "2026-10-28T12:00:00Z",
    final_total: 100,
  }));
  globalThis.fetch = async () => new Response(JSON.stringify(projects));
  const registerClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const registerRoot = createRoot(document.getElementById("root"));
  await act(async () =>
    registerRoot.render(
      h(
        QueryClientProvider,
        { client: registerClient },
        h(LanguageProvider, null, h(MemoryRouter, null, h(Estimates))),
      ),
    ),
  );
  await act(async () => new Promise((r) => setTimeout(r, 30)));
  assert.equal(
    document.querySelectorAll(".estimate-row").length,
    50,
    "large registers render only one page",
  );
  const next = () =>
    [...document.querySelectorAll("button")].find(
      (b) => b.textContent === "Next page",
    );
  await act(async () => next().click());
  assert.equal(document.querySelectorAll(".estimate-row").length, 50);
  await act(async () => next().click());
  assert.equal(document.querySelectorAll(".estimate-row").length, 21);
  assert.equal(next().disabled, true);
  await act(async () => registerRoot.unmount());
  registerClient.clear();
  console.log(
    "Autosave/photo UI passed: delayed edits, draft preservation, clean remote refresh, rejected write/retry and one fetch for thumbnail + viewer, and 121-project pagination.",
  );
} finally {
  await rm(dir, { recursive: true, force: true });
  dom.window.close();
}
