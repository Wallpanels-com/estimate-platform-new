/** Real page-access UI with isolated auth/transport; never connects to a site. */
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
const dir = await mkdtemp(resolve(".local/access-ui-"));
try {
  const bundle = await build({
    stdin: {
      contents: `export {default as Users} from './apps/frontend/src/pages/Users'; export {default as Shell} from './apps/frontend/src/components/Shell'; export {PageGate,NoPageAccess} from './apps/frontend/src/components/PageGate'; export {PAGES,canAccess,firstPage} from './apps/frontend/src/lib/access'; export {AuthProvider,useAuth} from './apps/frontend/src/lib/auth'; export {LanguageProvider} from './apps/frontend/src/lib/i18n'; export {QueryClient,QueryClientProvider} from '@tanstack/react-query'; export {MemoryRouter,Routes,Route} from 'react-router-dom'; export {createElement,act} from 'react'; export {createRoot} from 'react-dom/client';`,
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
    Users,
    Shell,
    PageGate,
    NoPageAccess,
    PAGES,
    canAccess,
    firstPage,
    AuthProvider,
    useAuth,
    LanguageProvider,
    QueryClient,
    QueryClientProvider,
    MemoryRouter,
    Routes,
    Route,
    createElement: h,
    act,
    createRoot,
  } = await import(pathToFileURL(resolve(dir, "app.mjs")));
  assert.equal(canAccess(undefined, "users"), false);
  assert.equal(canAccess({}, "users"), true);
  assert.equal(canAccess({}, "hr"), false);
  assert.equal(canAccess({page_access:["hr"]}, "hr"), true);
  assert.equal(canAccess({ page_access: [] }, "users"), false);
  assert.equal(firstPage({ page_access: [] }), "/access");
  assert.equal(firstPage({ page_access: ["users"] }), "/users");
  let profile,
    grants,
    puts = [],
    creates = [],
    fail = false;
  const employee = {
    id: "employee",
    email: "staff",
    name: "Employee",
    role: "user",
    is_active: true,
    page_access: null,
  };
  const buttons = (text) =>
    [...document.querySelectorAll("button")].filter(
      (b) => b.textContent.trim() === text,
    );
  globalThis.fetch = async (path, options = {}) => {
    let body;
    if (path.endsWith("/auth/me")) body = profile;
    else if (path.endsWith("/users/employee/access")) {
      if (options.method === "PUT") {
        puts.push(JSON.parse(options.body));
        if (fail)
          return new Response(
            JSON.stringify({
              detail:
                "This employee account changed. Reopen access settings and try again.",
            }),
            { status: 409 },
          );
        grants = { ...grants, pages: puts.at(-1).pages, updated_at: "v2" };
      }
      body = grants;
    } else if (path.endsWith("/users")) {
      if (options.method === "POST") { creates.push(JSON.parse(options.body)); body = {...employee, ...creates.at(-1)}; }
      else body = [employee];
    }
    else throw Error("Unexpected request " + path);
    return new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json" },
    });
  };
  async function mount(lang, owner, route = "/users") {
    localStorage.setItem("wallpanels.ui-language", lang);
    localStorage.setItem("wallpanels.token", "synthetic-test-token");
    profile = {
      ...employee,
      id: "me",
      can_manage_access: owner,
      page_access: owner ? PAGES.map((p) => p.key) : ["users", "estimates"],
    };
    grants = {
      pages: PAGES.map((p) => p.key),
      updated_at: "v1",
      protected_owner: false,
    };
    puts = [];
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    const root = createRoot(document.getElementById("root"));
    const routes = h(
      Routes,
      null,
      h(
        Route,
        { element: h(Shell) },
        h(Route, { path: "/", element: h("div", null, "Allowed home") }),
        h(Route, {
          path: "users",
          element: h(PageGate, { page: "users" }, h(Users)),
        }),
        h(Route, {
          path: "price-book",
          element: h(
            PageGate,
            { page: "price_book" },
            h("div", null, "Forbidden book"),
          ),
        }),
        h(Route, { path: "access", element: h(NoPageAccess) }),
      ),
    );
    function Ready() {
      const { loading } = useAuth();
      return loading ? null : routes;
    }
    const tree = h(
      LanguageProvider,
      null,
      h(
        QueryClientProvider,
        { client },
        h(
          AuthProvider,
          null,
          h(MemoryRouter, { initialEntries: [route] }, h(Ready)),
        ),
      ),
    );
    await act(async () => root.render(tree));
    for (let i = 0; i < 10 && !document.querySelector(".team-table"); i++)
      await act(async () => new Promise((r) => setTimeout(r, 10)));
    return { root, client };
  }
  for (const lang of ["en", "ru"]) {
    let { root, client } = await mount(lang, true);
    const toggle = () => document.querySelector('.nav-toggle');
    assert.equal(toggle().getAttribute('aria-expanded'), 'true');
    await act(async () => toggle().click());
    assert.ok(document.querySelector('.app-shell.nav-collapsed'));
    assert.equal(localStorage.getItem('wallpanels.nav-collapsed'), 'true');
    assert.equal(toggle().getAttribute('aria-expanded'), 'false');
    assert.ok([...document.querySelectorAll('#main-navigation a')].every(a => a.getAttribute('aria-label') && a.getAttribute('title')));
    // Route changes preserve collapsed state and icon links remain navigable.
    await act(async () => document.querySelector('nav a[href="/"]').click());
    assert.ok(document.querySelector('.app-shell.nav-collapsed'));
    await act(async () => document.querySelector('nav a[href="/users"]').click());
    await act(async () => root.unmount()); client.clear();
    ({root, client} = await mount(lang, true));
    assert.equal(toggle().getAttribute('aria-expanded'), 'false', 'Collapse survives remount');
    await act(async () => toggle().click());
    assert.equal(localStorage.getItem('wallpanels.nav-collapsed'), 'false');
    const access = lang === "ru" ? "Доступы" : "Access";
    assert.equal(buttons(access).length, 1);
    await act(async () => buttons(access)[0].click());
    for (let i = 0; i < 10 && !document.querySelector(".access-options"); i++)
      await act(async () => new Promise((r) => setTimeout(r, 10)));
    const boxes = [...document.querySelectorAll(".access-options input")];
    assert.equal(boxes.length, 6);
    assert.ok(boxes.every((b) => b.checked));
    await act(async () => boxes[2].click());
    assert.equal(boxes[2].checked, false);
    fail = true;
    await act(async () =>
      document
        .querySelector("dialog form")
        .dispatchEvent(
          new Event("submit", { bubbles: true, cancelable: true }),
        ),
    );
    assert.ok(document.querySelector("dialog"));
    assert.equal(
      document.querySelectorAll(".access-options input:checked").length,
      5,
    );
    fail = false;
    await act(async () =>
      document
        .querySelector("dialog form")
        .dispatchEvent(
          new Event("submit", { bubbles: true, cancelable: true }),
        ),
    );
    assert.equal(puts.length, 2);
    assert.ok(!puts.at(-1).pages.includes("price_book"));
    assert.equal(puts.at(-1).expected_updated_at, "v1");
    await act(async () => buttons(lang === "ru" ? "Добавить сотрудника" : "Add employee")[0].click());
    const creationBoxes = [...document.querySelectorAll(".access-create input[type=checkbox]")];
    assert.equal(creationBoxes.length, 6);
    assert.ok(creationBoxes.every(b => !b.checked));
    await act(async () => { creationBoxes[0].click(); creationBoxes[PAGES.findIndex(p => p.key === 'hr')].click(); });
    document.querySelector('input[name=name]').value = 'Example Employee';
    document.querySelector('input[name=email]').value = 'example.employee';
    document.querySelector('input[name=password]').value = 'SyntheticPassword123';
    await act(async () => document.querySelector('dialog form').dispatchEvent(new Event('submit', {bubbles:true,cancelable:true})));
    assert.deepEqual(creates.at(-1).page_access, ['estimates','hr']);

    await act(async () => root.unmount());
    client.clear();
    ({ root, client } = await mount(lang, false));
    assert.equal(buttons(access).length, 0);
    assert.equal(
      buttons(lang === "ru" ? "Сбросить пароль" : "Reset password").length,
      0,
    );
    assert.equal(document.querySelector('nav a[href="/price-book"]'), null);
    assert.ok(document.querySelector('nav a[href="/users"]'));
    await act(async () => root.unmount());
    client.clear();
    ({ root, client } = await mount(lang, false, "/price-book"));
    assert.ok(!document.body.textContent.includes("Forbidden book"));
    assert.ok(document.body.textContent.includes("Allowed home"));
    await act(async () => root.unmount());
    client.clear();
  }
  console.log(
    "Page access UI passed: EN/RU owner-only actions, six grants, save payload, conflict preservation, menu filtering and direct-link guards.",
  );
} finally {
  await rm(dir, { recursive: true, force: true });
  dom.window.close();
}
