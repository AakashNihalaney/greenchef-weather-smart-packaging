"""
api_client.py — Green Chef PackOps™ 2026
Katana ERP integration + Green Chef BOM packing list builder.

Green Chef packaging BOM — exact scope per sustainability brief:

  BASE BOX COMPONENTS (unchanged across all tiers):
  ─────────────────────────────────────────────────
  • Standard Box          — exterior corrugated cardboard, already sustainable
  • ClimaCell Liner       — plant-based EPS alternative, curbside recyclable
  • Paper Kit Bag         — paper-based bag grouping all ingredients, already sustainable
  • Recipe Card           — paper, already sustainable
  • [Kit Label]           — not modelled

  TIER 1 — Nutri-Ice (ice pack only):
  ─────────────────────────────────────
  Replaces Pelton Shepherd standard ice pack with Nutri-Ice.
  Qty/configuration scaled by FDA temperature tier (weather engine).
  Scope = ice pack ONLY. Everything else in the box is unchanged.

  TIER 2 — Sustainable bag alternatives (autobagger bags only):
  ──────────────────────────────────────────────────────────────
  Only the three plastic autobagger variants are modelled:
    • Autobagger 5×11.5 small  (clear perforated)  → paper alternative
    • Autobagger 5×11.5 alt    (clear perforated)  → paper alternative
    • Autobagger 8×13.5        (clear perforated)  → paper alternative
  Assigned per ingredient based on size/weight (see bag_type field in order items).

  NOT MODELLED (no cost data / already sustainable / out of scope):
  ──────────────────────────────────────────────────────────────────
  • Sauce containers     — no cost data for alternative
  • Meat packaging       — no cost data for alternative
  • Spice sachets        — not broken out in cost file
"""

import json
import os
import requests
from pathlib import Path
from typing import Optional
from database import upsert_order, log

MOCK_DATA_PATH  = Path(__file__).parent / "mock_data.json"
KATANA_BASE_URL = os.getenv("KATANA_BASE_URL", "https://api.katanamrp.com/v1")
KATANA_API_KEY  = os.getenv("KATANA_API_KEY", "")


def _load_mock() -> dict:
    with open(MOCK_DATA_PATH) as f:
        return json.load(f)


def _katana_headers() -> dict:
    return {"Authorization": f"Bearer {KATANA_API_KEY}", "Content-Type": "application/json"}


