/** Verify the toolbar is never imported or mounted for another account. */
import assert from "node:assert/strict";
import { build } from "esbuild";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { JSDOM } from "jsdom";
const dom = new JSDOM('<div id="root"></div>', {
  url: "http://localhost:5190",
});
for (const key of [
  "window",
  "document",
  "HTMLElement",
  "Node",
  "MutationObserver",
])
  globalThis[key] = dom.window[key];
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.feedbackAuth = { token: null };
globalThis.feedbackLoads = 0;
const dir = await mkdtemp(resolve(".local/agentation-test-"));
try {
  const compiled = await build({
    stdin: {
      contents: `export {default as StaffFeedback} from './apps/frontend/src/components/StaffFeedback'; export {createElement,act} from 'react'; export {createRoot} from 'react-dom/client';`,
      resolveDir: process.cwd(),
      loader: "tsx",
    },
    bundle: true,
    platform: "node",
    packages: "external",
    format: "esm",
    jsx: "automatic",
    write: false,
    plugins: [
      {
        name: "auth-fixture",
        setup(b) {
          b.onResolve({ filter: /^react-router-dom$/ }, () => ({
            path: "router",
            namespace: "router-fixture",
          }));
          b.onLoad({ filter: /.*/, namespace: "router-fixture" }, () => ({
            contents:
              "export const useLocation=()=>({pathname:globalThis.feedbackPath || '/'})",
            loader: "js",
          }));
          b.onResolve({ filter: /^react(?:-dom)?$/ }, (args) => ({
            path: args.path,
            external: true,
          }));
          b.onLoad({ filter: /lib\/auth\.tsx$/ }, () => ({
            contents: "export const useAuth=()=>globalThis.feedbackAuth",
            loader: "tsx",
          }));
          b.onResolve({ filter: /^agentation$/ }, () => ({
            path: "agentation",
            namespace: "fixture",
          }));
          b.onLoad({ filter: /.*/, namespace: "fixture" }, () => ({
            contents: `import {createElement} from 'react'; import {createPortal} from 'react-dom'; globalThis.feedbackLoads++; export function Agentation({portalContainer}){return createPortal(createElement('button',{'data-toolbar':true},'Agentation'),portalContainer || document.body)}`,
            loader: "jsx",
          }));
        },
      },
    ],
  });
  await writeFile(resolve(dir, "app.mjs"), compiled.outputFiles[0].contents);
  const {
    StaffFeedback,
    createElement: h,
    act,
    createRoot,
  } = await import(pathToFileURL(resolve(dir, "app.mjs")));
  const root = createRoot(document.getElementById("root"));
  async function render(auth) {
    globalThis.feedbackAuth = auth;
    await act(async () => {
      root.render(h(StaffFeedback));
      await new Promise((r) => setTimeout(r, 20));
    });
  }
  const user = { id: "other", is_active: true, agentation_enabled: false };
  await render({ token: "team", user });
  assert.equal(globalThis.feedbackLoads, 0);
  assert.equal(document.querySelector("[data-toolbar]"), null);
  await render({
    token: "owner",
    loading: true,
    user: { ...user, agentation_enabled: true },
  });
  assert.equal(globalThis.feedbackLoads, 0);
  await render({
    token: "owner",
    user: { ...user, id: "owner", agentation_enabled: true },
  });
  assert.ok(document.querySelector("[data-toolbar]"));
  assert.equal(globalThis.feedbackLoads, 1);
  const modal = document.createElement("dialog");
  const nested = document.createElement("dialog");
  async function mutate(change) {
    await act(async () => {
      change();
      await new Promise((r) => setTimeout(r, 0));
    });
  }
  await mutate(() => {
    document.body.append(modal);
    modal.open = true;
  });
  assert.equal(
    document.querySelector("[data-toolbar]").closest("dialog"),
    modal,
  );
  await mutate(() => {
    document.body.append(nested);
    nested.open = true;
  });
  assert.equal(
    document.querySelector("[data-toolbar]").closest("dialog"),
    nested,
  );
  await mutate(() => {
    nested.open = false;
  });
  assert.equal(
    document.querySelector("[data-toolbar]").closest("dialog"),
    modal,
  );
  await mutate(() => {
    modal.remove();
    nested.remove();
  });
  assert.equal(
    document.querySelector("[data-toolbar]").parentElement,
    document.body,
  );

  await render({ token: "team", user });
  assert.equal(document.querySelector("[data-toolbar]"), null);
  await render({ token: null });
  assert.equal(document.querySelector("[data-toolbar]"), null);
  await act(async () => root.unmount());
  console.log(
    "Agentation isolation passed: only enabled owner mounts/loads toolbar; loading, other users and logout hide it; toolbar follows open/nested/closed dialogs.",
  );
} finally {
  await rm(dir, { recursive: true, force: true });
  dom.window.close();
}
