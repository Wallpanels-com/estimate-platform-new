/** Exercise the real React item editor and picker in an isolated DOM; no browser or database writes. */
import assert from "node:assert/strict";
import { mkdtemp, writeFile, rm, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { build } from "esbuild";
import { JSDOM } from "jsdom";
import postcss from "postcss";

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
      contents: `export {default as ItemForm} from './apps/frontend/src/components/pricebook/ItemForm'; export {default as ItemNameFields} from './apps/frontend/src/components/pricebook/ItemNameFields'; export {default as Photos} from './apps/frontend/src/components/Photos'; export {default as CategoryForm} from './apps/frontend/src/components/pricebook/CategoryForm'; export {default as PriceBook} from './apps/frontend/src/pages/PriceBook'; export {default as AddItems} from './apps/frontend/src/components/AddItems'; export {LanguageProvider} from './apps/frontend/src/lib/i18n'; export {QueryClient,QueryClientProvider} from '@tanstack/react-query'; export {createElement,act} from 'react'; export {createRoot} from 'react-dom/client';`,
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
    ItemNameFields,
    ItemForm,
    PriceBook,
    CategoryForm,
    Photos,
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
    mirror: {
      rate: 80,
      minimum: 1000,
      types: [
        { key: "rustic", label: "Rustic Mirror", rate: 100 },
        { key: "bronze", label: "Bronze Mirror", rate: 100 },
        { key: "clear", label: "Clear Mirror", rate: 80 },
      ],
    },
    wall: { base_rates: [], addons_sf: [], addons_fixed: [] },
    cabinet: { types: [], addons_lf: [], glass_doors: [] },
    materials: {},
    colors: [],
    services: {},
  };
  let calculatorPayloads = [];
  let itemUpdates = [];
  let deletions = [];
  let categoryWrites = [],
    rateWrites = [];
  let config = {
    wall: {
      base_rates: { large: 40, medium: 45, small: 50 },
      addons_sf: {
        led: {
          label: "LED",
          price: 5,
          describable: true,
          label_ru: "Подсветка",
        },
      },
    },
  };
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
    if (path.startsWith("/media/"))
      return new Response(new Uint8Array([0]), {
        headers: { "Content-Type": "image/png" },
      });
    const payload = options.body ? JSON.parse(options.body) : null;
    if (options.method === "DELETE") {
      const id = path.split("/").at(-1).split("?")[0];
      deletions.push(id);
      book = {
        ...book,
        categories: book.categories.filter((c) => c.id !== id),
        items: book.items.filter((i) => i.id !== id && i.category_id !== id),
      };
      return new Response(null, { status: 204 });
    }
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
    } else if (path === "/pricing/schema")
      body = {
        ...schema,
        cabinet: {
          ...schema.cabinet,
          types: config.cabinet?.types
            ? Object.entries(config.cabinet.types).map(([key, value]) => ({
                key,
                label: value.label,
                label_ru: value.label_ru,
                rate: value.base_rate,
              }))
            : schema.cabinet.types,
        },
      };
    else if (path === "/pricing/catalog" && !payload) body = book;
    else if (path === "/pricing/catalog/items") {
      creates.push(payload);
      const item = { ...payload, id: "new-item", version: 1 };
      book = { ...book, items: [...book.items, item] };
      body = item;
    } else if (
      path.startsWith("/pricing/catalog/items/") &&
      options.method === "PUT"
    ) {
      itemUpdates.push(payload);
      body = { ...payload, id: "saved-item", version: 2 };
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
      calculatorPayloads.push(payload);
      body = { total: 2600, line_items: [] };
    } else throw Error(`Unexpected request: ${path}`);
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  async function mount(
    language = "en",
    initial = "calculator",
    zoneType = "mirror",
  ) {
    localStorage.setItem("wallpanels.ui-language", language);
    book = { categories, items: [existing, archived] };
    creates = [];
    quotes = [];
    added = [];
    closed = 0;
    failAdd = false;
    calculatorCalls = [];
    calculatorPayloads = [];
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
                zone_type: zoneType,
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

  // Focus/click stays open; dismissal is explicit rather than native auto light-dismiss.
  await mount();
  await act(async () => picker().focus());
  const focusedMenu = picker().closest(".choice").querySelector(".choice-menu");
  assert.equal(focusedMenu.getAttribute("popover"), "manual");
  await click(picker());
  assert.equal(focusedMenu.dataset.open, "true");
  await act(async () =>
    document.body.dispatchEvent(
      new MouseEvent("pointerdown", { bubbles: true }),
    ),
  );
  assert.notEqual(focusedMenu.dataset.open, "true");
  await cleanup();

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
  // Automatic names stay local, ignore stale responses and respect manual edits.
  let pendingOld;
  window.Translator = {
    create: async () => ({
      translate: async (text) => {
        if (text === "Old slow name")
          return new Promise((resolve) => {
            pendingOld = resolve;
          });
        return text === "Floating shelf" ? "Парящая полка" : "Новое название";
      },
    }),
  };
  let translatingName = false;
  root = createRoot(document.getElementById("root"));
  await act(async () =>
    root.render(
      h(
        LanguageProvider,
        null,
        h(
          "form",
          null,
          h(ItemNameFields, {
            initialName: "",
            initialRussian: "",
            onTranslating: (value) => {
              translatingName = value;
            },
          }),
        ),
      ),
    ),
  );
  const enName = () => document.querySelector('[name="name"]');
  const ruName = () => document.querySelector('[name="name_ru"]');
  const settleName = () =>
    act(async () => {
      await new Promise((r) => setTimeout(r, 500));
    });
  await input(enName(), "Floating shelf");
  assert.equal(translatingName, true);
  await settleName();
  assert.equal(ruName().value, "Парящая полка");
  await input(enName(), "Old slow name");
  await settleName();
  await input(enName(), "New fast name");
  await settleName();
  await act(async () => pendingOld("Устаревшее название"));
  assert.equal(ruName().value, "Новое название");
  await input(ruName(), "Ручное название");
  await input(enName(), "Other name");
  await settleName();
  assert.equal(ruName().value, "Ручное название");
  delete window.Translator;
  await input(ruName(), "");
  await settleName();
  assert.match(ruName().title, /Автоперевод недоступен/);
  assert.equal(ruName().placeholder, "Заполняется автоматически");
  assert.equal(document.querySelector("small"), null);
  assert.equal(translatingName, false);
  await act(async () => root.unmount());

  // Removing description controls must never erase existing bilingual content.
  localStorage.setItem("wallpanels.ui-language", "en");
  const describedItem = {
    ...existing,
    description: "Keep original English details",
    description_ru: "Сохранить русские детали",
    parameters: [{ name: "Finish", value: "Oak" }],
  };
  root = createRoot(document.getElementById("root"));
  await act(async () =>
    root.render(
      h(
        LanguageProvider,
        null,
        h(ItemForm, {
          item: describedItem,
          categoryId: "wall",
          categories,
          onClose: () => {},
          onSaved: async () => {},
        }),
      ),
    ),
  );
  assert.equal(editor().querySelector('[name="description"]'), null);
  assert.equal(editor().querySelector('[name="description_ru"]'), null);
  assert.equal(editor().querySelector(".book-specifications"), null);
  assert.equal(editor().querySelector(".form-hint"), null);
  await submit();
  assert.equal(itemUpdates.at(-1).description, describedItem.description);
  assert.equal(itemUpdates.at(-1).description_ru, describedItem.description_ru);
  assert.deepEqual(itemUpdates.at(-1).parameters, describedItem.parameters);
  await act(async () => root.unmount());

  // Exercise the actual Price Book page, including confirmations before writes.
  for (const language of ["en", "ru"]) {
    localStorage.setItem("wallpanels.ui-language", language);
    book = { categories, items: [] };
    config = {
      wall: {
        base_rates: { large: 40, medium: 45, small: 50 },
        addons_sf: {
          led: {
            label: "LED",
            price: 5,
            describable: true,
            label_ru: "Подсветка",
          },
        },
      },
    };
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
    assert.equal(
      button(ru ? "Восстановить базовые цены" : "Restore defaults"),
      undefined,
    );
    assert.equal(document.querySelector(".page-header p"), null);
    assert.equal(document.querySelector(".book-view-tabs"), null);
    assert.equal(document.querySelector(".rate-parameters"), null);

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
    assert.equal(rateWrites[0].config.wall.base_rates.large, 41);
    assert.equal(rateWrites[0].expected_revision, "test-revision");
    assert.deepEqual(
      rateWrites[0].config.wall.addons_sf.led,
      { label: "LED", price: 5, describable: true, label_ru: "Подсветка" },
      "Hiding rate parameters must preserve their saved values",
    );

    assert.equal(
      button(ru ? "Добавить подкатегорию" : "Add subcategory"),
      undefined,
    );
    await click(document.querySelector(".rate-add"));
    await input(editor().querySelector('[name="label"]'), "Selected wall rate");
    await input(editor().querySelector('[name="amount"]'), "73");
    await click(button(ru ? "Добавить в черновик" : "Add to draft", editor()));
    assert.equal(rateWrites.length, 1);
    await click(button(saveRate));
    await click(button(confirmSave, editor()));
    assert.ok(Object.values(rateWrites[1].config.wall.base_rates).includes(73));
    assert.ok(
      Object.values(rateWrites[1].config._rate_labels).some(
        (v) => v.label === "Selected wall rate",
      ),
    );
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
    await click(
      document.querySelector(
        '.book-category-actions button[title="' +
          (ru ? "Изменить категорию" : "Edit category") +
          '"]',
      ),
    );
    assert.equal(editor().querySelector('[name="parent_id"]'), null);
    await input(editor().querySelector('[name="name"]'), "Natural oak");
    await click(button(saveCategory, editor()));
    assert.equal(categoryWrites.length, 1);
    await click(button(confirmSave, editor()));
    assert.equal(categoryWrites[1].expected_version, 1);
    assert.equal(categoryWrites[1].parent_id, null);
    const archiveCategory = () =>
      document.querySelector(
        '.book-category-actions button[title="' +
          (ru ? "Архивировать категорию" : "Archive category") +
          '"]',
      );
    await click(archiveCategory());
    await click(button(cancel, editor()));
    assert.equal(categoryWrites.length, 2);
    await click(archiveCategory());
    await click(
      button(ru ? "В архив" : "Archive", editor()) ||
        button(ru ? "Архивировать" : "Archive", editor()),
    );
    assert.equal(categoryWrites.at(-1).archived, true);
    assert.equal(categoryWrites.at(-1).expected_version, 2);
    const toggle = document.querySelector(".book-archive-toggle input");
    await click(toggle);
    await click(button(ru ? "Отделка на заказ" : "Natural oak"));
    const deleteText = ru ? "Удалить безвозвратно" : "Delete permanently";
    deletions = [];
    await click(button(deleteText));
    await click(button(cancel, editor()));
    assert.equal(deletions.length, 0);
    await click(button(deleteText));
    await click(button(deleteText, editor()));
    assert.equal(deletions.length, 1);
    await cleanup();
  }
  await mount("en", "calculator", "wall");
  await input(picker(), "Mirror");
  await key(picker(), "Enter");
  const mirrorType = editor().querySelector('select[name="mirror_type"]');
  assert.equal(
    mirrorType.value,
    "clear",
    "Switching from wall must reset the mirror selector to Clear",
  );
  await act(async () => {
    mirrorType.value = "rustic";
    mirrorType.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await input(editor().querySelector('[name="square_footage"]'), "10");
  await submit();
  assert.equal(calculatorPayloads[0].mirror_type, "rustic");
  assert.equal(calculatorPayloads[0].square_footage, 10);
  await cleanup();
  // Create a supported LF cabinet type, persist shared rates, and select it immediately.
  config = {
    ...config,
    cabinet: { types: { tv_stand: { label: "TV stand", base_rate: 700 } } },
  };
  rateWrites = [];
  await mount("en", "calculator", "cabinet");
  await click(document.querySelector('[aria-label="Add cabinet type"]'));
  await input(editor().querySelector('[name="name"]'), "Display cabinet");
  await input(editor().querySelector('[name="name_ru"]'), "Витрина");
  await input(editor().querySelector('[name="rate"]'), "925");
  await submit(false);
  assert.equal(rateWrites.length, 0);
  await click(button("Confirm save", editor()));
  const cabinetKey = Object.keys(config.cabinet.types).find((key) =>
    key.startsWith("custom_"),
  );
  assert.ok(cabinetKey);
  assert.equal(config.cabinet.types[cabinetKey].base_rate, 925);
  assert.equal(config.cabinet.types.tv_stand.base_rate, 700);
  assert.equal(rateWrites[0].expected_revision, "test-revision");
  assert.equal(
    editor().querySelector('[name="cabinet_type"]').value,
    cabinetKey,
  );
  await input(editor().querySelector('[name="linear_footage"]'), "4");
  await submit();
  assert.equal(calculatorPayloads[0].cabinet_type, cabinetKey);
  assert.equal(calculatorPayloads[0].linear_footage, 4);
  await cleanup();
  localStorage.setItem("wallpanels.ui-language", "en");
  // Regression: hidden upload fields must not create a layout box below a
  // scroll rail. The visible Add/Replace actions must still open the chooser.
  const sheet = postcss.parse(
    await readFile("apps/frontend/src/styles.css", "utf8"),
  );
  const uploadStyle = document.createElement("style");
  sheet.walkRules((rule) => {
    if (
      rule.selector === ".file-input" ||
      rule.selector.replace(/\s/g, "") === "input,select,textarea"
    )
      uploadStyle.textContent += rule.toString();
  });
  document.head.append(uploadStyle);
  for (const count of [0, 4]) {
    const uploads = [];
    root = createRoot(document.getElementById("root"));
    await act(async () =>
      root.render(
        h(
          LanguageProvider,
          null,
          h(Photos, {
            zone: {
              id: "photo-scroll-zone",
              images: Array.from({ length: count }, (_, i) => ({
                slot: i + 1,
                id: `photo-${i + 1}`,
              })),
            },
            busy: false,
            finalMode: true,
            onUpload: (slot, file) => uploads.push({ slot, file }),
            onDelete: () => {},
          }),
        ),
      ),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    const fileInput = document.querySelector('input[type="file"]');
    assert.equal(
      dom.window.getComputedStyle(fileInput).display,
      "none",
      "Upload field must be excluded from scroll geometry",
    );
    let chooserOpened = 0;
    fileInput.addEventListener("click", (e) => {
      e.preventDefault();
      chooserOpened++;
    });
    if (count === 0) await click(button("Add photo"));
    else {
      assert.equal(
        button("Add photo"),
        undefined,
        "Four photos remains the maximum",
      );
      await click(
        document.querySelectorAll(".photo-actions .action-menu-trigger")[2],
      );
      await click(
        button(
          "Replace photo",
          document.querySelectorAll(".action-popover")[2],
        ),
      );
    }
    assert.equal(chooserOpened, 1);
    const file = new dom.window.File(["photo bytes"], "photo.png", {
      type: "image/png",
    });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      configurable: true,
    });
    await act(async () =>
      fileInput.dispatchEvent(new Event("change", { bubbles: true })),
    );
    assert.equal(uploads.length, 1);
    assert.equal(uploads[0].slot, count === 0 ? 1 : 3);
    assert.equal(uploads[0].file, file);
    await act(async () => root.unmount());
  }
  console.log(
    "Catalogue UI tests passed: EN/RU search, keyboard selection/create, Price Book persistence callback, current-zone quote, retry without duplicate item, cancel, unchanged calculator routing, and EN/RU Price Book rate/category/edit/archive/delete confirmations and rate-group additions, and hidden photo upload/replace regression.",
  );
} finally {
  await rm(dir, { recursive: true, force: true });
  dom.window.close();
}
