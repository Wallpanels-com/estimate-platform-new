import type { CalculatedItem } from "./types";
export const roomTypes = [
  ["hallway", "Hallway / Entryway"],
  ["living_room", "Living Room"],
  ["kitchen", "Kitchen"],
  ["bedroom", "Bedroom"],
  ["bathroom", "Bathroom"],
  ["home_office", "Home Office"],
  ["bar", "Bar"],
  ["gym_media", "Gym / Media Room"],
  ["staircase", "Staircase / Landing"],
] as const;
export interface QuickRoom {
  id: string;
  room_type: string;
  label: string;
  width_ft: number;
  height_ft: number;
  options: Record<string, string | number | boolean>;
}
// Recovered as readable source from the original Quick Estimate. Intentionally
// separate from the regular server rule engine: these rates differ in the legacy UI.
export const quickRates = {
  wall: 80,
  mirror: 80,
  mirrorSmall: 95,
  mirrorLarge: 80,
  mirrorThreshold: 20,
  fireplace: 2200,
  fireplaceInstall: 1000,
  bottleRack: 1500,
  glassDoor: 650,
  tvStand: 600,
  tvStandFireplace: 800,
  kitchenBudget: 800,
  kitchenHigh: 1300,
  console: 1400,
  nightStand: 1400,
  vanity: 1200,
  deskBudget: 800,
  deskHigh: 1600,
  bar: 1200,
  builtin: 1200,
  wardrobe: 950,
};
export const buildoutTiers = [
  { max: 12, price: 2000 },
  { max: 18, price: 4000 },
  { max: 24, price: 5000 },
  { max: Infinity, price: 6000 },
];
export interface QuickPricing {
  quick_estimate?: {
    wall_rate?: number;
    mirror_rate?: number;
    mirror_installation?: {
      rate_small: number;
      rate_large: number;
      threshold_sf: number;
    };
    fixed_items?: Record<string, { price: number }>;
    buildout_tiers?: { max_ft: number; price: number }[];
  };
  cabinet_types?: Record<string, { base_rate: number }>;
}
export function calculateRoom(
  room: QuickRoom,
  pricing?: QuickPricing,
): CalculatedItem[] {
  const items: CalculatedItem[] = [];
  const o = room.options;
  const width = Number(room.width_ft) || 0;
  const sf = width * (Number(room.height_ft) || 0);
  const q = pricing?.quick_estimate;
  const cabinetRate = (key: string, fallback: number) =>
    pricing?.cabinet_types?.[key]?.base_rate ?? fallback;
  const r = {
    ...quickRates,
    wall: q?.wall_rate ?? quickRates.wall,
    mirror: q?.mirror_rate ?? quickRates.mirror,
    mirrorSmall: q?.mirror_installation?.rate_small ?? quickRates.mirrorSmall,
    mirrorLarge: q?.mirror_installation?.rate_large ?? quickRates.mirrorLarge,
    mirrorThreshold:
      q?.mirror_installation?.threshold_sf ?? quickRates.mirrorThreshold,
    fireplace: q?.fixed_items?.efireplace_unit?.price ?? quickRates.fireplace,
    fireplaceInstall:
      q?.fixed_items?.fireplace_installation?.price ??
      quickRates.fireplaceInstall,
    bottleRack: q?.fixed_items?.bottle_racks?.price ?? quickRates.bottleRack,
    tvStand: cabinetRate("tv_stand", quickRates.tvStand),
    console: cabinetRate("entry_console", quickRates.console),
    nightStand: cabinetRate("night_stands", quickRates.nightStand),
    vanity: cabinetRate("vanity", quickRates.vanity),
    deskBudget: cabinetRate("desk_budget", quickRates.deskBudget),
    deskHigh: cabinetRate("desk_highend", quickRates.deskHigh),
    bar: cabinetRate("bar_cabinetry", quickRates.bar),
    builtin: cabinetRate("builtin_cabinetry", quickRates.builtin),
    wardrobe: cabinetRate("wardrobe_closet", quickRates.wardrobe),
  };
  const tiers =
    q?.buildout_tiers?.map((tier) => ({
      max: tier.max_ft,
      price: tier.price,
    })) || buildoutTiers;
  const priced = (
    name: string,
    section: string,
    quantity: number,
    unit: string,
    rate: number,
  ) => {
    items.push({
      name,
      section,
      description: "",
      calc_type: unit === "SF" ? "sf" : unit === "LF" ? "lf" : "fixed",
      quantity,
      unit,
      unit_price: rate,
      total_price: quantity * rate,
    });
  };
  const blank = (name: string, section = "Services") => {
    items.push({
      name,
      section,
      description: "",
      calc_type: "fixed",
      quantity: null,
      unit: null,
      unit_price: null,
      total_price: 0,
    });
  };
  const wall = (name = "Wall Panels") => {
    if (sf > 0) priced(name, "Wall Panels", sf, "SF", r.wall);
  };
  const led = (name = "LED Lighting") => blank(name, "Lighting");
  const electrical = () => blank("Electrical Work");
  const protection = () => blank("Floor & Furniture Protection");
  const mirror = () => {
    const qty = Number(o.mirror_sf) || 0;
    if (qty > 0) {
      priced("Mirror", "Mirrors", qty, "SF", r.mirror);
      priced(
        "Mirror Delivery & Installation",
        "Mirrors",
        qty,
        "SF",
        qty <= r.mirrorThreshold ? r.mirrorSmall : r.mirrorLarge,
      );
    }
  };
  const cabinet = (key: string, name: string, rate: number) => {
    const qty = Number(o[key]) || 0;
    if (qty > 0) priced(name, "Cabinetry", qty, "LF", rate);
  };
  switch (room.room_type) {
    case "hallway":
      wall();
      led();
      mirror();
      cabinet("console_lf", "Entry Console", r.console);
      electrical();
      protection();
      break;
    case "living_room": {
      wall("Feature Wall / TV Wall");
      led();
      const fireplace = !!o.fireplace;
      const length =
        width <= 10 ? width : width <= 16 ? width - 4 : Math.round(width / 2);
      if (length > 0)
        priced(
          `TV Stand${fireplace ? " with Fireplace" : ""}`,
          "Cabinetry",
          length,
          "LF",
          fireplace ? r.tvStandFireplace : r.tvStand,
        );
      if (fireplace) {
        priced("E-Fireplace Unit", "Fireplace", 1, "ea", r.fireplace);
        priced(
          "Fireplace Installation",
          "Fireplace",
          1,
          "ea",
          r.fireplaceInstall,
        );
      }
      if (Number(o.buildout_ft) > 0)
        priced(
          "Wall Build-out",
          "Construction",
          1,
          "ea",
          (
            tiers.find((t) => Number(o.buildout_ft) <= t.max) ||
            tiers[tiers.length - 1]
          ).price,
        );
      electrical();
      break;
    }
    case "kitchen": {
      const high = o.tier === "highend";
      const rate = high ? r.kitchenHigh : r.kitchenBudget;
      cabinet(
        "cabinet_lf",
        `Kitchen Cabinets - ${high ? "High-end" : "Budget"}`,
        rate,
      );
      cabinet(
        "island_lf",
        `Kitchen Island - ${high ? "High-end" : "Budget"}`,
        rate,
      );
      blank("Backsplash Installation", "Finishes");
      led();
      blank("Countertop", "Finishes");
      blank("Plumbing Services");
      blank("Electrical / Appliance Installation");
      protection();
      break;
    }
    case "bedroom":
      wall();
      led();
      mirror();
      priced(
        "Night Stands",
        "Cabinetry",
        Number(o.nightstand_lf ?? 4),
        "LF",
        r.nightStand,
      );
      cabinet("wardrobe_lf", "Wardrobe / Closet", r.wardrobe);
      electrical();
      protection();
      break;
    case "bathroom":
      wall();
      cabinet("vanity_lf", "Vanity", r.vanity);
      mirror();
      led();
      blank("Plumbing Services");
      electrical();
      protection();
      break;
    case "home_office":
      if (o.wall_panels) wall();
      cabinet("cabinetry_lf", "Built-in Cabinetry / Shelving", r.builtin);
      cabinet(
        "desk_lf",
        `Built-in Desk - ${o.desk_tier === "highend" ? "High-end" : "Budget"}`,
        o.desk_tier === "highend" ? r.deskHigh : r.deskBudget,
      );
      led();
      electrical();
      blank("Appliance / Device Installation");
      protection();
      break;
    case "bar":
      cabinet("bar_lf", "Bar Cabinetry", r.bar);
      wall("Accent Wall");
      blank("Backsplash Installation", "Finishes");
      led();
      blank("Countertop", "Finishes");
      priced(
        "Bottle Racks",
        "Accessories",
        Number(o.bottle_racks ?? 1),
        "ea",
        r.bottleRack,
      );
      if (width > 0) {
        const count = Math.floor((width * 12) / 26);
        if (count > 0)
          priced(
            "Glass Doors - standard",
            "Cabinetry",
            count,
            "ea",
            r.glassDoor,
          );
      }
      blank("Plumbing Services");
      electrical();
      protection();
      break;
    case "gym_media":
      wall();
      led();
      cabinet("storage_lf", "Built-in Storage", r.builtin);
      electrical();
      protection();
      break;
    case "staircase":
      wall("Staircase Wall Panels");
      led("LED Strip Lighting");
      electrical();
      protection();
      break;
  }
  return items;
}
export const roomOptions: Record<string, [string, string][]> = {
  hallway: [
    ["mirror_sf", "Mirror area (SF)"],
    ["console_lf", "Console length (LF)"],
  ],
  living_room: [["buildout_ft", "Wall build-out width (ft)"]],
  kitchen: [
    ["cabinet_lf", "Cabinet length (LF)"],
    ["island_lf", "Island length (LF)"],
  ],
  bedroom: [
    ["nightstand_lf", "Night stands (LF)"],
    ["mirror_sf", "Mirror area (SF)"],
    ["wardrobe_lf", "Wardrobe length (LF)"],
  ],
  bathroom: [
    ["vanity_lf", "Vanity length (LF)"],
    ["mirror_sf", "Mirror area (SF)"],
  ],
  home_office: [
    ["cabinetry_lf", "Cabinetry length (LF)"],
    ["desk_lf", "Desk length (LF)"],
  ],
  bar: [
    ["bar_lf", "Bar cabinetry (LF)"],
    ["bottle_racks", "Bottle racks (qty)"],
  ],
  gym_media: [["storage_lf", "Built-in storage (LF)"]],
  staircase: [],
};
