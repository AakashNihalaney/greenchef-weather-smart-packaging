"""
app.py — Green Chef PackOps™ 2026
Climate-Smart Fulfillment · Ingredient-by-Ingredient Packing Interface
"""

import streamlit as st
import json, base64, random
from datetime import datetime, date, timedelta
from pathlib import Path

st.set_page_config(
    page_title="Green Chef PackOps™",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

import sys
sys.path.insert(0, str(Path(__file__).parent))
from database       import init_db, get_all_orders, get_order, save_manifest, \
                           get_recent_logs, add_manual_order, update_order_status
from api_client     import KatanaClient
from weather_engine import (WeatherEngine, PRECIP_THRESHOLD,
                            HEAT_THRESHOLD_F, FREEZE_THRESHOLD_F,
                            EXTREME_HEAT_F, HOT_F, WARM_F, DANGER_ZONE_MAX_F, FREEZE_RISK_F,
                            get_safety_tier)
from p2l_controller import P2LController

init_db()
katana  = KatanaClient(use_mock=True)
weather = WeatherEngine(use_mock=True)
p2l     = P2LController(protocol="simulated")
katana.fetch_open_orders()

# ── Logo (embedded base64 so no static file server needed) ────────────────────
LOGO_PATH = Path(__file__).parent / "greenchef_logo.png"
def get_logo_b64():
    try:
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""
LOGO_B64 = get_logo_b64()
LOGO_HTML = (f'<img src="data:image/png;base64,{LOGO_B64}" style="height:44px;border-radius:6px;">'
             if LOGO_B64 else '<span style="font-size:26px;">🌿</span>')

# ── Category icons ────────────────────────────────────────────────────────────
CAT_ICON = {
    "protein": "🥩", "produce": "🥦", "herb": "🌿", "dairy": "🧀",
    "grain": "🌾", "pantry": "🫙", "sauce": "🫕", "packaging": "📦",
}

TRANSIT_ICON = {
    "Corrugated Liner Sheet":   "📋",
    "Molded Pulp Tray":         "🫙",
    "Bubble Wrap Sheet":        "🫧",
    "Leak-Proof Bag":           "🛡️",
    "Divider Cardboard Insert": "📐",
    "Corner Foam Pad":          "🔲",
}

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');
:root {
  --gc-green:       #4a7c59;
  --gc-green-mid:   #3d6b4a;
  --gc-green-dark:  #2e5438;
  --gc-green-deep:  #1e3d28;
  --gc-green-light: #7ab893;
  --gc-green-pale:  #b8d9c4;
  --gc-white:       #ffffff;
  --gc-charcoal:    #1a2820;
  --gc-forest:      #1f3028;
  --gc-bark:        #263830;
  --gc-moss:        #2e4436;
  --gc-sage:        #5a7a64;
  --gc-mist:        #8aad96;
  --gc-amber:       #e8a030;
  --gc-amber-soft:  #f5c870;
  --gc-ember:       #d94f3d;
  --gc-sky:         #4ab8d4;
  --gc-text:        #ddeee3;
  --gc-text-muted:  #7a9e86;
  --gc-border:      rgba(74,124,89,0.25);
  --gc-border-mid:  rgba(74,124,89,0.45);
  --gc-border-hi:   rgba(74,124,89,0.7);
}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;background:var(--gc-charcoal);color:var(--gc-text);}

/* Sidebar */
[data-testid="stSidebar"]{background:var(--gc-forest);border-right:1px solid var(--gc-border);}
[data-testid="stSidebar"] *{color:var(--gc-text)!important;}
[data-testid="stSidebar"] .stRadio label{font-size:14px!important;font-weight:500!important;padding:9px 14px!important;border-radius:9px!important;cursor:pointer;display:block;transition:background .15s;}
[data-testid="stSidebar"] .stRadio label:hover{background:rgba(74,124,89,.18)!important;}

/* Cards */
.gc-card{background:var(--gc-forest);border:1px solid var(--gc-border);border-radius:14px;padding:20px 22px;margin-bottom:14px;}
.gc-card-hdr{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gc-mist);margin-bottom:14px;}

/* Section titles */
.gc-title{font-size:24px;font-weight:600;color:var(--gc-white);letter-spacing:-.3px;margin-bottom:3px;}
.gc-sub{font-size:13px;color:var(--gc-mist);margin-bottom:20px;}

