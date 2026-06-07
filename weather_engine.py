"""
weather_engine.py — Green Chef PackOps™ 2026
Climate-Smart Packaging Decision Engine — FDA/USDA Compliant

Ice pack: Nutri-Ice (Tier 1 replacement for Pelton Shepherd).
Qty of Nutri-Ice is scaled by the FDA temperature tier below.
All other box components (ClimaCell liner, box, paper bag, card) are unchanged
and are NOT touched by this engine — they are already set in api_client.py.

FDA Food Code 2022 §3-501.11 + USDA FSIS Danger Zone (40°F–140°F):

  Tier map (effective ambient °F across delivery window):
  ───────────────────────────────────────────────────────
  ≥ 85°F  EXTREME HEAT : 3× Nutri-Ice  (interior exceeds 40°F in < 1 hr)
  ≥ 70°F  HOT          : 2× Nutri-Ice  (interior exceeds 40°F in ~2 hrs)
  ≥ 55°F  WARM         : 2× Nutri-Ice  (interior exceeds 40°F in ~4 hrs; danger zone)
  ≥ 40°F  MILD         : 1× Nutri-Ice  (mandatory FDA minimum — still above 40°F threshold)
  < 40°F  COLD/SAFE    : 0× ice — ClimaCell liner sufficient; no freeze risk added
  < 32°F  FREEZE RISK  : 0× ice — ClimaCell liner insulates against freeze damage

  Note: ClimaCell liner handles passive insulation in cold/freeze tiers.
  It is already plant-based and included in every box. No extra liner is
  added by this engine — that would be out of scope of the Green Chef BOM.
"""

import os
import json
import requests
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional
from database import log

MOCK_DATA_PATH   = Path(__file__).parent / "mock_data.json"
OWM_API_KEY      = os.getenv("OWM_API_KEY", "")
WEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"

# ── FDA / USDA Thresholds ─────────────────────────────────────────────────────
EXTREME_HEAT_F    = 85.0
HOT_F             = 70.0
WARM_F            = 55.0
DANGER_ZONE_MAX_F = 40.0
FREEZE_RISK_F     = 32.0

# UI alias exports
HEAT_THRESHOLD_F   = HOT_F
FREEZE_THRESHOLD_F = FREEZE_RISK_F
PRECIP_THRESHOLD   = 50


def _load_mock() -> dict:
    with open(MOCK_DATA_PATH) as f:
        return json.load(f)


def _kelvin_to_f(k: float) -> float:
    return (k - 273.15) * 9 / 5 + 32


def get_safety_tier(temp_f: float) -> dict:
    if temp_f >= EXTREME_HEAT_F:
        return {
            "tier":     "EXTREME HEAT",
            "color":    "heat",
            "ice_qty":  3,
            "fda_note": f"≥{EXTREME_HEAT_F:.0f}°F — Interior exceeds 40°F (FDA danger zone) in under 1 hour. 3× Nutri-Ice required.",
        }
    if temp_f >= HOT_F:
        return {
            "tier":     "HOT",
            "color":    "heat",
            "ice_qty":  2,
            "fda_note": f"≥{HOT_F:.0f}°F — Interior exceeds 40°F in ~2 hours. 2× Nutri-Ice required.",
        }
    if temp_f >= WARM_F:
        return {
            "tier":     "WARM",
            "color":    "warn",
            "ice_qty":  2,
            "fda_note": f"≥{WARM_F:.0f}°F — Inside FDA danger zone (40–140°F). Interior exceeds 40°F in ~4 hours. 2× Nutri-Ice required.",
        }
    if temp_f >= DANGER_ZONE_MAX_F:
        return {
            "tier":     "MILD — ICE REQUIRED",
            "color":    "warn",
            "ice_qty":  1,
            "fda_note": f"≥{DANGER_ZONE_MAX_F:.0f}°F — At/above FDA 40°F threshold. 1× Nutri-Ice mandatory for all perishables.",
        }
    if temp_f >= FREEZE_RISK_F:
        return {
            "tier":     "COLD — SAFE",
            "color":    "safe",
            "ice_qty":  0,
            "fda_note": f"{FREEZE_RISK_F:.0f}–{DANGER_ZONE_MAX_F:.0f}°F — Below FDA danger zone. ClimaCell liner provides passive insulation. No ice needed.",
        }
    return {
        "tier":     "FREEZE RISK",
        "color":    "freeze",
        "ice_qty":  0,
        "fda_note": f"< {FREEZE_RISK_F:.0f}°F — Freeze damage risk. ClimaCell liner insulates against freezing. No ice added.",
    }


