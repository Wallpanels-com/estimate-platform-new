/** Synthetic HR UI: no site, credentials or candidate files are accessed. */
import assert from "node:assert/strict";
import { build } from "esbuild";
import { JSDOM } from "jsdom";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
const dom = new JSDOM('<div id="root"></div>', {
  url: "http://localhost:5190",
});
for (const key of [
  "window",
  "document",
  "HTMLElement",
  "HTMLInputElement",
  "HTMLDialogElement",
  "Event",
  "MouseEvent",
  "Node",
  "FormData",
  "localStorage",
])
  globalThis[key] = dom.window[key];
Object.defineProperty(globalThis, "navigator", {
  value: dom.window.navigator,
  configurable: true,
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
HTMLDialogElement.prototype.close = function () {
  this.open = false;
};
const dir = await mkdtemp(resolve(".local/hr-actions-ui-"));
try {
  const out = await build({
    stdin: {
      contents: `export{default as HR}from'./apps/frontend/src/pages/HR';export{LanguageProvider}from'./apps/frontend/src/lib/i18n';export{NoticeProvider}from'./apps/frontend/src/components/ui';export{QueryClient,QueryClientProvider}from'@tanstack/react-query';export{createElement,act}from'react';export{createRoot}from'react-dom/client';`,
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
  await writeFile(resolve(dir, "app.mjs"), out.outputFiles[0].contents);
  const {
    HR,
    LanguageProvider,
    NoticeProvider,
    QueryClient,
    QueryClientProvider,
    createElement: h,
    act,
    createRoot,
  } = await import(pathToFileURL(resolve(dir, "app.mjs")));
  for (const language of ["en", "ru"]) {
    localStorage.setItem("wallpanels.ui-language", language);
    let row = {
      id: "synthetic",
      name: "Example Candidate",
      email: "example@example.com",
      phone: "+380000000000",
      answers: {},
      source: "Synthetic",
      status: "interview",
      priority: false,
      hidden: false,
      notes: "Existing note",
      location: "",
      location_verified: false,
      version: 1,
      updated_by: "Preview",
      updated_at: new Date().toISOString(),
      contact_flags: [],
      score: null,
      evidence: [],
    };
    const writes = [];
    let fail = false;
    globalThis.fetch = async (path, options = {}) => {
      const url = new URL(path, "http://localhost");
      let result;
      if (url.pathname.endsWith("/vacancies"))
        result = [{ id: "vacancy", name: "Example vacancy", count: 1 }];
      else if (url.pathname.endsWith("/candidates")) {
        const visible =
          row.hidden === (url.searchParams.get("hidden") === "true");
        result = {
          items: visible ? [row] : [],
          total: visible ? 1 : 0,
          page: 1,
          counts: {},
        };
      } else if (url.pathname.endsWith("/history")) result = [];
      else if (url.pathname.endsWith("/quick")) {
        const body = JSON.parse(options.body);
        writes.push(body);
        if (fail)
          return new Response(JSON.stringify({ detail: "Concurrent edit" }), {
            status: 409,
          });
        assert.equal(body.version, row.version);
        row = { ...row, ...body, version: row.version + 1 };
        result = row;
      } else throw new Error(`Unexpected request ${path}`);
      return new Response(JSON.stringify(result), {
        headers: { "Content-Type": "application/json" },
      });
    };
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    const root = createRoot(document.getElementById("root"));
    const settle = async () => {
      for (let i = 0; i < 5; i++)
        await act(async () => new Promise((r) => setTimeout(r, 10)));
    };
    const button = (label) =>
      [...document.querySelectorAll("button")].find(
        (b) =>
          b.getAttribute("aria-label") === label ||
          b.textContent.trim() === label,
      );
    const click = async (label) => {
      assert.ok(button(label), label);
      await act(async () => button(label).click());
      await settle();
    };
    await act(async () =>
      root.render(
        h(
          LanguageProvider,
          null,
          h(QueryClientProvider, { client }, h(NoticeProvider, null, h(HR))),
        ),
      ),
    );
    await settle();
    const labels =
      language === "ru"
        ? [
            "В приоритет",
            "Убрать приоритет",
            "Заметка о кандидате",
            "Скрыть кандидата",
            "Скрытые",
            "Вернуть кандидата",
            "Кандидаты",
          ]
        : [
            "Prioritize candidate",
            "Remove candidate priority",
            "Candidate note",
            "Hide candidate",
            "Hidden candidates",
            "Restore candidate",
            "Visible candidates",
          ];
    assert.equal(document.querySelectorAll(".hr-row-actions button").length, 3);
    assert.ok(
      [...document.querySelectorAll(".hr-row-actions button")].every(
        (b) => !b.hasAttribute("title"),
      ),
    );
    await click(labels[0]);
    assert.ok(row.priority);
    assert.deepEqual(Object.keys(writes[0]).sort(), ["priority", "version"]);
    await click(labels[2]);
    assert.equal(
      document.querySelector("textarea[name=notes]").value,
      "Existing note",
    );
    assert.equal(
      document.activeElement,
      document.querySelector("textarea[name=notes]"),
    );
    await click(language === "ru" ? "Отмена" : "Cancel");
    fail = true;
    await click(labels[3]);
    assert.equal(row.hidden, false);
    assert.ok(document.querySelector(".hr-name"));
    fail = false;
    await click(labels[3]);
    assert.equal(row.hidden, true);
    assert.ok(!document.querySelector(".hr-name"));
    assert.equal(row.status, "interview");
    assert.equal(row.notes, "Existing note");
    await click(labels[4]);
    assert.ok(document.querySelector(".hr-name"));
    await click(labels[5]);
    assert.equal(row.hidden, false);
    assert.ok(row.priority);
    assert.equal(row.status, "interview");
    await click(labels[6]);
    assert.ok(document.querySelector(".hr-name"));
    await click(labels[1]);
    assert.equal(row.priority, false);
    await act(async () => root.unmount());
    client.clear();
    document.getElementById("root").innerHTML = "";
  }
  console.log(
    "HR actions UI passed: EN/RU star, note focus, hide/restore, no tooltips, conflict recovery and preserved stage/notes.",
  );
} finally {
  await rm(dir, { recursive: true, force: true });
}