/* Weather banner */
.gc-wb{border-radius:16px;padding:22px 26px;margin-bottom:20px;display:flex;align-items:flex-start;gap:20px;position:relative;overflow:hidden;}
.gc-wb::before{content:'';position:absolute;inset:0;background:repeating-linear-gradient(-45deg,rgba(255,255,255,.025) 0,rgba(255,255,255,.025) 1px,transparent 1px,transparent 8px);}
.wb-heat  {background:linear-gradient(135deg,#6b2200,#b85000);border:1px solid #e07030;}
.wb-freeze{background:linear-gradient(135deg,#0d2440,#1a4070);border:1px solid #5090d0;}
.wb-rain  {background:linear-gradient(135deg,#0c2030,#1a3858);border:1px solid #3898c0;}
.wb-clear {background:linear-gradient(135deg,var(--gc-green-deep),var(--gc-green-dark));border:1px solid var(--gc-green);}
.wb-icon{font-size:56px;line-height:1;position:relative;z-index:1;flex-shrink:0;}
.wb-body{flex:1;position:relative;z-index:1;}
.wb-loc{font-size:12px;color:rgba(255,255,255,.6);letter-spacing:.05em;margin-bottom:3px;}
.wb-city{font-size:20px;font-weight:700;margin-bottom:1px;}
.wb-temp{font-size:42px;font-weight:300;font-family:'DM Mono',monospace;line-height:1;letter-spacing:-2px;}
.wb-sup{font-size:18px;vertical-align:super;}
.wb-feels{font-size:12px;color:rgba(255,255,255,.6);margin-top:3px;}
.wb-tag{display:inline-block;margin-top:7px;margin-right:6px;font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;background:rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.18);padding:2px 9px;border-radius:20px;}

/* Forecast pills */
.fc-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;}
.fc-pill{background:rgba(0,0,0,.22);border:1px solid rgba(255,255,255,.1);border-radius:11px;padding:10px 14px;text-align:center;min-width:84px;flex:1;}
.fp-date{font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:rgba(255,255,255,.45);margin-bottom:5px;}
.fp-icon{font-size:20px;margin-bottom:4px;}
.fp-temp{font-size:19px;font-weight:600;font-family:'DM Mono',monospace;}
.fp-rain{font-size:11px;color:var(--gc-sky);margin-top:3px;}

/* Transit protection badge */
.ci-transit{background:rgba(74,160,212,.08);border-left:3px solid var(--gc-sky);}
.ci-badge-transit{margin-left:auto;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--gc-sky);background:rgba(74,160,212,.12);padding:2px 8px;border-radius:10px;border:1px solid rgba(74,160,212,.3);}
.ci-transit-note{font-size:11px;color:var(--gc-mist);margin-top:3px;font-style:italic;padding-left:2px;}

/* Metrics (sidebar) */
.gc-met{background:rgba(0,0,0,.2);border:1px solid var(--gc-border);border-radius:10px;padding:11px 13px;margin-bottom:7px;text-align:center;}
.gc-met-lbl{font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--gc-mist);margin-bottom:4px;}
.gc-met-val{font-size:23px;font-weight:600;font-family:'DM Mono',monospace;}

/* ═══════════════════════════════════════
   INGREDIENT PACKING CARDS — main feature
   ═══════════════════════════════════════ */
.pack-progress-bar-outer{background:rgba(0,0,0,.3);border-radius:20px;height:10px;margin-bottom:18px;overflow:hidden;border:1px solid var(--gc-border);}
.pack-progress-bar-inner{height:100%;border-radius:20px;background:linear-gradient(90deg,var(--gc-green-mid),var(--gc-green-light));transition:width .4s ease;}

/* Active card (current item to pack) */
.ing-card-active{
  background:var(--gc-forest);
  border:2px solid var(--gc-green);
  border-radius:16px;padding:22px 24px;margin-bottom:12px;
  box-shadow:0 0 24px rgba(74,124,89,.25);
  position:relative;overflow:hidden;
}
.ing-card-active::before{
  content:'';position:absolute;inset:0;
  background:linear-gradient(135deg,rgba(74,124,89,.08),transparent 60%);
  pointer-events:none;
}
/* Done card */
.ing-card-done{
  background:rgba(0,0,0,.15);
  border:1px solid rgba(74,124,89,.2);
  border-radius:12px;padding:14px 18px;margin-bottom:8px;
  opacity:.65;
}
/* Upcoming card */
.ing-card-upcoming{
  background:var(--gc-bark);
  border:1px solid var(--gc-border);
  border-radius:12px;padding:14px 18px;margin-bottom:8px;
}
.ing-row{display:flex;align-items:center;gap:14px;}
.ing-icon{font-size:28px;flex-shrink:0;}
.ing-icon-sm{font-size:20px;flex-shrink:0;}
.ing-name{font-size:16px;font-weight:600;line-height:1.2;}
.ing-name-sm{font-size:14px;font-weight:500;}
.ing-meta{font-size:12px;color:var(--gc-mist);margin-top:3px;}
.ing-qty-badge{font-family:'DM Mono',monospace;font-size:13px;background:var(--gc-green-dark);border:1px solid var(--gc-border-hi);color:var(--gc-green-pale);padding:3px 10px;border-radius:20px;white-space:nowrap;}
.ing-bin-badge{font-family:'DM Mono',monospace;font-size:11px;background:rgba(0,0,0,.3);border:1px solid var(--gc-border);color:var(--gc-mist);padding:2px 8px;border-radius:6px;white-space:nowrap;}
.ing-weight-tgt{font-size:22px;font-weight:300;font-family:'DM Mono',monospace;color:var(--gc-green-pale);}
.ing-weight-unit{font-size:13px;color:var(--gc-mist);margin-left:3px;}
.ing-done-tick{font-size:20px;margin-left:auto;flex-shrink:0;}
.ing-step-num{font-size:11px;font-weight:700;color:var(--gc-green-light);letter-spacing:.06em;margin-bottom:6px;}

/* Scale readout */
.scale-readout{
  background:rgba(0,0,0,.35);border:1px solid var(--gc-border-mid);
  border-radius:12px;padding:14px 20px;text-align:center;margin-top:14px;
}
.scale-lbl{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--gc-mist);margin-bottom:6px;}
.scale-val{font-size:38px;font-weight:300;font-family:'DM Mono',monospace;letter-spacing:-1px;}
.scale-unit{font-size:16px;color:var(--gc-mist);}
.scale-ok   {color:var(--gc-green-light);}
.scale-warn {color:var(--gc-amber);}
.scale-err  {color:var(--gc-ember);}

/* P2L flash badge */
.p2l-flash{
  display:inline-flex;align-items:center;gap:8px;
  background:rgba(74,124,89,.2);border:1px solid var(--gc-border-hi);
  border-radius:8px;padding:6px 14px;margin-top:12px;
  font-size:13px;font-family:'DM Mono',monospace;
}
.p2l-dots{color:var(--gc-green-light);letter-spacing:3px;font-size:16px;}

/* Weight box final */
.gc-wb-box{border-radius:12px;padding:16px 20px;text-align:center;}
.gwb-ok   {background:rgba(46,84,56,.35);border:1px solid var(--gc-green);}
.gwb-alert{background:rgba(217,79,61,.15);border:1px solid var(--gc-ember);}
.gwb-lbl  {font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;opacity:.65;margin-bottom:7px;}
.gwb-val  {font-size:30px;font-weight:300;font-family:'DM Mono',monospace;letter-spacing:-1px;}
.gwb-sub  {font-size:12px;margin-top:5px;opacity:.7;font-family:'DM Mono',monospace;}

/* Alert banner */
.gc-alert{background:rgba(120,25,20,.55);border:2px solid var(--gc-ember);color:#fca5a5;border-radius:12px;padding:16px 22px;font-weight:700;font-size:15px;text-align:center;animation:gc-blink 1.2s step-start infinite;}
@keyframes gc-blink{0%,100%{opacity:1}50%{opacity:.55}}
@keyframes gc-pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* P2L sidebar status */
.gc-p2l-pill{display:inline-flex;align-items:center;gap:7px;font-size:12px;font-weight:500;padding:5px 12px;border-radius:20px;border:1px solid var(--gc-border);background:rgba(0,0,0,.2);margin-bottom:14px;}
.dot-live{color:var(--gc-green-light);animation:gc-pulse 1.8s infinite;}
.dot-idle{color:var(--gc-sage);}

/* Buttons */
.stButton>button{background:var(--gc-green-dark)!important;color:white!important;border:none!important;border-radius:10px!important;font-family:'DM Sans',sans-serif!important;font-weight:600!important;font-size:14px!important;padding:10px 20px!important;transition:all .18s!important;}
.stButton>button:hover{background:var(--gc-green-mid)!important;transform:translateY(-1px)!important;box-shadow:0 4px 16px rgba(74,124,89,.35)!important;}

/* Inputs */
.stTextInput input,.stNumberInput input,.stDateInput input{background:var(--gc-bark)!important;border:1px solid var(--gc-border-mid)!important;color:var(--gc-text)!important;border-radius:8px!important;font-family:'DM Sans',sans-serif!important;}
.stSelectbox>div>div{background:var(--gc-bark)!important;border:1px solid var(--gc-border-mid)!important;color:var(--gc-text)!important;border-radius:8px!important;}

/* Tabs */
.stTabs [data-baseweb="tab"]{color:var(--gc-mist)!important;font-weight:600!important;background:transparent!important;}
.stTabs [aria-selected="true"]{color:var(--gc-green-light)!important;border-bottom-color:var(--gc-green)!important;}
hr{border-color:var(--gc-border)!important;}

/* Log rows */
.gc-log{font-family:'DM Mono',monospace;font-size:12px;padding:5px 10px;border-bottom:1px solid var(--gc-border);display:flex;gap:12px;}
.ll-ts{color:var(--gc-sage);white-space:nowrap;}
.ll-INFO{color:var(--gc-green-light);}
.ll-WARNING{color:var(--gc-amber);}
.ll-ERROR{color:var(--gc-ember);}
.ll-mod{color:var(--gc-mist);}

/* Empty state */
.gc-empty{text-align:center;padding:56px 20px;color:var(--gc-sage);}
.gc-empty-icon{font-size:52px;margin-bottom:12px;}
.gc-empty-text{font-size:16px;}

/* Completion celebration */
.gc-complete{background:linear-gradient(135deg,var(--gc-green-deep),var(--gc-green-dark));border:2px solid var(--gc-green);border-radius:16px;padding:26px 28px;text-align:center;}
.gc-complete-icon{font-size:56px;margin-bottom:10px;}
.gc-complete-title{font-size:22px;font-weight:700;color:var(--gc-white);margin-bottom:6px;}
.gc-complete-sub{font-size:14px;color:var(--gc-green-pale);}

/* Order status tag */
.status-tag{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:2px 9px;border-radius:20px;}
.st-pending{background:rgba(232,160,48,.15);color:var(--gc-amber);border:1px solid rgba(232,160,48,.4);}
.st-packed {background:rgba(74,124,89,.2);color:var(--gc-green-light);border:1px solid var(--gc-border-hi);}
.st-error  {background:rgba(217,79,61,.15);color:var(--gc-ember);border:1px solid rgba(217,79,61,.4);}
.st-inprog {background:rgba(74,180,212,.1);color:var(--gc-sky);border:1px solid rgba(74,180,212,.35);}
</style>
""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────────────────────────
DEFAULTS = {
    "manifest": None, "weather_data": None, "active_order": None, "alert": None,
    # Ingredient-by-ingredient packing state
    "pack_mode": False,           # True while stepping through items
    "pack_index": 0,              # current item index (0-based)
    "pack_checked": [],           # list of booleans per item
    "pack_weights": [],           # simulated scale weight per item
    "pack_complete": False,       # all items done
    "final_weight_result": None,  # overall weight check after completion
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Helpers ────────────────────────────────────────────────────────────────────
def wb_class(w):
    t = w.get("current_temp_f", 68)
    r = w.get("rain_chance_pct", 0)
    c = w.get("condition", "").lower()
    if t >= EXTREME_HEAT_F: return "wb-heat"
    if t >= HOT_F:          return "wb-heat"
    if t >= WARM_F:         return "wb-rain"   # amber/warm tone
    if t >= DANGER_ZONE_MAX_F: return "wb-rain"
    if t < FREEZE_RISK_F:   return "wb-freeze"
    if r > PRECIP_THRESHOLD or any(x in c for x in ["rain","snow","thunder"]): return "wb-rain"
    return "wb-clear"

def fcast_icon(cond, tf):
    c=cond.lower()
    if "snow" in c or tf<32: return "❄️"
    if "thunder" in c or "storm" in c: return "⛈️"
    if "rain" in c or "drizzle" in c: return "🌧️"
    if "cloud" in c: return "⛅"
    return "☀️"

def sim_weight(target_kg, jitter_pct=0.8):
    """Simulate a scale reading within ±jitter_pct% of target."""
    v = random.uniform(-jitter_pct/100, jitter_pct/100)
    return round(target_kg * (1 + v), 3)

def cat_icon(item):
    return CAT_ICON.get(item.get("category",""), "📦")

def all_items_for_packing(manifest):
    """Flatten meal items + packaging into one ordered list with bin_ids."""
    items = []
    for it in manifest.get("meal_items", []):
        items.append({**it, "bin_id": it.get("bin_id", "PICK"), "source": "meal"})
    for pk in manifest.get("packaging", []):
        items.append({**pk, "source": "packaging"})
    return items

def start_pack_mode(order_id):
    order = katana.get_order_by_id(order_id) or get_order(order_id)
    if not order:
        st.session_state.alert = f"Order **{order_id}** not found."
        return
    st.session_state.active_order   = order
    st.session_state.alert          = None
    st.session_state.pack_complete  = False
    st.session_state.final_weight_result = None

    w_data = weather.get_weather(order["zip_code"], order.get("delivery_date",""))
    st.session_state.weather_data   = w_data

    base_packing = katana.build_base_packing_list(order)
    manifest     = weather.build_manifest(order, base_packing, w_data)
    st.session_state.manifest       = manifest

    all_items = all_items_for_packing(manifest)
    n = len(all_items)
    st.session_state.pack_mode      = True
    st.session_state.pack_index     = 0
    st.session_state.pack_checked   = [False] * n
    st.session_state.pack_weights   = [0.0]  * n

def confirm_item(idx):
    """Mark current item as confirmed and advance."""
    items    = all_items_for_packing(st.session_state.manifest)
    item     = items[idx]
    target   = item.get("weight_kg", 0.1) * item.get("qty", 1)
    measured = sim_weight(target)
    st.session_state.pack_weights[idx]  = measured
    st.session_state.pack_checked[idx]  = True

    # flash the bin
    bin_id = item.get("bin_id", "BIN-UNK")
    qty    = item.get("qty", 1)
    p2l._send_signal(bin_id, qty)

    next_idx = idx + 1
    if next_idx >= len(items):
        st.session_state.pack_complete = True
        _finalize_pack()
    else:
        st.session_state.pack_index = next_idx

def _finalize_pack():
    manifest  = st.session_state.manifest
    order     = st.session_state.active_order
    w_data    = st.session_state.weather_data
    items     = all_items_for_packing(manifest)

    theo_kg   = manifest["weights"]["theoretical_total_kg"]
    actual_kg = round(sum(st.session_state.pack_weights), 3)
    manifest["weights"]["actual_kg"] = actual_kg
    diff_pct  = abs(theo_kg - actual_kg) / max(theo_kg, 0.001) * 100
    weight_ok = diff_pct <= 2.0
    manifest["weights"]["weight_ok"] = weight_ok

    if not weight_ok:
        p2l.flash_alert("BIN-ALL", color="RED")
        st.session_state.alert = (
            f"🚨 WEIGHT MISMATCH — LINE HALTED  |  "
            f"Expected {theo_kg:.3f} kg · Got {actual_kg:.3f} kg · Δ {diff_pct:.1f}%"
        )

    save_manifest(order["order_id"], manifest, w_data, theo_kg, actual_kg)
    update_order_status(order["order_id"], "packed" if weight_ok else "error")
    st.session_state.final_weight_result = {
        "theo_kg": theo_kg, "actual_kg": actual_kg,
        "diff_pct": diff_pct, "ok": weight_ok
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        f"<div style='margin-bottom:6px;'>{LOGO_HTML}</div>"
        f"<div style='font-size:10px;color:var(--gc-mist);letter-spacing:.08em;"
        f"text-transform:uppercase;padding-bottom:14px;border-bottom:1px solid var(--gc-border);'>"
        f"PackOps™ · Climate-Smart Fulfillment</div>",
        unsafe_allow_html=True
    )

    dot = "dot-live" if p2l.is_connected() else "dot-idle"
    st.markdown(
        f"<div class='gc-p2l-pill' style='margin-top:12px;'>"
        f"<span class='{dot}'>●</span>P2L &nbsp;·&nbsp; "
        f"<span style='color:var(--gc-mist)'>{p2l.get_protocol_label()}</span></div>",
        unsafe_allow_html=True
    )

    page = st.radio("nav", ["🌿 Pack Order", "📋 Order Queue", "➕ New Order", "📊 System Logs"],
                    label_visibility="collapsed")
    st.divider()

    all_orders = get_all_orders()
    pending = sum(1 for o in all_orders if o["status"] == "pending")
    packed  = sum(1 for o in all_orders if o["status"] == "packed")
    errors  = sum(1 for o in all_orders if o["status"] == "error")

    st.markdown(
        f'<div class="gc-met"><div class="gc-met-lbl">Awaiting Pack</div>'
        f'<div class="gc-met-val" style="color:var(--gc-amber)">{pending}</div></div>'
        f'<div class="gc-met"><div class="gc-met-lbl">Packed Today</div>'
        f'<div class="gc-met-val" style="color:var(--gc-green-light)">{packed}</div></div>'
        f'<div class="gc-met"><div class="gc-met-lbl">Needs Review</div>'
        f'<div class="gc-met-val" style="color:var(--gc-ember)">{errors}</div></div>',
        unsafe_allow_html=True
    )
    st.markdown(
        "<div style='margin-top:16px;font-size:9px;color:var(--gc-sage);text-align:center;"
        "letter-spacing:.07em;'>© 2026 GREEN CHEF · CERTIFIED ORGANIC</div>",
        unsafe_allow_html=True
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: PACK ORDER
# ═══════════════════════════════════════════════════════════════════════════════
if page == "🌿 Pack Order":
    st.markdown(
        "<div class='gc-title'>Pack Order</div>"
        "<div class='gc-sub'>Scan a barcode to begin — confirm each ingredient one by one</div>",
        unsafe_allow_html=True
    )

    # Alert
    if st.session_state.alert:
        if "WEIGHT MISMATCH" in str(st.session_state.alert):
            st.markdown(f'<div class="gc-alert">{st.session_state.alert}</div>', unsafe_allow_html=True)
        else:
            st.error(st.session_state.alert)
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Scan bar (only shown before pack mode starts) ─────────────────────────
    if not st.session_state.pack_mode:
        c1, c2 = st.columns([4, 1])
        with c1:
            scan_id = st.text_input("Order ID", placeholder="Scan barcode or type e.g. GC-2026-0501",
                                    label_visibility="collapsed", key="scan_input")
        with c2:
            if st.button("▶  Begin Pack", use_container_width=True):
                if scan_id.strip():
                    with st.spinner("Fetching weather & building manifest…"):
                        start_pack_mode(scan_id.strip().upper())
                    st.rerun()

        # Quick load chips
        demos = get_all_orders()[:5]
        if demos:
            st.markdown(
                "<div style='font-size:10px;letter-spacing:.1em;text-transform:uppercase;"
                "color:var(--gc-mist);margin-top:8px;margin-bottom:6px;'>Quick Load</div>",
                unsafe_allow_html=True
            )
            qcols = st.columns(min(len(demos), 5))
            for i, o in enumerate(demos):
                with qcols[i]:
                    lbl = f"🌿 {o['order_id']}"
                    if st.button(lbl, key=f"q_{o['order_id']}"):
                        with st.spinner(f"Loading {o['order_id']}…"):
                            start_pack_mode(o["order_id"])
                        st.rerun()

        st.markdown(
            "<div class='gc-empty'><div class='gc-empty-icon'>🌿</div>"
            "<div class='gc-empty-text'>Scan or select an order above to begin packing</div></div>",
            unsafe_allow_html=True
        )

    # ── ACTIVE PACKING MODE ───────────────────────────────────────────────────
    else:
        manifest  = st.session_state.manifest
        order     = st.session_state.active_order
        w_data    = st.session_state.weather_data
        all_items = all_items_for_packing(manifest)
        n         = len(all_items)
        idx       = st.session_state.pack_index
        checked   = st.session_state.pack_checked
        complete  = st.session_state.pack_complete

        col_left, col_right = st.columns([7, 3], gap="large")

        with col_left:
            # ── Weather Banner ─────────────────────────────────────────────────
            wc    = wb_class(w_data)
            icon  = weather.get_weather_icon(w_data)
            temp  = w_data["current_temp_f"]
            feels = w_data.get("feels_like_f", temp)
            city  = w_data.get("city", order["city"])
            rain  = w_data["rain_chance_pct"]
            tags  = []
            eff_temp = max(temp, max((f.get("high_f", temp) for f in w_data.get("forecast",[])), default=temp))
            tier  = get_safety_tier(eff_temp)
            if eff_temp >= EXTREME_HEAT_F:
                tags.append(f"🌡️ EXTREME HEAT — 3× XL Ice + Foil Liner (FDA §3-501.11)")
            elif eff_temp >= HOT_F:
                tags.append(f"☀️ HOT {eff_temp:.0f}°F — 2× XL Ice Pack + Foil Liner (FDA §3-501.11)")
            elif eff_temp >= WARM_F:
                tags.append(f"🌤 WARM {eff_temp:.0f}°F — 2× Standard Ice Pack required (FDA danger zone)")
            elif eff_temp >= DANGER_ZONE_MAX_F:
                tags.append(f"⚠️ {eff_temp:.0f}°F ≥ 40°F FDA threshold — 1× Ice Pack mandatory")
            elif eff_temp < FREEZE_RISK_F:
                tags.append(f"❄️ FREEZE RISK {eff_temp:.0f}°F — Insulation + Freeze Guard Liner")
            else:
                tags.append(f"✅ {eff_temp:.0f}°F — Below FDA danger zone · Insulation sleeve only")
            if rain > PRECIP_THRESHOLD:    tags.append(f"🌧️ {rain}% Precip — Waterproof Wrap Added")
            if w_data.get("is_fallback"):  tags.append("⚠️ Weather API Offline — Conservative Pack Applied")
            tags_html = "".join(f"<span class='wb-tag'>{t}</span>" for t in tags)

            st.markdown(f"""
            <div class="gc-wb {wc}">
              <div class="wb-icon">{icon}</div>
              <div class="wb-body">
                <div class="wb-loc">📍 {order['delivery_address']}, {order['city']}, {order['state']} {order['zip_code']}</div>
                <div class="wb-city">{city}</div>
                <div class="wb-temp">{temp:.0f}<span class="wb-sup">°F</span>
                  <span style="font-size:16px;font-weight:300;opacity:.65;"> · feels {feels:.0f}°F · {w_data['condition']}</span>
                </div>
                <div>{tags_html}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Forecast pills
            forecast = w_data.get("forecast", [])
            if forecast:
                pills = "<div class='fc-row'>"
                for day in forecast[:5]:
                    try:    label = datetime.strptime(day["date"],"%Y-%m-%d").strftime("%a %-d")
                    except: label = day.get("date","")
                    fi = fcast_icon(day.get("condition",""), day.get("high_f",68))
                    pills += (f"<div class='fc-pill'><div class='fp-date'>{label}</div>"
                              f"<div class='fp-icon'>{fi}</div>"
                              f"<div class='fp-temp'>{day.get('high_f','--'):.0f}°</div>"
                              f"<div class='fp-rain'>💧{day.get('rain_chance_pct',0)}%</div></div>")
                pills += "</div>"
                st.markdown(pills, unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)

            # ── FDA Food Safety Compliance Panel ───────────────────────────────
            tier_colors = {
                "heat":   ("#5c2000", "#f97316", "🌡️"),
                "warn":   ("#4a2e00", "#f59e0b", "⚠️"),
                "safe":   ("#1b3d22", "#4caf50", "✅"),
                "freeze": ("#0d2440", "#60a5fa", "❄️"),
            }
            bg, border, ticon = tier_colors.get(tier["color"], ("#1f3028","#4a7c59","ℹ️"))
            st.markdown(
                f"<div style='background:{bg};border:1px solid {border};border-radius:12px;"
                f"padding:13px 17px;margin-bottom:18px;'>"
                f"<div style='font-size:9px;font-weight:700;letter-spacing:.13em;"
                f"text-transform:uppercase;color:{border};margin-bottom:5px;'>"
                f"{ticon} &nbsp;FDA Food Safety Status · {tier['tier']}</div>"
                f"<div style='font-size:12px;color:var(--gc-text);line-height:1.6;'>"
                f"{tier['fda_note']}</div>"
                f"<div style='font-size:10px;color:var(--gc-mist);margin-top:5px;'>"
                f"Ref: FDA Food Code 2022 §3-501.11 · USDA FSIS Danger Zone 40°F – 140°F</div>"
                f"</div>",
                unsafe_allow_html=True
            )

            # ── PROGRESS BAR ──────────────────────────────────────────────────
            done_count = sum(checked)
            pct        = int(done_count / n * 100)
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;align-items:center;"
                f"margin-bottom:6px;font-size:12px;color:var(--gc-mist);'>"
                f"<span>Packing progress</span>"
                f"<span style='font-family:DM Mono,monospace;color:var(--gc-green-light);'>"
                f"{done_count} / {n} items confirmed</span></div>"
                f"<div class='pack-progress-bar-outer'>"
                f"<div class='pack-progress-bar-inner' style='width:{pct}%;'></div></div>",
                unsafe_allow_html=True
            )

            # ── COMPLETION STATE ───────────────────────────────────────────────
            if complete:
                wr = st.session_state.final_weight_result
                if wr and wr["ok"]:
                    st.markdown(
                        f"<div class='gc-complete'>"
                        f"<div class='gc-complete-icon'>✅</div>"
                        f"<div class='gc-complete-title'>Order Packed Successfully!</div>"
                        f"<div class='gc-complete-sub'>"
                        f"All {n} items confirmed · Total weight {wr['actual_kg']:.3f} kg · "
                        f"Variance {wr['diff_pct']:.1f}% ✓</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("📦 Pack Another Order"):
                    for k, v in DEFAULTS.items():
                        st.session_state[k] = v
                    st.rerun()

            # ── ACTIVE ITEM CARD ───────────────────────────────────────────────
            elif not complete:
                item    = all_items[idx]
                target  = round(item.get("weight_kg", 0.1) * item.get("qty", 1), 3)
                bin_id  = item.get("bin_id", "PICK")
                icon_i  = cat_icon(item)

                st.markdown(
                    f"<div class='ing-step-num'>STEP {idx+1} OF {n}</div>"
                    f"<div class='ing-card-active'>"
                    f"<div class='ing-row'>"
                    f"  <div class='ing-icon'>{icon_i}</div>"
                    f"  <div style='flex:1;'>"
                    f"    <div class='ing-name'>{item['name']}</div>"
                    f"    <div class='ing-meta'>{item.get('category','').capitalize()} "
                    f"· {item.get('unit','piece')}</div>"
                    f"  </div>"
                    f"  <div style='display:flex;flex-direction:column;align-items:flex-end;gap:6px;'>"
                    f"    <span class='ing-qty-badge'>× {item.get('qty',1)}</span>"
                    f"    <span class='ing-bin-badge'>{bin_id}</span>"
                    f"  </div>"
                    f"</div>"
                    f"<div class='scale-readout'>"
                    f"  <div class='scale-lbl'>🔴 Place on Scale — Target Weight</div>"
                    f"  <div class='scale-val scale-ok'>{target:.3f} <span class='scale-unit'>kg</span></div>"
                    f"  <div style='font-size:11px;color:var(--gc-mist);margin-top:4px;'>Tolerance ±2%  ·  "
                    f"{target*0.98:.3f} – {target*1.02:.3f} kg acceptable</div>"
                    f"</div>"
                    f"<div class='p2l-flash'>"
                    f"  <span>💡 BIN {bin_id}</span>"
                    f"  <span class='p2l-dots'>{'●' * min(item.get('qty',1),6)}</span>"
                    f"  <span style='color:var(--gc-mist);font-size:11px;'>Flash × {item.get('qty',1)}</span>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

                c_btn1, c_btn2 = st.columns([2, 1])
                with c_btn1:
                    if st.button(f"✅  Confirm — {item['name']}", use_container_width=True, key=f"confirm_{idx}"):
                        confirm_item(idx)
                        st.rerun()
                with c_btn2:
                    if st.button("⏭ Skip Item", use_container_width=True, key=f"skip_{idx}"):
                        st.session_state.pack_checked[idx] = False
                        nxt = idx + 1
                        if nxt >= n:
                            st.session_state.pack_complete = True
                            _finalize_pack()
                        else:
                            st.session_state.pack_index = nxt
                        st.rerun()

            # ── DONE & UPCOMING ITEMS ─────────────────────────────────────────
            st.markdown("<br><div class='gc-card-hdr'>All Items</div>", unsafe_allow_html=True)
            for i, item in enumerate(all_items):
                icon_i = cat_icon(item)
                wt     = round(item.get("weight_kg",0.1) * item.get("qty",1), 3)
                tier   = item.get("tier", item.get("source", ""))
                is_t1  = "tier1" in tier
                is_t2  = tier == "tier2"
                type_label = ("🧊 Tier 1" if is_t1 else ("🌱 Tier 2" if is_t2 else ""))
                tcolor     = "var(--gc-amber)" if is_t1 else ("var(--gc-green-light)" if is_t2 else "")

                if checked[i]:
                    meas = st.session_state.pack_weights[i]
                    badge_html = (f"&nbsp;<span style='font-size:10px;color:{tcolor};'>{type_label}</span>"
                                  if type_label else "")
                    st.markdown(
                        f"<div class='ing-card-done'><div class='ing-row'>"
                        f"<div class='ing-icon-sm'>{icon_i}</div>"
                        f"<div style='flex:1;'>"
                        f"<div class='ing-name-sm'>{item['name']}{badge_html}</div>"
                        f"<div class='ing-meta'>{item.get('bin_id','—')} · measured {meas:.3f} kg</div>"
                        f"</div>"
                        f"<div class='ing-done-tick'>✅</div>"
                        f"</div></div>",
                        unsafe_allow_html=True
                    )
                elif i == idx and not complete:
                    pass  # shown above as active card
                else:
                    note = item.get("note", item.get("fda_rule", ""))
                    badge_html = (f"&nbsp;<span style='font-size:10px;color:{tcolor};opacity:.8;'>{type_label}</span>"
                                  if type_label else "")
                    st.markdown(
                        f"<div class='ing-card-upcoming'><div class='ing-row'>"
                        f"<div class='ing-icon-sm' style='opacity:.5;'>{icon_i}</div>"
                        f"<div style='flex:1;'>"
                        f"<div class='ing-name-sm' style='opacity:.7;'>{item['name']}{badge_html}</div>"
                        f"<div class='ing-meta'>{item.get('bin_id','—')} · {wt:.3f} kg expected</div>"
                        f"{'<div class=\"ci-transit-note\">' + note[:80] + ('…' if len(note)>80 else '') + '</div>' if note else ''}"
                        f"</div>"
                        f"<span class='ing-qty-badge' style='opacity:.5;'>× {item.get('qty',1)}</span>"
                        f"</div></div>",
                        unsafe_allow_html=True
                    )

        with col_right:
            # Order card
            st.markdown(
                f"<div class='gc-card'>"
                f"<div class='gc-card-hdr'>Order Details</div>"
                f"<div style='font-size:20px;font-weight:700;letter-spacing:-.3px;margin-bottom:2px;'>"
                f"{order['order_id']}</div>"
                f"<div style='font-size:15px;font-weight:500;margin-bottom:3px;'>{order['customer_name']}</div>"
                f"<div style='font-size:12px;color:var(--gc-mist);line-height:1.6;'>"
                f"{order['delivery_address']}<br>{order['city']}, {order['state']} {order['zip_code']}</div>"
                f"<div style='margin-top:10px;font-size:13px;color:var(--gc-amber);font-weight:500;'>"
                f"📅 Delivery: {order.get('delivery_date','')}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

            # Final weight card (after completion)
            wr = st.session_state.final_weight_result
            if wr:
                ok     = wr["ok"]
                wclass = "gwb-ok" if ok else "gwb-alert"
                vcolor = "var(--gc-green-light)" if ok else "var(--gc-ember)"
                st.markdown(
                    f"<div class='gc-wb-box {wclass}'>"
                    f"<div class='gwb-lbl'>{'✅ Weight Check · PASS' if ok else '🚨 Weight Check · FAIL'}</div>"
                    f"<div class='gwb-val' style='color:{vcolor};'>{wr['actual_kg']:.3f} kg</div>"
                    f"<div class='gwb-sub'>Expected {wr['theo_kg']:.3f} kg · Δ {wr['diff_pct']:.1f}%</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                st.markdown("<br>", unsafe_allow_html=True)

            # Packaging summary card
            st.markdown("<div class='gc-card-hdr'>Packaging Summary</div>", unsafe_allow_html=True)
            pkg_groups = {
                "📦 Base (unchanged)":       [p for p in manifest.get("packaging",[]) if p.get("tier") == "base"],
                "🧊 Tier 1 — Nutri-Ice":     [p for p in manifest.get("packaging",[]) if p.get("tier") in ("tier1","tier1-fda")],
                "🌱 Tier 2 — Paper Bags":    [p for p in manifest.get("packaging",[]) if p.get("tier") == "tier2"],
            }
            for group_label, pkg_list in pkg_groups.items():
                if not pkg_list:
                    continue
                st.markdown(
                    f"<div style='font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;"
                    f"color:var(--gc-mist);margin:10px 0 5px;'>{group_label}</div>",
                    unsafe_allow_html=True
                )
                for pkg in pkg_list:
                    tier   = pkg.get("tier", "")
                    is_t1  = "tier1" in tier
                    is_t2  = tier == "tier2"
                    color  = "var(--gc-amber)" if is_t1 else ("var(--gc-green-light)" if is_t2 else "var(--gc-mist)")
                    note   = pkg.get("note", pkg.get("fda_rule", ""))
                    st.markdown(
                        f"<div style='padding:7px 0;border-bottom:1px solid var(--gc-border);font-size:13px;'>"
                        f"<div style='display:flex;align-items:center;gap:8px;'>"
                        f"<span style='font-family:DM Mono,monospace;font-size:10px;color:var(--gc-mist);'>{pkg.get('bin_id','—')}</span>"
                        f"<span style='flex:1;'>📦 {pkg['name']}</span>"
                        f"<span style='font-family:DM Mono,monospace;font-size:12px;color:{color};'>×{pkg['qty']}</span>"
                        f"</div>"
                        f"{'<div style=\"font-size:11px;color:var(--gc-mist);margin-top:2px;font-style:italic;\">' + note[:80] + ('…' if len(note)>80 else '') + '</div>' if note else ''}"
                        f"</div>",
                        unsafe_allow_html=True
                    )

            # Abort button
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✕  Abort & Rescan", use_container_width=True):
                for k, v in DEFAULTS.items():
                    st.session_state[k] = v
                st.rerun()

            with st.expander("🗂️ Manifest JSON"):
                st.code(json.dumps(manifest, indent=2), language="json")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: ORDER QUEUE
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Order Queue":
    st.markdown(
        "<div class='gc-title'>Order Queue</div>"
        "<div class='gc-sub'>May 2026 · All Green Chef orders synced from Katana ERP</div>",
        unsafe_allow_html=True
    )
    all_orders = get_all_orders()
    if not all_orders:
        st.markdown("<div class='gc-empty'><div class='gc-empty-icon'>📋</div>"
                    "<div class='gc-empty-text'>No orders found.</div></div>", unsafe_allow_html=True)
    else:
        sf = st.selectbox("Filter", ["All", "pending", "packed", "error"])
        filtered = all_orders if sf == "All" else [o for o in all_orders if o["status"] == sf]

        for o in filtered:
            smap = {"pending":("st-pending","🟡"),"packed":("st-packed","✅"),"error":("st-error","🔴")}
            scls, sico = smap.get(o["status"],("st-pending","⚪"))
            with st.expander(f"{sico}  {o['order_id']}  ·  {o['customer_name']}  ·  "
                             f"{o['city']}, {o['state']}  ·  📅 {o['delivery_date']}"):
                c1,c2,c3 = st.columns(3)
                with c1:
                    st.markdown(f"**ZIP** &nbsp; `{o['zip_code']}`")
                    st.markdown(f"**Items** &nbsp; {len(o['items'])}")
                with c2:
                    st.markdown(
                        f"**Status** &nbsp; <span class='status-tag {scls}'>{o['status'].upper()}</span>",
                        unsafe_allow_html=True
                    )
                with c3:
                    if st.button("🌿 Pack Now", key=f"pack_{o['order_id']}"):
                        with st.spinner("Loading…"):
                            start_pack_mode(o["order_id"])
                        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: NEW ORDER
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "➕ New Order":
    st.markdown(
        "<div class='gc-title'>New Order</div>"
        "<div class='gc-sub'>Register a manual order — climate packaging applied at pack time</div>",
        unsafe_allow_html=True
    )
    with st.form("new_order_form", clear_on_submit=True):
        c1,c2 = st.columns(2)
        with c1:
            order_id      = st.text_input("Order ID *", placeholder="GC-2026-0510")
            customer_name = st.text_input("Customer Name *", placeholder="Alex Johnson")
            delivery_date = st.date_input("Delivery Date *", value=date(2026,5,20))
        with c2:
            address  = st.text_input("Street Address *", placeholder="123 Elm St")
            city     = st.text_input("City *", placeholder="Denver")
            cs1,cs2  = st.columns(2)
            with cs1: state    = st.text_input("State", placeholder="CO", max_chars=2)
            with cs2: zip_code = st.text_input("ZIP *", placeholder="80202")

        st.divider()
        st.markdown("**Meal Kit Ingredients**")
        num_items = st.number_input("Number of items", min_value=1, max_value=15, value=4)
        items = []
        for i in range(int(num_items)):
            ic1,ic2,ic3,ic4 = st.columns([4,1,1,2])
            with ic1: iname = st.text_input(f"Item {i+1}", key=f"in_{i}", placeholder="Chicken Thigh")
            with ic2: iqty  = st.number_input("Qty",   min_value=1, max_value=20, key=f"iq_{i}", value=2)
            with ic3: iwt   = st.number_input("kg",    min_value=0.005, max_value=5.0, key=f"iw_{i}", value=0.25, step=0.005)
            with ic4: icat  = st.selectbox("Category", ["protein","produce","herb","dairy","grain","pantry","sauce"], key=f"ic_{i}")
            if iname:
                items.append({"sku":f"GC-MAN-{i+1:03d}","name":iname,"qty":iqty,"weight_kg":iwt,"category":icat,"unit":"piece"})

        submitted = st.form_submit_button("🌿 Create Order", use_container_width=True)

    if submitted:
        if not all([order_id, customer_name, address, city, zip_code]):
            st.error("Please fill in all required fields (*)")
        elif not items:
            st.error("Add at least one ingredient.")
        else:
            add_manual_order({
                "order_id":order_id.strip().upper(),"customer_name":customer_name.strip(),
                "delivery_address":address.strip(),"city":city.strip(),
                "state":state.strip().upper(),"zip_code":zip_code.strip(),
                "delivery_date":str(delivery_date),"items":items,"status":"pending",
            })
            st.success(f"✅ Order **{order_id.upper()}** created — go to Pack Order to process it.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: SYSTEM LOGS
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📊 System Logs":
    st.markdown(
        "<div class='gc-title'>System Logs</div>"
        "<div class='gc-sub'>Real-time PackOps™ event stream</div>",
        unsafe_allow_html=True
    )
    logs = get_recent_logs(150)
    lf   = st.multiselect("Levels", ["INFO","WARNING","ERROR"], default=["INFO","WARNING","ERROR"])
    logs = [l for l in logs if l["level"] in lf]
    st.markdown(f"<div style='font-size:11px;color:var(--gc-mist);margin-bottom:8px;'>"
                f"{len(logs)} entries</div>", unsafe_allow_html=True)
    for e in logs:
        lv = e["level"]
        st.markdown(
            f"<div class='gc-log'>"
            f"<span class='ll-ts'>{e['logged_at'][:19]}</span>"
            f"<span class='ll-{lv}'>{lv}</span>"
            f"<span class='ll-mod'>[{e['module']}]</span>"
            f"<span>{e['message']}</span></div>",
            unsafe_allow_html=True
        )
    if not logs:
        st.markdown("<div class='gc-empty'><div class='gc-empty-icon'>📊</div>"
                    "<div class='gc-empty-text'>No entries match this filter.</div></div>",
                    unsafe_allow_html=True)
    if st.button("🔄 Refresh"):
        st.rerun()
