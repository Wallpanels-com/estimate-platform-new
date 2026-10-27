/** Exercise the real React item editor and picker in an isolated DOM; no browser or database writes. */
import assert from "node:assert/strict";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { build } from "esbuild";
import { JSDOM } from "jsdom";

const dom = new JSDOM(
  '<!doctype html><html><body><div id="root"></div></body></html>',
  { url: "http://localhost:5190" },
);
for (const name of [
  "window",
  "document",
  "HTMLElement",
  "HTMLInputElement",
  "HTMLDialogElement",
  "Event",
  "MouseEvent",
  "KeyboardEvent",
  "Node",
  "FormData",
  "localStorage",
])
  globalThis[name] = dom.window[name];
Object.defineProperty(globalThis, "navigator", {
  value: dom.window.navigator,
  configurable: true,
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const nativeMatches = HTMLElement.prototype.matches;
HTMLElement.prototype.matches = function (selector) {
  return selector === ":popover-open"
    ? this.dataset.open === "true"
    : nativeMatches.call(this, selector);
};
HTMLElement.prototype.showPopover = function () {
  this.dataset.open = "true";
  this.dispatchEvent(new Event("toggle"));
};
HTMLElement.prototype.hidePopover = function () {
  delete this.dataset.open;
  this.dispatchEvent(new Event("toggle"));
};
HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
HTMLDialogElement.prototype.close = function () {
  this.open = false;
};
const dir = await mkdtemp(resolve(".local/catalog-ui-"));
try {
  const compiled = await build({
    stdin: {
      contents: `export {default as CategoryForm} from './apps/frontend/src/components/pricebook/CategoryForm'; export {default as PriceBook} from './apps/frontend/src/pages/PriceBook'; export {default as AddItems} from './apps/frontend/src/components/AddItems'; export {LanguageProvider} from './apps/frontend/src/lib/i18n'; export {QueryClient,QueryClientProvider} from '@tanstack/react-query'; export {createElement,act} from 'react'; export {createRoot} from 'react-dom/client';`,
      resolveDir: process.cwd(),
      loader: "tsx",
    },
    bundle: true,
    platform: "node",
    packages: "external",
    format: "esm",
    jsx: "automatic",
    write: false,
    define: { "import.meta.env.VITE_API_ORIGIN": '""' },
  });
  await writeFile(resolve(dir, "app.mjs"), compiled.outputFiles[0].contents);
  const {
    AddItems,
    PriceBook,
    CategoryForm,
    LanguageProvider,
    QueryClient,
    QueryClientProvider,
    createElement: h,
    act,
    createRoot,
  } = await import(pathToFileURL(resolve(dir, "app.mjs")));
  const categories = ["wall", "cabinet", "mirror", "services"].map((id) => ({
    id,
    icon: "folder",
    builtin: true,
    parent_id: null,
    description: "",
    description_ru: "",
    name: id,
    name_ru: "",
    archived: false,
    version: 1,
  }));
  const existing = {
    id: "saved-item",
    name: "Acoustic finish",
    name_ru: "Акустическая отделка",
    category_id: "wall",
    kind: "work",
    pricing_mode: "unit",
    unit: "SF",
    unit_price: "25.50",
    default_quantity: "3",
    description: "",
    description_ru: "",
    parameters: [],
    archived: false,
    version: 1,
  };
  const archived = {
    ...existing,
    id: "archived",
    name: "Archived scope",
    archived: true,
  };
  const schema = {
    mirror: { rate: 80, minimum: 1000 },
    wall: { addons_sf: [], addons_fixed: [] },
    cabinet: { types: [], addons_lf: [], glass_doors: [] },
    materials: {},
    colors: [],
    services: {},
  };
  let categoryWrites = [],
    rateWrites = [];
  let config = { wall: { base_rate: 40 } };
  let book,
    creates,
    quotes,
    added,
    closed,
    failAdd,
    root,
    client,
    calculatorCalls;
  globalThis.fetch = async (url, options = {}) => {
    const path = String(url).replace("/api/v1", "");
    const payload = options.body ? JSON.parse(options.body) : null;
    let body;
    if (path === "/pricing/config") {
      if (payload) {
        rateWrites.push(payload);
        config = payload.config;
      }
      body = { config, revision: "test-revision", is_default: false };
    } else if (path.startsWith("/pricing/catalog/categories")) {
      categoryWrites.push(payload);
      const id = path.split("/")[4] || `category-${categoryWrites.length}`;
      const previous = book.categories.find((c) => c.id === id);
      body = {
        ...payload,
        id,
        version: (previous?.version || 0) + 1,
        builtin: false,
        calculator_id: null,
      };
      book = {
        ...book,
        categories: [...book.categories.filter((c) => c.id !== id), body],
      };
    } else if (path === "/pricing/schema") body = schema;
    else if (path === "/pricing/catalog" && !payload) body = book;
    else if (path === "/pricing/catalog/items") {
      creates.push(payload);
      const item = { ...payload, id: "new-item", version: 1 };
      book = { ...book, items: [...book.items, item] };
      body = item;
    } else if (path.endsWith("/quote")) {
      const item = book.items.find((i) => path.includes(`/${i.id}/`));
      assert.ok(item);
      quotes.push({ item, quantity: payload.quantity });
      const qty = item.pricing_mode === "fixed" ? "1" : payload.quantity;
      body = {
        section: item.category_id,
        name: item.name,
        description: item.description || "",
        calc_type: item.unit === "SF" ? "sf" : "fixed",
        quantity: qty,
        unit: item.unit,
        unit_price: item.unit_price,
        total_price:
          item.pricing_mode === "unpriced"
            ? "0.00"
            : (Number(item.unit_price) * Number(qty)).toFixed(2),
        is_tbd: item.pricing_mode === "unpriced",
      };
    } else if (path.startsWith("/pricing/calc/")) {
      calculatorCalls.push(path);
      body = { total: 2600, line_items: [] };
    } else throw Error(`Unexpected request: ${path}`);
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  async function mount(language = "en", initial = "calculator") {
    localStorage.setItem("wallpanels.ui-language", language);
    book = { categories, items: [existing, archived] };
    creates = [];
    quotes = [];
    added = [];
    closed = 0;
    failAdd = false;
    calculatorCalls = [];
    client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    root = createRoot(document.getElementById("root"));
    await act(async () => {
      root.render(
        h(
          LanguageProvider,
          null,
          h(
            QueryClientProvider,
            { client },
            h(AddItems, {
              zone: {
                id: "zone-1",
                zone_type: "mirror",
                line_items: [],
                square_footage: "20",
              },
              initial,
              onClose: () => closed++,
              onAdd: async (items) => {
                added.push(items);
                if (failAdd) {
                  failAdd = false;
                  throw Error("Temporary estimate save failure");
                }
              },
            }),
          ),
        ),
      );
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 20));
    });
  }
  async function cleanup() {
    await act(async () => root.unmount());
    client.clear();
  }
  const all = (selector) => [...document.querySelectorAll(selector)];
  const editor = () => all("dialog").at(-1);
  const button = (text, scope = document) =>
    [...scope.querySelectorAll("button")].find(
      (n) => n.textContent.trim() === text,
    );
  async function click(node) {
    assert.ok(node, "Button exists");
    await act(async () =>
      node.dispatchEvent(new MouseEvent("click", { bubbles: true })),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
  }
  async function input(node, value) {
    assert.ok(node);
    await act(async () => {
      Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      ).set.call(node, value);
      node.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }
  async function key(node, key) {
    await act(async () =>
      node.dispatchEvent(
        new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }),
      ),
    );
  }
  async function submit(confirm = true) {
    await act(async () =>
      editor()
        .querySelector("form")
        .dispatchEvent(
          new Event("submit", { bubbles: true, cancelable: true }),
        ),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    const confirmation =
      button("Confirm save", editor()) ||
      button("Подтвердить сохранение", editor());
    if (confirmation && confirm) await click(confirmation);
  }
  const picker = () => document.querySelector('input[role="combobox"]');

  // Search saved EN/RU names, exclude archived entries, and add the server quote.
  for (const lang of ["en", "ru"]) {
    await mount(lang);
    await input(picker(), lang === "ru" ? "Акустическая" : "Acoustic");
    const options = all('[role="option"]').filter(
      (n) => n.closest(".choice-menu")?.dataset.open === "true",
    );
    assert.equal(options.length, 2);
    assert.match(options[0].textContent, /Acoustic|Акустическая/);
    await key(picker(), "Enter");
    assert.equal(
      document.querySelector(".book-picker-selection input").value,
      "3",
    );
    await click(
      button(lang === "ru" ? "Добавить позицию в зону" : "Add item to zone"),
    );
    assert.equal(added[0][0].name, "Acoustic finish");
    assert.equal(added[0][0].total_price, "76.50");
    assert.equal(closed, 1);
    await cleanup();
  }

  // Keyboard creation prefills the editor. A failed zone save retries the persisted
  // item instead of issuing another Price Book POST; English export text is retained.
  await mount();
  await input(picker(), "Custom floating shelf");
  await key(picker(), "Enter");
  assert.equal(all("dialog").length, 2);
  assert.equal(
    editor().querySelector('[name="name"]').value,
    "Custom floating shelf",
  );
  await input(editor().querySelector('[name="name_ru"]'), "Полка на заказ");
  await input(editor().querySelector('[name="unit_price"]'), "45.50");
  await input(editor().querySelector('[name="default_quantity"]'), "2");
  await submit(false);
  assert.equal(
    creates.length,
    0,
    "Opening confirmation must not persist an item",
  );
  await click(button("Cancel", editor()));
  assert.equal(
    editor().querySelector('[name="unit_price"]').value,
    "45.50",
    "Cancel retains the draft",
  );
  assert.equal(creates.length, 0);
  failAdd = true;
  await submit();
  assert.equal(creates.length, 1);
  assert.equal(added.length, 1);
  assert.equal(closed, 0);
  assert.match(editor().textContent, /Item saved to Price Book/);
  assert.ok(editor().querySelector("fieldset").disabled);
  await submit();
  assert.equal(creates.length, 1);
  assert.equal(added.length, 2);
  assert.equal(closed, 1);
  assert.equal(added[1][0].total_price, "91.00");
  assert.equal(quotes[1].quantity, "2");
  assert.ok(
    client
      .getQueryData(["pricebook-catalog"])
      .items.some((i) => i.id === "new-item"),
  );
  await cleanup();

  // Fixed and unpriced entries use the same Price Book validation and quote path.
  for (const mode of ["fixed", "unpriced"]) {
    await mount();
    await click(document.querySelector(".search-select-create"));
    await input(editor().querySelector('[name="name"]'), `${mode} scope`);
    const select = [...editor().querySelectorAll("select")].find((n) =>
      [...n.options].some((o) => o.value === "unpriced"),
    );
    await act(async () => {
      select.value = mode;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    if (mode === "fixed")
      await input(editor().querySelector('[name="unit_price"]'), "150");
    await submit();
    assert.equal(creates.length, 1);
    assert.equal(creates[0].pricing_mode, mode);
    assert.equal(added[0][0].total_price, mode === "fixed" ? "150.00" : "0.00");
    assert.equal(added[0][0].is_tbd, mode === "unpriced");
    if (mode === "fixed") {
      assert.equal(quotes[0].quantity, "1");
      assert.equal(creates[0].unit, "Fixed");
    }
    await cleanup();
  }

  // Cancel leaves the entered calculator quantity intact and creates no record.
  await mount();
  const area = document.querySelector('[name="square_footage"]');
  await input(area, "32");
  await input(picker(), "Cancelled work");
  await click(document.querySelector(".search-select-create"));
  await click(button("Cancel", editor()));
  assert.equal(all("dialog").length, 1);
  assert.equal(area.value, "32");
  assert.equal(creates.length, 0);
  assert.equal(added.length, 0);
  // Choosing an existing calculator preserves its own endpoint and formula inputs.
  await input(picker(), "Mirror");
  await key(picker(), "Enter");
  await act(async () =>
    document
      .querySelector("form")
      .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })),
  );
  assert.deepEqual(calculatorCalls, ["/pricing/calc/mirror"]);
  await cleanup();

  // The Price Book tab also creates in the current zone, without navigating away.
  await mount("ru", "catalog");
  await input(
    document.querySelector('input[placeholder="Поиск по справочнику…"]') ||
      document.querySelector(".search-field input"),
    "Карниз",
  );
  await click(button("Добавить новую позицию"));
  assert.equal(editor().querySelector('[name="name"]').value, "Карниз");
  await cleanup();
  // Exercise the actual Price Book page, including confirmations before writes.
  for (const language of ["en", "ru"]) {
    localStorage.setItem("wallpanels.ui-language", language);
    book = { categories, items: [] };
    config = { wall: { base_rate: 40 } };
    rateWrites = [];
    categoryWrites = [];
    client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    root = createRoot(document.getElementById("root"));
    await act(async () =>
      root.render(
        h(
          LanguageProvider,
          null,
          h(QueryClientProvider, { client }, h(PriceBook)),
        ),
      ),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 20));
    });
    const ru = language === "ru";
    await input(
      document.querySelector('.book-rate-form input[type="number"]'),
      "41",
    );
    const saveRate = ru ? "Сохранить ставки" : "Save rates";
    const confirmSave = ru ? "Подтвердить сохранение" : "Confirm save";
    const cancel = ru ? "Отмена" : "Cancel";
    await click(button(saveRate));
    assert.equal(rateWrites.length, 0);
    await click(button(cancel, editor()));
    assert.equal(
      document.querySelector('.book-rate-form input[type="number"]').value,
      "41",
    );
    await click(button(saveRate));
    await click(button(confirmSave, editor()));
    assert.equal(rateWrites.length, 1);
    assert.equal(rateWrites[0].config.wall.base_rate, 41);
    assert.equal(rateWrites[0].expected_revision, "test-revision");
    await click(button(ru ? "Добавить категорию" : "Add category"));
    await input(editor().querySelector('[name="name"]'), "Custom finishes");
    await input(editor().querySelector('[name="name_ru"]'), "Отделка на заказ");
    const saveCategory = ru ? "Сохранить категорию" : "Save category";
    await click(button(saveCategory, editor()));
    assert.equal(categoryWrites.length, 0);
    await click(button(cancel, editor()));
    assert.equal(
      editor().querySelector('[name="name"]').value,
      "Custom finishes",
    );
    await click(button(saveCategory, editor()));
    await click(button(confirmSave, editor()));
    assert.equal(categoryWrites.length, 1);
    assert.equal(categoryWrites[0].parent_id, null);
    await click(button(ru ? "Добавить подкатегорию" : "Add subcategory"));
    assert.equal(
      editor().querySelector('[name="parent_id"]').value,
      "category-1",
    );
    await input(editor().querySelector('[name="name"]'), "Oak");
    await click(button(saveCategory, editor()));
    await click(button(confirmSave, editor()));
    assert.equal(categoryWrites[1].parent_id, "category-1");
    await click(
      document.querySelector(
        '.book-category-actions button[title="' +
          (ru ? "Изменить категорию" : "Edit category") +
          '"]',
      ),
    );
    await input(editor().querySelector('[name="name"]'), "Natural oak");
    await click(button(saveCategory, editor()));
    assert.equal(categoryWrites.length, 2);
    await click(button(confirmSave, editor()));
    assert.equal(categoryWrites[2].expected_version, 1);
    assert.equal(categoryWrites[2].parent_id, "category-1");
    const archiveCategory = () =>
      document.querySelector(
        '.book-category-actions button[title="' +
          (ru ? "Архивировать категорию" : "Archive category") +
          '"]',
      );
    await click(archiveCategory());
    await click(button(cancel, editor()));
    assert.equal(categoryWrites.length, 3);
    await click(archiveCategory());
    await click(
      button(ru ? "В архив" : "Archive", editor()) ||
        button(ru ? "Архивировать" : "Archive", editor()),
    );
    assert.equal(categoryWrites.at(-1).archived, true);
    assert.equal(categoryWrites.at(-1).expected_version, 2);
    await cleanup();
  }
  // Editing an archived child must keep its archived parent selected.
  const archivedParent = {
    ...categories[0],
    id: "archived-parent",
    name: "Archived parent",
    builtin: false,
    archived: true,
  };
  const archivedChild = {
    ...archivedParent,
    id: "archived-child",
    name: "Archived child",
    parent_id: archivedParent.id,
  };
  localStorage.setItem("wallpanels.ui-language", "en");
  root = createRoot(document.getElementById("root"));
  await act(async () =>
    root.render(
      h(
        LanguageProvider,
        null,
        h(CategoryForm, {
          category: archivedChild,
          categories: [...categories, archivedParent, archivedChild],
          onClose: () => {},
          onSaved: async () => {},
        }),
      ),
    ),
  );
  assert.equal(
    editor().querySelector('[name="parent_id"]').value,
    archivedParent.id,
  );
  await act(async () => root.unmount());
  console.log(
    "Catalogue UI tests passed: EN/RU search, keyboard selection/create, Price Book persistence callback, current-zone quote, retry without duplicate item, cancel, unchanged calculator routing, and EN/RU Price Book rate/category/subcategory/edit/archive confirmations.",
  );
} finally {
  await rm(dir, { recursive: true, force: true });
  dom.window.close();
}