def _fetch_live_orders() -> list[dict]:
    try:
        resp = requests.get(
            f"{KATANA_BASE_URL}/sales_orders",
            headers=_katana_headers(),
            params={"status": "open"},
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json().get("data", [])
        return [_normalize_katana_order(o) for o in raw]
    except Exception as e:
        log("WARNING", "api_client", f"Katana live fetch failed: {e}. Falling back to mock data.")
        return []


def _normalize_katana_order(raw: dict) -> dict:
    addr  = raw.get("shipping_address", {})
    items = []
    for line in raw.get("sales_order_rows", []):
        sku = line.get("product_variant_code", "UNK-000")
        items.append({
            "sku":       sku,
            "name":      line.get("product_name", "Unknown Item"),
            "qty":       line.get("quantity", 1),
            "weight_kg": line.get("unit_weight_kg", 0.30),
            "category":  line.get("category", ""),
            "bag_type":  line.get("bag_type", "autobagger_5x11_a"),
        })
    return {
        "order_id":        raw.get("order_no", ""),
        "customer_name":   raw.get("customer_name", ""),
        "delivery_address": addr.get("address_line_1", ""),
        "city":            addr.get("city", ""),
        "state":           addr.get("state", ""),
        "zip_code":        addr.get("zip", ""),
        "delivery_date":   raw.get("delivery_date", ""),
        "items":           items,
        "status":          "pending",
    }


# ── Bag type → catalog key mapping ───────────────────────────────────────────
BAG_TYPE_TO_CATALOG = {
    "autobagger_5x11_a": "Autobagger 5x11 Small (Paper Alt)",
    "autobagger_5x11_b": "Autobagger 5x11 Alt (Paper Alt)",
    "autobagger_8x13":   "Autobagger 8x13 (Paper Alt)",
    "none":              None,   # sauce containers, meat packaging, spice sachets — not modelled
}


class KatanaClient:

    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock or not KATANA_API_KEY
        self._mock    = _load_mock() if self.use_mock else {}

    def fetch_open_orders(self) -> list[dict]:
        if self.use_mock:
            orders = self._mock.get("katana_orders", [])
            log("INFO", "api_client", f"Loaded {len(orders)} mock orders from mock_data.json")
        else:
            orders = _fetch_live_orders()
            if not orders:
                orders = self._mock.get("katana_orders", [])
        for o in orders:
            upsert_order(o)
        return orders

    def get_order_by_id(self, order_id: str) -> Optional[dict]:
        orders = self.fetch_open_orders()
        match  = next((o for o in orders if o["order_id"] == order_id), None)
        if not match:
            log("WARNING", "api_client", f"Order {order_id} not found.")
        return match

    def get_packing_materials_catalog(self) -> dict:
        raw = self._mock.get("packing_materials", {})
        # Strip comment-only keys (start with _)
        return {k: v for k, v in raw.items() if not k.startswith("_")}

    def build_base_packing_list(self, order: dict) -> list[dict]:
        """
        Build the exact Green Chef box BOM for one order.

        Fixed box components (base tier — always included, no change):
          1. Standard Box       — outer corrugated cardboard
          2. ClimaCell Liner    — insulated plant-based liner
          3. Paper Kit Bag      — groups all ingredients
          4. Recipe Card        — paper recipe instructions

        Temperature-scaled ice (Tier 1 — weather engine overrides qty/type):
          5. Nutri-Ice Pack     — replaces Pelton Shepherd; qty set by FDA tier

        Per-ingredient bags (Tier 2 — assigned by bag_type on each item):
          • Autobagger 5×11.5 small  → small produce, herbs, small dairy
          • Autobagger 5×11.5 alt    → medium produce, cheese bags
          • Autobagger 8×13.5        → protein, grains, larger items

        Items with bag_type = "none" (sauce containers, meat pkging, spice sachets)
        are NOT assigned a bag here — no sustainable alternative is modelled.
        """
        catalog    = self.get_packing_materials_catalog()
        packing    = []
        items      = order.get("items", [])
        categories = {i.get("category", "") for i in items}
        has_perishable = bool({"protein", "dairy", "produce", "herb", "sauce"} & categories)

        # ── 1. Standard Box ───────────────────────────────────────────────────
        box = catalog.get("Standard Box", {})
        packing.append({
            **box,
            "name":   "Standard Box",
            "qty":    1,
            "source": "base",
            "tier":   "base",
            "note":   "Exterior corrugated cardboard — already sustainable, no change",
        })

        # ── 2. ClimaCell Liner ────────────────────────────────────────────────
        climacell = catalog.get("ClimaCell Liner", {})
        packing.append({
            **climacell,
            "name":   "ClimaCell Liner",
            "qty":    1,
            "source": "base",
            "tier":   "base",
            "note":   "Plant-based insulated liner, curbside recyclable — no change needed",
        })

        # ── 3. Paper Kit Bag ──────────────────────────────────────────────────
        kit_bag = catalog.get("Paper Kit Bag", {})
        packing.append({
            **kit_bag,
            "name":   "Paper Kit Bag",
            "qty":    1,
            "source": "base",
            "tier":   "base",
            "note":   "Paper-based bag — already sustainable, no change",
        })

        # ── 4. Recipe Card ────────────────────────────────────────────────────
        card = catalog.get("Recipe Card", {})
        packing.append({
            **card,
            "name":   "Recipe Card",
            "qty":    1,
            "source": "base",
            "tier":   "base",
            "note":   "Paper recipe card — already sustainable, no change",
        })

        # ── 5. Nutri-Ice Pack baseline (Tier 1) ───────────────────────────────
        # The weather engine will override qty/count based on FDA temperature tier.
        # This baseline of 1 is always included for any order with perishables.
        if has_perishable:
            nutrice = catalog.get("Nutri-Ice Pack", {})
            packing.append({
                **nutrice,
                "name":   "Nutri-Ice Pack",
                "qty":    1,
                "source": "base",
                "tier":   "tier1",
                "note":   "Tier 1: Nutri-Ice replaces Pelton Shepherd — weather engine adjusts qty",
            })
            log("INFO", "api_client",
                f"Order {order['order_id']}: Nutri-Ice Pack (Tier 1) added as baseline")

        # ── 6. Autobagger bag per ingredient (Tier 2) ─────────────────────────
        # Count how many of each bag variant are needed across all ingredients.
        bag_counts: dict[str, int] = {}
        for item in items:
            bag_type = item.get("bag_type", "none")
            cat_key  = BAG_TYPE_TO_CATALOG.get(bag_type)
            if cat_key is None:
                # Sauce containers, meat packaging, spice sachets — not modelled
                log("INFO", "api_client",
                    f"  {item['name']}: bag_type=none — sauce/meat/spice packaging "
                    "not modelled in Tier 2 cost file")
                continue
            if cat_key not in catalog:
                log("WARNING", "api_client",
                    f"  Bag catalog entry '{cat_key}' not found for {item['name']}")
                continue
            bag_counts[cat_key] = bag_counts.get(cat_key, 0) + item.get("qty", 1)

        for bag_name, count in bag_counts.items():
            bag_entry = catalog.get(bag_name, {})
            packing.append({
                **bag_entry,
                "name":   bag_name,
                "qty":    count,
                "source": "tier2-bag",
                "tier":   "tier2",
                "note":   f"Tier 2: sustainable paper alternative to clear perforated plastic bag — {bag_entry.get('description','')}",
            })

        if bag_counts:
            log("INFO", "api_client",
                f"Order {order['order_id']}: Tier 2 bags — "
                + ", ".join(f"{k} x{v}" for k, v in bag_counts.items()))

        return packing