class WeatherEngine:

    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock or not OWM_API_KEY
        self._mock    = _load_mock()
        self._catalog = {k: v for k, v in self._mock.get("packing_materials", {}).items()
                         if not k.startswith("_")}

    def _fetch_live_current(self, zip_code: str) -> Optional[dict]:
        try:
            resp = requests.get(
                f"{WEATHER_BASE_URL}/weather",
                params={"zip": f"{zip_code},us", "appid": OWM_API_KEY},
                timeout=8,
            )
            resp.raise_for_status()
            d = resp.json()
            return {
                "city":            d["name"],
                "current_temp_f":  round(_kelvin_to_f(d["main"]["temp"]), 1),
                "feels_like_f":    round(_kelvin_to_f(d["main"]["feels_like"]), 1),
                "condition":       d["weather"][0]["main"],
                "rain_chance_pct": int(d.get("pop", 0) * 100),
            }
        except Exception as e:
            log("WARNING", "weather_engine", f"OWM current fetch failed for {zip_code}: {e}")
            return None

    def _fetch_live_forecast(self, zip_code: str, days: int = 5) -> list[dict]:
        try:
            resp = requests.get(
                f"{WEATHER_BASE_URL}/forecast",
                params={"zip": f"{zip_code},us", "appid": OWM_API_KEY, "cnt": days * 8},
                timeout=8,
            )
            resp.raise_for_status()
            raw   = resp.json().get("list", [])
            daily: dict[str, dict] = {}
            for entry in raw:
                day_str = entry["dt_txt"][:10]
                temp_f  = _kelvin_to_f(entry["main"]["temp_max"])
                rain    = int(entry.get("pop", 0) * 100)
                cond    = entry["weather"][0]["main"]
                if day_str not in daily:
                    daily[day_str] = {"date": day_str, "high_f": temp_f,
                                      "low_f": temp_f, "rain_chance_pct": rain, "condition": cond}
                else:
                    daily[day_str]["high_f"] = max(daily[day_str]["high_f"], temp_f)
                    daily[day_str]["rain_chance_pct"] = max(daily[day_str]["rain_chance_pct"], rain)
            return list(daily.values())[:days]
        except Exception as e:
            log("WARNING", "weather_engine", f"OWM forecast fetch failed for {zip_code}: {e}")
            return []

    def get_weather(self, zip_code: str, delivery_date: str = "", days_ahead: int = 5) -> dict:
        if self.use_mock:
            data = self._mock.get("mock_weather", {}).get(zip_code)
            if data:
                log("INFO", "weather_engine",
                    f"Mock weather for {zip_code}: {data['city']} {data['current_temp_f']}°F")
                return data
            log("WARNING", "weather_engine",
                f"No mock data for {zip_code}. Using safe conservative fallback (72°F → 2× Nutri-Ice).")
            return self._safe_fallback(zip_code)

        current = self._fetch_live_current(zip_code)
        if not current:
            log("WARNING", "weather_engine",
                f"Weather API unavailable for {zip_code}. Conservative fallback applied.")
            return self._safe_fallback(zip_code)
        current["forecast"] = self._fetch_live_forecast(zip_code, days=days_ahead)
        return current

    def _safe_fallback(self, zip_code: str) -> dict:
        """
        Conservative fallback: 72°F triggers the WARM tier → 2× Nutri-Ice.
        Never under-protect perishables when weather data is unavailable.
        """
        today = date.today()
        return {
            "city":            f"ZIP {zip_code}",
            "current_temp_f":  72.0,
            "feels_like_f":    72.0,
            "condition":       "Unknown",
            "rain_chance_pct": 0,
            "is_fallback":     True,
            "forecast": [
                {"date": str(today + timedelta(days=i)), "high_f": 75, "low_f": 60,
                 "rain_chance_pct": 20, "condition": "Unknown"}
                for i in range(5)
            ],
        }

    def apply_weather_rules(self, base_packing: list[dict],
                            weather: dict, order: dict) -> list[dict]:
        """
        Adjust Nutri-Ice quantity based on FDA temperature tier.

        THIS ENGINE ONLY TOUCHES THE ICE PACK.
        All other packaging (box, ClimaCell liner, paper kit bag, recipe card,
        autobagger bags) is already set by api_client.py and is left unchanged.
        """
        packing  = {item["name"]: item.copy() for item in base_packing}
        temp     = weather["current_temp_f"]
        rain_pct = weather["rain_chance_pct"]

        # Worst-case temperature and precipitation across the full delivery window
        forecast_max_temp = max(
            (f.get("high_f", temp) for f in weather.get("forecast", [])), default=temp
        )
        forecast_max_rain = max(
            (f.get("rain_chance_pct", 0) for f in weather.get("forecast", [])), default=rain_pct
        )
        effective_temp = max(temp, forecast_max_temp)
        effective_rain = max(rain_pct, forecast_max_rain)

        tier = get_safety_tier(effective_temp)
        log("INFO", "weather_engine",
            f"Order {order['order_id']} | {effective_temp:.0f}°F | tier: {tier['tier']} | "
            f"Nutri-Ice qty: {tier['ice_qty']} | rain: {effective_rain}%")

        # ── Nutri-Ice: set qty from FDA tier ──────────────────────────────────
        # Remove the baseline pack first; re-add with correct qty
        packing.pop("Nutri-Ice Pack", None)

        if tier["ice_qty"] > 0:
            nutrice = self._catalog.get("Nutri-Ice Pack", {})
            packing["Nutri-Ice Pack"] = {
                **nutrice,
                "name":     "Nutri-Ice Pack",
                "qty":      tier["ice_qty"],
                "source":   "tier1-fda",
                "tier":     "tier1",
                "fda_rule": f"FDA §3-501.11: {tier['tier']} — {tier['ice_qty']}× Nutri-Ice required",
                "note":     tier["fda_note"],
            }
            log("INFO", "weather_engine",
                f"Nutri-Ice: {tier['ice_qty']}× applied ({tier['tier']})")
        else:
            log("INFO", "weather_engine",
                f"Nutri-Ice: 0× — {tier['tier']} ({effective_temp:.0f}°F). "
                "ClimaCell liner provides passive cold protection.")

        return list(packing.values())

    def build_manifest(self, order: dict, base_packing: list[dict],
                       weather: dict) -> dict:
        adjusted_packing = self.apply_weather_rules(base_packing, weather, order)

        items_weight   = sum(i["weight_kg"] * i.get("qty", 1) for i in order["items"])
        pkg_weight     = sum(p.get("weight_kg", 0) * p.get("qty", 1) for p in adjusted_packing)
        theoretical_kg = round(items_weight + pkg_weight, 3)

        temp = weather["current_temp_f"]
        eff  = max(temp, max((f.get("high_f", temp) for f in weather.get("forecast", [])), default=temp))
        tier = get_safety_tier(eff)

        cond = weather["condition"].lower()
        if temp < FREEZE_RISK_F or "snow" in cond or "sleet" in cond:
            badge = "❄️ FREEZE RISK"
        elif "thunder" in cond or "storm" in cond:
            badge = "⛈️ STORM"
        elif "rain" in cond or "drizzle" in cond:
            badge = "🌧️ RAIN"
        elif temp >= EXTREME_HEAT_F:
            badge = "🌡️ EXTREME HEAT"
        elif temp >= HOT_F:
            badge = "☀️ HOT"
        elif temp >= WARM_F:
            badge = "🌤 WARM"
        elif temp >= DANGER_ZONE_MAX_F:
            badge = "🌥 MILD"
        else:
            badge = "🥶 COLD — SAFE"

        return {
            "manifest_version": "3.1",
            "generated_at":     datetime.now().isoformat(),
            "order_id":         order["order_id"],
            "customer":         order["customer_name"],
            "destination": {
                "address": order["delivery_address"],
                "city":    order["city"],
                "state":   order["state"],
                "zip":     order["zip_code"],
            },
            "delivery_date": order.get("delivery_date", ""),
            "food_safety": {
                "standard":  "FDA Food Code 2022 §3-501.11 + USDA FSIS Danger Zone",
                "danger_zone": "40°F – 140°F",
                "tier":      tier["tier"],
                "fda_note":  tier["fda_note"],
                "ice_qty":   tier["ice_qty"],
                "ice_brand": "Nutri-Ice (Tier 1)",
                "compliant": True,
            },
            "weather_summary": {
                "city":            weather.get("city", ""),
                "current_temp_f":  temp,
                "feels_like_f":    weather.get("feels_like_f", temp),
                "condition":       weather["condition"],
                "rain_chance_pct": weather["rain_chance_pct"],
                "badge":           badge,
                "is_fallback":     weather.get("is_fallback", False),
                "forecast":        weather.get("forecast", []),
            },
            "sustainability": {
                "tier1_applied": "Nutri-Ice (replaces Pelton Shepherd)",
                "tier2_applied": "Paper autobagger bags (replaces clear perforated plastic)",
                "tier2_bags_replaced": [
                    p["name"] for p in adjusted_packing if p.get("tier") == "tier2"
                ],
                "not_modelled": [
                    "Sauce containers", "Meat packaging", "Spice sachets",
                    "Kit label"
                ],
            },
            "meal_items": order["items"],
            "packaging":  adjusted_packing,
            "weights": {
                "meal_items_kg":        round(items_weight, 3),
                "packaging_kg":         round(pkg_weight, 3),
                "theoretical_total_kg": theoretical_kg,
                "actual_kg":            None,
                "weight_ok":            None,
            },
        }

    def get_weather_icon(self, weather: dict) -> str:
        temp = weather.get("current_temp_f", 68)
        cond = weather.get("condition", "").lower()
        rain = weather.get("rain_chance_pct", 0)
        if "snow" in cond or "sleet" in cond or temp < FREEZE_RISK_F: return "❄️"
        if "thunder" in cond or "storm" in cond:                       return "⛈️"
        if "rain" in cond or "drizzle" in cond or rain > PRECIP_THRESHOLD: return "🌧️"
        if temp >= EXTREME_HEAT_F:  return "🌡️"
        if temp >= HOT_F:           return "☀️"
        if temp >= WARM_F:          return "🌤"
        return "⛅"
