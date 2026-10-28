export type NumberValue = number | string | null;
export interface User {
  id: string;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
  onboarding_completed: boolean;
}
export interface LineItem {
  id: string;
  estimate_id: string;
  zone_id: string | null;
  section: string | null;
  sort_order: number;
  name: string;
  description: string | null;
  calc_type: string;
  quantity: NumberValue;
  unit: string | null;
  unit_price: NumberValue;
  original_unit_price: NumberValue;
  total_price: NumberValue;
  is_tbd: boolean;
}
export interface Photo {
  id: string;
  zone_id: string;
  slot: number;
  file_path: string;
  original_name: string | null;
}
export interface Zone {
  id: string;
  estimate_id: string;
  sort_order: number;
  zone_type: string;
  label: string;
  room_name: string | null;
  wall_name: string | null;
  wall_width_ft: NumberValue;
  wall_height_ft: NumberValue;
  square_footage: NumberValue;
  linear_footage: NumberValue;
  notes: string | null;
  subtotal: NumberValue;
  line_items: LineItem[];
  images: Photo[];
}
export interface Estimate {
  pdf_layout?: {
    final_zone_photos?: Record<string, number>;
    [key: string]: unknown;
  } | null;
  source_estimate_id?: string | null;
  cover_image_id?: string | null;
  id: string;
  type: string;
  status: string;
  title: string | null;
  client_name: string | null;
  project_name: string | null;
  prepared_by: string | null;
  created_by_name?: string | null;
  updated_by_name?: string | null;
  estimate_date: string | null;
  description: string | null;
  notes: string | null;
  subtotal: NumberValue;
  final_total: NumberValue;
  markup_pct: NumberValue;
  discount_pct: NumberValue;
  manual_override: boolean;
  zones: Zone[];
  line_items: LineItem[];
  images: Photo[];
  created_at: string;
  updated_at: string;
}
export interface EstimateSummary {
  id: string;
  type: string;
  status: string;
  title: string | null;
  client_name: string | null;
  final_total: NumberValue;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}
export interface CalculatedItem {
  section: string;
  name: string;
  description?: string;
  calc_type: string;
  quantity: NumberValue;
  unit: string | null;
  unit_price: NumberValue;
  total_price: NumberValue;
}
export type JsonValue =
  string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type PricingConfig = Record<string, JsonValue>;
export interface PricingOption {
  label_ru?: string;
  key: string;
  label: string;
  price?: number;
  rate?: number;
}
export interface PricingSchema {
  wall: {
    base_rates: PricingOption[];
    addons_sf: PricingOption[];
    addons_fixed: PricingOption[];
  };
  cabinet: {
    base_rates: PricingOption[];
    types: PricingOption[];
    addons_lf: PricingOption[];
    glass_doors: PricingOption[];
  };
  mirror: { rate: number; minimum: number; types?: PricingOption[] };
  services: Record<
    string,
    { label: string; label_ru?: string; default_price: number; unit: string }
  >;
  materials: Record<string, { label: string; label_ru?: string; addon_key: string | null }>;
  colors: { group: string; options: string[] }[];
}
