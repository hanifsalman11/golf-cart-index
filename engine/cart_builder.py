import os
import json
import re
import time
import math
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

# ==========================================
# ENVIRONMENT CONFIGURATION
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://hanifsalman11.github.io/golf-cart-index").rstrip("/")
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7").strip()
CUSTOM_CART = os.environ.get("CUSTOM_CART", "").strip()
PAGES_PER_RUN = int(os.environ.get("PAGES_PER_RUN", "3"))

DOCS_DIR = "docs"
DATA_DIR = "data"
PUBLISHED_FILE = os.path.join(DATA_DIR, "published_carts.json")
MONETIZATION_FILE = os.path.join(DATA_DIR, "monetization.json")

_CACHED_MODELS = None

# Format: (Cart Model / Upgrade Scenario, Nominal Volts, Battery Ah, Controller Peak Amps, Motor RPM, Tire OD Inches, Axle Ratio)
SEED_CARTS = [
    ("Club Car Precedent 48V 105Ah LiFePO4 Conversion", 48, 105, 350, 4200, 20.0, 12.44),
    ("Club Car DS 48V 100Ah Drop-In Lithium Battery Upgrade", 48, 100, 300, 4000, 20.0, 12.28),
    ("Club Car DS 36V to 48V Lithium & High-Speed Motor Conversion", 48, 105, 400, 4800, 22.0, 12.28),
    ("Club Car Onward & Tempo 48V Lifted (23\" Tires) 105Ah Setup", 48, 105, 500, 4900, 23.0, 12.44),
    ("EZGO TXT 48V 105Ah LiFePO4 Lithium Battery Conversion", 48, 105, 350, 4100, 20.0, 12.44),
    ("EZGO TXT 36V 100Ah LiFePO4 Drop-In Battery Conversion", 36, 100, 300, 3800, 18.5, 12.44),
    ("EZGO TXT 36V to 48V Navitas 440A / 600A AC Conversion", 48, 105, 600, 5400, 22.0, 12.44),
    ("EZGO RXV 48V AC-Drive 105Ah LiFePO4 Conversion (200A BMS)", 48, 105, 450, 5200, 20.5, 12.44),
    ("EZGO Marathon 36V 100Ah Lithium & Solenoid Upgrade", 36, 100, 300, 3700, 18.0, 12.28),
    ("Yamaha Drive (G29) 48V 105Ah LiFePO4 Lithium Conversion", 48, 105, 350, 4200, 20.0, 12.49),
    ("Yamaha Drive2 48V AC-Drive 105Ah LiFePO4 Battery Setup", 48, 105, 400, 4800, 20.5, 12.49),
    ("Yamaha G19 & G22 48V 100Ah LiFePO4 Drop-In Conversion", 48, 100, 300, 4000, 20.0, 12.49),
    ("Icon i20 / i40 / i60 48V 105Ah LiFePO4 Battery Upgrade", 48, 105, 450, 5000, 21.5, 12.30),
    ("Vatrer 48V 105Ah LiFePO4 (200A BMS) Range & Speed Sizing", 48, 105, 400, 4500, 20.5, 12.44),
    ("Chins / Lossigy 48V 100Ah LiFePO4 Golf Cart Battery Sizing", 48, 100, 350, 4200, 20.0, 12.44),
    ("Eco-Worthy & LiTime 48V 100Ah Golf Cart Lithium Sizing", 48, 100, 350, 4200, 20.0, 12.44),
    ("Epoch & Allied 48V 105Ah High-Output 250A BMS Cart Setup", 48, 105, 600, 5400, 23.0, 12.44),
    ("Navitas 600A 5kW AC Conversion Kit Battery & BMS Sizing", 48, 105, 600, 5800, 23.0, 12.44),
    ("Navitas 440A DC-to-AC Golf Cart Controller & BMS Sizing", 48, 105, 440, 5000, 22.0, 12.44),
    ("Alltrax XCT-400 & SR-48400 (400A) Controller Cable & BMS", 48, 105, 400, 4600, 22.0, 12.44),
    ("Curtis 1268 / 1510SepEx 400A–500A Controller Upgrade", 48, 105, 500, 4800, 22.0, 12.44),
    ("72V 100Ah LiFePO4 High-Speed Lifted Street-Legal LSV Cart", 72, 100, 600, 6200, 23.0, 10.35),
    ("6-Passenger Stretch Limo Golf Cart 48V 160Ah / 200Ah Setup", 48, 160, 500, 4500, 22.0, 12.44),
    ("Hunting Buggy 4x4 Lifted Golf Cart (23\" Mud Tires) 48V", 48, 105, 550, 4600, 23.0, 12.44),
    ("23-Inch vs 20-Inch vs 18-Inch Golf Cart Tire Speed & Torque", 48, 105, 400, 4500, 23.0, 12.44),
    ("8:1 High-Speed Gears vs 12.44:1 Stock Axle Ratio MPH", 48, 105, 450, 4500, 22.0, 8.00),
    ("6x 8V Trojan T-875 Lead-Acid to Single 48V 105Ah LiFePO4", 48, 105, 350, 4200, 20.0, 12.44),
    ("8x 6V Trojan T-105 Lead-Acid to Single 48V 105Ah LiFePO4", 48, 105, 350, 4200, 20.0, 12.44),
    ("6x 6V Lead-Acid to Single 36V 105Ah LiFePO4 Conversion", 36, 105, 300, 3800, 20.0, 12.44),
    ("48V-to-12V 30A Voltage Reducer & 400A Heavy-Duty Solenoid", 48, 105, 400, 4500, 21.0, 12.44)
]


def load_json(filepath, default):
    """Self-healing JSON loader: otomatis pulih jika file korup atau kosong."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, type(default)) else default
        except Exception as e:
            print(f"[SELF-HEAL] Recovering {filepath} due to read notice: {e}")
    return default


def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")


def safe_float(val, default=48.0):
    try:
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return float(cleaned) if cleaned else float(default)
    except Exception:
        return float(default)


def build_amazon_url(search_keywords, mon_cfg):
    domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")
    encoded_q = urllib.parse.quote_plus(search_keywords)
    return f"https://{domain}/s?k={encoded_q}&tag={tag}"


def get_active_gemini_model(api_key):
    """
    LAPIS 1: Mesin Pemindai Versi Otomatis berbasis Regex tanpa angka versi manual.
    Otomatis mendeteksi model Gemini Flash STABIL generasi tertinggi lintas tahun.
    """
    global _CACHED_MODELS
    if _CACHED_MODELS is not None:
        return _CACHED_MODELS

    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        req = urllib.request.Request(list_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            scored_models = []

            for m in data.get("models", []):
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])

                if "generateContent" not in methods or "flash" not in name.lower():
                    continue

                if any(bad in name.lower() for bad in [
                    "preview", "exp", "thinking", "image", "tts", "audio", "vision", "8b"
                ]):
                    continue

                ver_match = re.search(r"gemini-(\d+(?:\.\d+)?)-flash", name.lower())
                if ver_match:
                    ver_num = float(ver_match.group(1))
                    if name.lower() == f"gemini-{ver_match.group(1)}-flash":
                        tier_score = 2
                    elif name.lower() == f"gemini-{ver_match.group(1)}-flash-lite":
                        tier_score = 1
                    else:
                        tier_score = 0
                    scored_models.append((ver_num, tier_score, name))
                elif name.lower() == "gemini-flash-latest":
                    scored_models.append((0.1, 0, name))

            if scored_models:
                scored_models.sort(key=lambda x: (x[0], x[1]), reverse=True)
                _CACHED_MODELS = [item[2] for item in scored_models[:2]]
                print(f"[GEMINI] Future-proof active models locked: {_CACHED_MODELS}")
                return _CACHED_MODELS
    except Exception as e:
        print(f"[WARN] Dynamic model discovery notice: {e}")

    _CACHED_MODELS = ["gemini-flash-latest"]
    return _CACHED_MODELS


def discover_google_cart_queries(published_slugs):
    """
    LAPIS 4: 3-Tier Infinite Keyword Supply:
    Tier A: Seed List -> Tier B: Google Suggest US -> Tier C: Combinatorial Cart × Battery × Tire Permutator.
    """
    discovered = []
    seeds = [
        "golf cart lithium battery ",
        "48v 105ah lifepo4 golf cart ",
        "club car precedent lithium ",
        "ezgo txt lithium conversion "
    ]
    for seed in seeds:
        try:
            url = f"http://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=us&q={urllib.parse.quote(seed)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for suggestion in data[1]:
                    cleaned = suggestion.lower()
                    for pref in seeds:
                        if "calculator" in pref:
                            cleaned = cleaned.replace(pref, "")
                    cleaned = re.sub(
                        r"\b(calculator|size|sizing|chart|manual|review|reddit|for)\b",
                        "",
                        cleaned
                    ).strip()
                    if 5 <= len(cleaned) <= 42:
                        v_sys = 36 if "36v" in cleaned else (72 if "72v" in cleaned else 48)
                        ah_m = re.search(r"\b(60|100|105|150|160|200)\s*ah\b", cleaned)
                        ah_v = int(ah_m.group(1)) if ah_m else 105
                        discovered.append((cleaned.title(), v_sys, ah_v, 400, 4400, 20.5, 12.44))
        except Exception as e:
            print(f"[WARN] Google Suggest notice: {e}")

    # Tier C Fallback: Combinatorial Permutator (Anti-Habis Lintas Tahun)
    chassis_list = [
        ("Club Car Precedent", 12.44),
        ("Club Car DS", 12.28),
        ("Club Car Onward", 12.44),
        ("EZGO TXT", 12.44),
        ("EZGO RXV", 12.44),
        ("Yamaha Drive G29", 12.49),
        ("Yamaha Drive2", 12.49)
    ]
    power_configs = [
        (36, 105, 300, 3800, "36V 105Ah LiFePO4 (300A Controller)"),
        (48, 100, 350, 4300, "48V 100Ah LiFePO4 (350A Controller)"),
        (48, 105, 440, 5000, "48V 105Ah LiFePO4 (440A AC Controller)"),
        (48, 105, 600, 5600, "48V 105Ah LiFePO4 (600A Navitas AC)"),
        (72, 100, 600, 6000, "72V 100Ah LiFePO4 High-Speed Setup")
    ]
    tires = [18.5, 20.5, 22.0, 23.0]
    for c_name, ax_rat in chassis_list:
        for v_nom, ah_cap, ctrl_a, m_rpm, p_desc in power_configs:
            for t_od in tires:
                combo_title = f"{c_name} {p_desc} w/ {t_od:g}\" Tires"
                test_slug = slugify(f"{combo_title}-range-mph-calculator")
                if test_slug not in published_slugs:
                    discovered.append((combo_title, v_nom, ah_cap, ctrl_a, m_rpm, t_od, ax_rat))
                    if len(discovered) >= 25:
                        return discovered
    return discovered


def build_deterministic_cart_data(cart_tuple):
    """
    LAPIS 3: Mesin Fisika Drivetrain Golf Cart, BMS Surge Cut-Off & Pengurangan Beban LiFePO4 (100% Bebas Gagal).
    """
    model_name, nom_volts, batt_ah, ctrl_peak_amps, motor_rpm, tire_od_in, axle_ratio = cart_tuple

    # 1. Tegangan Kerja Riil LiFePO4 (12S = 38.4V, 16S = 51.2V, 24S = 76.8V) & Total Energi (Wh):
    real_lfp_volts = 38.4 if nom_volts == 36 else (76.8 if nom_volts == 72 else 51.2)
    total_energy_wh = int(round(real_lfp_volts * batt_ah))
    usable_lfp_wh = int(round(total_energy_wh * 0.95))

    # 2. Kecepatan Puncak (Top Speed MPH):
    # MPH = (Motor_RPM * Tire_Diameter_Inches) / (Axle_Gear_Ratio * 336)
    top_speed_mph = round((motor_rpm * tire_od_in) / (axle_ratio * 336.0), 1)

    # 3. Penghematan Berat (Weight Shedding: 6x 8V Lead-Acid = ~385 lbs vs Single LiFePO4 = ~98 lbs -> Hemat 287 lbs!)
    weight_saved_lbs = 245 if nom_volts == 36 else 285

    # 4. Konsumsi Energi (Wh per Mile) & Jarak Tempuh (Miles Per Charge):
    # Rata-rata 48V cart membutuhkan ~105 Wh/mile setelah diet 285 lbs (atau ~125 Wh/mile jika pakai ban 23" lifted)
    wh_per_mile = 122.0 if tire_od_in >= 22.0 else 104.0
    estimated_range_miles = int(round(usable_lfp_wh / wh_per_mile))
    old_lead_acid_miles = int(round(estimated_range_miles * 0.44))

    # 5. Spesifikasi BMS Continuous / Peak (30s) & Kabel Tembaga:
    min_bms_cont_amps = 150 if ctrl_peak_amps <= 300 else (200 if ctrl_peak_amps <= 450 else 250)
    min_bms_peak_amps = max(350, int(round(ctrl_peak_amps * 1.15, -1)))
    cable_awg = "2 AWG Pure Copper (OFC)" if ctrl_peak_amps >= 350 else "4 AWG Pure Copper (OFC)"

    return {
        "cart_name": model_name,
        "seo_title": f"{model_name} Range, BMS Amps & MPH Speed Calculator (2026)",
        "meta_description": f"Calculate exact LiFePO4 driving range ({estimated_range_miles} miles on {total_energy_wh:,} Wh), top speed ({top_speed_mph} MPH w/ {tire_od_in:g}\" tires), {min_bms_cont_amps}A/{min_bms_peak_amps}A BMS sizing, and {weight_saved_lbs}-lb weight drop for {model_name}.",
        "specs": {
            "nominal_voltage": nom_volts,
            "operating_lfp_voltage": real_lfp_volts,
            "battery_capacity_ah": batt_ah,
            "total_energy_wh": total_energy_wh,
            "controller_peak_amps": ctrl_peak_amps,
            "min_bms_continuous_amps": min_bms_cont_amps,
            "min_bms_peak_amps": min_bms_peak_amps,
            "motor_rpm": motor_rpm,
            "tire_diameter_in": tire_od_in,
            "axle_gear_ratio": axle_ratio,
            "top_speed_mph": top_speed_mph,
            "estimated_range_miles": estimated_range_miles,
            "lead_acid_range_miles": old_lead_acid_miles,
            "weight_shed_lbs": weight_saved_lbs,
            "recommended_cable_awg": cable_awg
        },
        "drivetrain_verdict": f"Upgrading {model_name} to a single metal-case {nom_volts}V ({real_lfp_volts}V nominal) {batt_ah}Ah LiFePO4 battery pack provides {total_energy_wh:,} Wh of energy while shedding ~{weight_saved_lbs} lbs of lead-acid dead weight—boosting real-world driving range from {old_lead_acid_miles} miles to ~{estimated_range_miles} miles per charge. Spinning at {motor_rpm:,} RPM through a {axle_ratio}:1 differential with {tire_od_in:g}-inch tires yields a top speed of {top_speed_mph} MPH. To prevent BMS over-current cutouts during steep hill climbs or hard acceleration on a {ctrl_peak_amps}A controller, select a battery rated for at least {min_bms_cont_amps}A continuous ({min_bms_peak_amps}A peak surge) wired with {cable_awg}.",
        "hardware_bundle": [
            {
                "badge": f"{nom_volts}V {batt_ah}Ah LiFePO4 Kit",
                "title": f"{nom_volts}V ({real_lfp_volts}V) {batt_ah}Ah Metal-Case Golf Cart LiFePO4 Battery ({min_bms_cont_amps}A BMS) + Charger & LCD",
                "price_range": "$749 - $1,599",
                "amazon_query": f"{nom_volts}V {batt_ah}Ah 100Ah LiFePO4 Golf Cart Battery Kit Charger 200A BMS",
                "cart_note": f"Replaces 6 to 8 heavy lead-acid batteries with a single 98-lb unit delivering {estimated_range_miles} miles of zero-maintenance range."
            },
            {
                "badge": f"{ctrl_peak_amps}A Controller & Solenoid",
                "title": f"High-Torque {nom_volts}V {ctrl_peak_amps}A Speed Controller + 400A Silver-Alloy Continuous Solenoid Contactor",
                "price_range": "$159 - $799",
                "amazon_query": f"{nom_volts}V Golf Cart Speed Controller 400A Solenoid Contactor",
                "cart_note": f"Stock 150A solenoids weld their contacts shut under lithium inrush currents; a 400A silver solenoid prevents runaway carts."
            },
            {
                "badge": f"{nom_volts}V-to-12V 30A Reducer",
                "title": f"Waterproof IP68 {nom_volts}V-to-12V 30A (360W) Step-Down Voltage Converter + {cable_awg.split()[0]} AWG Copper Cables",
                "price_range": "$48 - $109",
                "amazon_query": f"{nom_volts}V to 12V 30A Golf Cart Voltage Reducer Converter 2 AWG Battery Cables",
                "cart_note": "Powers 12V LED headlights, turn signals, underglow, and Bluetooth soundbars safely from the main lithium pack."
            },
            {
                "badge": f"Lift Kit & {tire_od_in:g}\" Tires",
                "title": f"4\"–6\" Heavy-Duty A-Arm Golf Cart Lift Kit + {tire_od_in:g}\" All-Terrain Tire/Wheel Set & Rear Leaf Springs",
                "price_range": "$149 - $649",
                "amazon_query": f"Golf Cart Lift Kit All Terrain Wheels Tires Heavy Duty Leaf Springs",
                "cart_note": f"Stepping up to {tire_od_in:g}-inch tires increases ground clearance and raises top speed to {top_speed_mph} MPH."
            }
        ],
        "conversion_checklist": [
            f"Never tap 12V accessories off a single battery post (impossible on a single {nom_volts}V monoblock LiFePO4 battery anyway!): install a dedicated {nom_volts}V-to-12V 30A Step-Down Voltage Reducer wired to the main positive and negative busbars.",
            f"Match your Battery BMS Continuous & Peak Rating ({min_bms_cont_amps}A continuous / {min_bms_peak_amps}A 30s peak) to your motor controller ({ctrl_peak_amps}A): if you install a 100A-BMS budget battery on a 440A–600A controller with {tire_od_in:g}\" tires, the BMS will trip and shut the cart off mid-hill.",
            "Disconnect or bypass the factory On-Board Computer (OBC) on 1995–2014 Club Car DS and Precedent carts when installing a lithium charger so the cart's sense wire recognizes the new charger.",
            "Install a 25W 10-Ohm Pre-Charge Resistor across the main 400A solenoid (or Tow/Run switch) so closing the switch into the controller's large capacitors never triggers a short-circuit protection trip in your LiFePO4 BMS."
        ],
        "faqs": [
            {
                "q": f"How far will a {nom_volts}V {batt_ah}Ah LiFePO4 battery run {model_name}?",
                "a": f"A {nom_volts}V ({real_lfp_volts}V true operating voltage) {batt_ah}Ah LiFePO4 pack stores {total_energy_wh:,} Watt-hours. Because converting from lead-acid sheds ~{weight_saved_lbs} lbs and eliminates Peukert voltage sag, it delivers ~{estimated_range_miles} miles per charge (compared to {old_lead_acid_miles} miles on aging lead-acid batteries)."
            },
            {
                "q": f"How fast will {model_name} go with {tire_od_in:g}-inch tires at {motor_rpm:,} RPM?",
                "a": f"Using the drivetrain formula ($\\text{{MPH}} = [\\text{{Motor RPM}} \\times \\text{{Tire OD}}] \\div [\\text{{Axle Ratio}} \\times 336]$), {motor_rpm:,} RPM × {tire_od_in:g}\" tires ÷ ({axle_ratio} × 336) equals {top_speed_mph} MPH. Plus, LiFePO4 sits at {real_lfp_volts}V instead of sagging to 44V under load, keeping motor RPM 7% higher up hills."
            },
            {
                "q": f"What BMS amp rating do I need for a {ctrl_peak_amps}A controller on {model_name}?",
                "a": f"Your LiFePO4 Battery Management System (BMS) must have a Continuous Discharge rating of at least {min_bms_cont_amps}A and a 3-to-30 second Peak Surge rating of {min_bms_peak_amps}A+ so steep hills or heavy 4-passenger loads never trip over-current protection."
            }
        ]
    }


def generate_cart_data(cart_tuple):
    """
    LAPIS 2: Memanggil model Gemini stabil dengan proteksi Cooldown HTTP 429 & Fallback Otomatis.
    """
    if not GEMINI_API_KEY:
        return build_deterministic_cart_data(cart_tuple)

    model_name, nom_volts, batt_ah, ctrl_peak_amps, motor_rpm, tire_od_in, axle_ratio = cart_tuple
    det_fallback = build_deterministic_cart_data(cart_tuple)
    sp = det_fallback["specs"]

    prompt = f"""
You are a Master Electric Vehicle (EV) Golf Cart Drivetrain Engineer & LiFePO4 Battery Systems Architect. Create an accurate 2026 golf cart lithium battery range, BMS vs controller amp matching, weight-loss gain, and tire/gear MPH speed guide for: "{model_name}".
Baseline specs: System={nom_volts}V ({sp['operating_lfp_voltage']}V LFP) {batt_ah}Ah ({sp['total_energy_wh']} Wh), Range={sp['estimated_range_miles']} miles (-{sp['weight_shed_lbs']} lbs weight shed vs {sp['lead_acid_range_miles']} mi lead-acid), Controller={ctrl_peak_amps}A Peak (Requires {sp['min_bms_continuous_amps']}A Cont / {sp['min_bms_peak_amps']}A Peak BMS, {sp['recommended_cable_awg']}), Top Speed={sp['top_speed_mph']} MPH ({motor_rpm} RPM, {tire_od_in}" Tires, {axle_ratio}:1 Axle).
Return ONLY a valid JSON object matching this exact schema:
{{
  "cart_name": "{model_name}",
  "seo_title": "{model_name} Range, BMS Amps & MPH Speed Calculator (2026)",
  "meta_description": "Calculate exact golf cart LiFePO4 driving range, BMS continuous/peak amp sizing, and tire/gear MPH top speed for {model_name}.",
  "specs": {{
    "nominal_voltage": {nom_volts},
    "operating_lfp_voltage": {sp['operating_lfp_voltage']},
    "battery_capacity_ah": {batt_ah},
    "total_energy_wh": {sp['total_energy_wh']},
    "controller_peak_amps": {ctrl_peak_amps},
    "min_bms_continuous_amps": {sp['min_bms_continuous_amps']},
    "min_bms_peak_amps": {sp['min_bms_peak_amps']},
    "motor_rpm": {motor_rpm},
    "tire_diameter_in": {tire_od_in},
    "axle_gear_ratio": {axle_ratio},
    "top_speed_mph": {sp['top_speed_mph']},
    "estimated_range_miles": {sp['estimated_range_miles']},
    "lead_acid_range_miles": {sp['lead_acid_range_miles']},
    "weight_shed_lbs": {sp['weight_shed_lbs']},
    "recommended_cable_awg": "{sp['recommended_cable_awg']}"
  }},
  "drivetrain_verdict": "3-sentence technical summary stating total Wh, weight shed in lbs, driving range in miles, top speed MPH with {tire_od_in}-inch tires, and required BMS continuous/peak amps.",
  "hardware_bundle": [
    {{
      "badge": "{nom_volts}V {batt_ah}Ah LiFePO4 Kit",
      "title": "{nom_volts}V {batt_ah}Ah Metal-Case Golf Cart LiFePO4 Battery ({sp['min_bms_continuous_amps']}A BMS) + Charger",
      "price_range": "$749 - $1,599",
      "amazon_query": "{nom_volts}V {batt_ah}Ah 100Ah LiFePO4 Golf Cart Battery Kit Charger",
      "cart_note": "1-sentence weight reduction and range boost note"
    }},
    {{
      "badge": "{ctrl_peak_amps}A Controller & Solenoid",
      "title": "{nom_volts}V {ctrl_peak_amps}A High-Torque Speed Controller + 400A Silver Solenoid",
      "price_range": "$159 - $799",
      "amazon_query": "{nom_volts}V Golf Cart Speed Controller 400A Solenoid",
      "cart_note": "1-sentence hill torque and anti-welding solenoid note"
    }},
    {{
      "badge": "{nom_volts}V-to-12V 30A Reducer",
      "title": "Waterproof {nom_volts}V-to-12V 30A Voltage Reducer + {sp['recommended_cable_awg'].split()[0]} AWG Copper Cable Kit",
      "price_range": "$48 - $109",
      "amazon_query": "{nom_volts}V to 12V 30A Golf Cart Voltage Reducer 2 AWG Battery Cables",
      "cart_note": "1-sentence 12V accessory protection note"
    }},
    {{
      "badge": "Lift Kit & {tire_od_in:g}\" Tires",
      "title": "A-Arm Golf Cart Lift Kit + {tire_od_in:g}\" All-Terrain Wheels/Tires & Heavy-Duty Leaf Springs",
      "price_range": "$149 - $649",
      "amazon_query": "Golf Cart Lift Kit All Terrain Wheels Tires Leaf Springs",
      "cart_note": "1-sentence ground clearance and MPH speed gain note"
    }}
  ],
  "conversion_checklist": [
    "Step 1 regarding installing a {nom_volts}V-to-12V 30A voltage reducer for lights and accessories",
    "Step 2 regarding matching {sp['min_bms_continuous_amps']}A/{sp['min_bms_peak_amps']}A BMS to {ctrl_peak_amps}A controller",
    "Step 3 regarding OBC computer bypass on Club Car / EZGO charger sense wires",
    "Step 4 regarding 400A solenoid upgrade and pre-charge resistor to prevent BMS trips"
  ],
  "faqs": [
    {{"q": "How many miles will a {nom_volts}V {batt_ah}Ah LiFePO4 battery run {model_name}?", "a": "Exact Wh, lbs shed, and miles per charge vs lead-acid."}},
    {{"q": "How fast will {model_name} go with {tire_od_in:g}-inch tires?", "a": "Exact Motor RPM x Tire OD / (Axle Ratio x 336) MPH calculation."}},
    {{"q": "What BMS amp rating do I need for a {ctrl_peak_amps}A golf cart controller?", "a": "Exact continuous and peak BMS amp requirements for hill climbing."}}
  ]
}}
"""

    for model_id in get_active_gemini_model(GEMINI_API_KEY):
        for attempt in range(2):
            try:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "responseMimeType": "application/json"
                    }
                }
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=40) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                    raw_text = re.sub(r"\s*```$", "", raw_text)
                    parsed = json.loads(raw_text)
                    if "specs" in parsed and "hardware_bundle" in parsed:
                        time.sleep(6)
                        return parsed
            except urllib.error.HTTPError as he:
                if he.code == 429:
                    print(f"[RATE-LIMIT] HTTP 429 on {model_id} (attempt {attempt + 1}). Cooling down 20s...")
                    time.sleep(20)
                else:
                    print(f"[WARN] HTTP {he.code} on {model_id} for '{model_name}': {he}")
                    break
            except Exception as e:
                print(f"[WARN] Gemini ({model_id}) notice for '{model_name}': {e}")
                break

    return det_fallback


def build_cart_html_page(data, slug, mon_cfg):
    cart_name = data.get("cart_name", "Golf Cart LiFePO4 Conversion")
    sp = data.get("specs", {})
    nom_v = int(safe_float(sp.get("nominal_voltage", 48), 48))
    lfp_v = round(safe_float(sp.get("operating_lfp_voltage", 51.2), 51.2), 1)
    ah = int(safe_float(sp.get("battery_capacity_ah", 105), 105))
    wh = int(safe_float(sp.get("total_energy_wh", 5376), 5376))
    ctrl_a = int(safe_float(sp.get("controller_peak_amps", 400), 400))
    bms_c = int(safe_float(sp.get("min_bms_continuous_amps", 200), 200))
    bms_p = int(safe_float(sp.get("min_bms_peak_amps", 460), 460))
    m_rpm = int(safe_float(sp.get("motor_rpm", 4500), 4500))
    tire_in = round(safe_float(sp.get("tire_diameter_in", 20.5), 20.5), 1)
    ax_rat = round(safe_float(sp.get("axle_gear_ratio", 12.44), 12.44), 2)
    mph = round(safe_float(sp.get("top_speed_mph", 22.1), 22.1), 1)
    rng_mi = int(safe_float(sp.get("estimated_range_miles", 46), 46))
    wt_shed = int(safe_float(sp.get("weight_shed_lbs", 285), 285))

    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "48V+105Ah+LiFePO4+Golf+Cart+Battery+Kit+200A+BMS"), mon_cfg)

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": f"{cart_name} LiFePO4 Range, BMS & MPH Calculator",
                "applicationCategory": "UtilitiesApplication",
                "operatingSystem": "Web Browser",
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f.get("q", ""),
                        "acceptedAnswer": {"@type": "Answer", "text": f.get("a", "")}
                    } for f in data.get("faqs", [])
                ]
            }
        ]
    }

    bundle_html = ""
    for item in data.get("hardware_bundle", []):
        amz_url = build_amazon_url(item.get("amazon_query", item.get("title", "48V 105Ah LiFePO4 Golf Cart Battery")), mon_cfg)
        bundle_html += f"""
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-emerald-500/60 transition">
          <div>
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="text-xs font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2.5 py-0.5 rounded">{item.get('badge', 'Cart Upgrade')}</span>
              <span class="text-sm font-bold text-amber-400">{item.get('price_range', '$69+')}</span>
            </div>
            <h3 class="text-base font-bold text-white mt-2">{item.get('title', '')}</h3>
            <p class="text-xs text-slate-400 mt-2 leading-relaxed">⛳ {item.get('cart_note', '')}</p>
          </div>
          <a href="{amz_url}" target="_blank" rel="nofollow sponsored" class="mt-5 block text-center bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold py-2.5 px-4 rounded-lg text-sm transition shadow-lg">
            Check Price on Amazon →
          </a>
        </div>"""

    # Build Golf Cart Battery Capacity vs Range, Weight Saved & Controller BMS Matrix Table
    cart_tiers = [
        ("36V 100Ah LiFePO4 (3,840 Wh)", "32 – 38 Miles", "-245 lbs Shed", "150A Cont / 350A Peak BMS", "Stock 250A–300A Controller"),
        ("48V 60Ah LiFePO4 (3,072 Wh)", "25 – 30 Miles", "-315 lbs Shed", "150A Cont / 300A Peak BMS", "2-Seat Course Cruiser"),
        ("48V 100Ah LiFePO4 (5,120 Wh)", "42 – 48 Miles", "-290 lbs Shed", "200A Cont / 400A Peak BMS", "Stock or 350A–440A Controller"),
        ("48V 105Ah LiFePO4 (5,376 Wh)", "45 – 54 Miles", "-285 lbs Shed", "200A–250A Cont / 500A Peak", "Lifted 4-Seat + 440A–600A AC"),
        ("48V 160Ah LiFePO4 (8,192 Wh)", "68 – 80 Miles", "-240 lbs Shed", "250A Cont / 600A Peak BMS", "6-Passenger Limo / Work Cart"),
        ("72V 100Ah LiFePO4 (7,680 Wh)", "55 – 65 Miles", "-310 lbs Shed", "250A Cont / 600A Peak BMS", "35+ MPH Street-Legal LSV")
    ]
    matrix_rows_html = ""
    for b_lbl, r_lbl, w_lbl, m_lbl, c_lbl in cart_tiers:
        matrix_rows_html += f"""
        <tr class="border-b border-slate-800 hover:bg-slate-800/40">
          <td class="py-3 px-4 font-bold text-white">{b_lbl}</td>
          <td class="py-3 px-4 font-bold text-emerald-400">{r_lbl}</td>
          <td class="py-3 px-4 text-amber-400 font-semibold">{w_lbl}</td>
          <td class="py-3 px-4 text-slate-300">{m_lbl}</td>
          <td class="py-3 px-4 text-xs text-slate-300">{c_lbl}</td>
        </tr>"""

    checklist_html = ""
    for idx, step_text in enumerate(data.get("conversion_checklist", []), start=1):
        checklist_html += f"""
        <label class="flex items-start gap-3.5 bg-slate-900 border border-slate-800 rounded-xl p-4 cursor-pointer hover:border-slate-700 transition">
          <input type="checkbox" class="mt-1 w-5 h-5 accent-emerald-500 rounded cursor-pointer cart-check">
          <span class="text-sm text-slate-200 leading-relaxed"><strong>Conversion Step {idx}:</strong> {step_text}</span>
        </label>"""

    faqs_html = "".join([
        f"<div class='bg-slate-900 border border-slate-800 rounded-xl p-5'><h3 class='font-bold text-white text-base mb-2'>{f.get('q', '')}</h3><p class='text-sm text-slate-300 leading-relaxed'>{f.get('a', '')}</p></div>"
        for f in data.get("faqs", [])
    ])

    canonical_url = f"{SITE_BASE_URL}/{slug}.html"
    amz_domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    amz_tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")

    html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{data.get('seo_title', cart_name)}</title>
  <meta name="description" content="{data.get('meta_description', '')}">
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:title" content="{data.get('seo_title', cart_name)}">
  <meta property="og:description" content="{data.get('meta_description', '')}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical_url}">
  <script src="https://cdn.tailwindcss.com"></script>
  <script type="application/ld+json">{json.dumps(schema_graph)}</script>
</head>
<body class="bg-slate-950 text-slate-100 antialiased min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-30">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <a href="index.html" class="text-lg font-black tracking-tight text-white flex items-center gap-2">
        <span class="bg-emerald-500 text-slate-950 px-2 py-0.5 rounded font-black">GOLFCART</span>LFPIndex
      </a>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop Golf Cart LiFePO4 Kits →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-10 flex-1 w-full">
    <div class="mb-8">
      <div class="flex flex-wrap items-center gap-2.5 mb-3">
        <span class="text-xs font-extrabold uppercase tracking-widest bg-emerald-500 text-slate-950 px-3 py-1 rounded-full">{nom_v}V {ah}Ah ({wh:,} Wh) → ~{rng_mi} Miles</span>
        <span class="text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 px-3 py-1 rounded-full">{mph} MPH ({tire_in:g}" Tires) | -{wt_shed} lbs Shed</span>
        <span class="text-xs font-semibold bg-slate-800 text-slate-300 px-3 py-1 rounded-full">BMS: {bms_c}A Cont / {bms_p}A Peak</span>
      </div>
      <h1 class="text-3xl sm:text-4xl font-black text-white leading-tight">{data.get('seo_title', cart_name)}</h1>
      <div class="mt-4 bg-slate-900 border-l-4 border-emerald-500 p-4 rounded-r-xl text-sm text-slate-200 leading-relaxed">
        <strong>EV Drivetrain, BMS & Weight-Loss Verdict:</strong> {data.get('drivetrain_verdict', '')}
      </div>
    </div>

    <!-- INTERACTIVE GOLF CART LIFEPO4 RANGE, BMS AMPS & TIRE/GEAR MPH CALCULATOR -->
    <section class="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 mb-12 shadow-2xl">
      <h2 class="text-xl font-extrabold text-white mb-2">Interactive {cart_name} Range, BMS & MPH Calculator</h2>
      <p class="text-xs text-slate-400 mb-6">Adjust your golf cart battery pack (Volts & Ah), controller amperage, motor RPM, and tire diameter to compute exact LiFePO4 driving range, BMS continuous/surge amp requirements, and top speed MPH.</p>

      <div class="grid md:grid-cols-2 gap-8 items-center">
        <div class="space-y-5">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="packSelect" class="block text-xs font-medium text-slate-400 mb-1">LiFePO4 Battery Pack Size</label>
              <select id="packSelect" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500">
                <option value="36|38.4|105" {"selected" if nom_v == 36 else ""}>36V 105Ah LiFePO4 (4,032 Wh)</option>
                <option value="48|51.2|60">48V 60Ah LiFePO4 (3,072 Wh)</option>
                <option value="48|51.2|100" {"selected" if nom_v == 48 and ah == 100 else ""}>48V 100Ah LiFePO4 (5,120 Wh)</option>
                <option value="48|51.2|105" {"selected" if nom_v == 48 and ah == 105 else ""}>48V 105Ah LiFePO4 (5,376 Wh)</option>
                <option value="48|51.2|160" {"selected" if nom_v == 48 and ah >= 150 else ""}>48V 160Ah LiFePO4 (8,192 Wh)</option>
                <option value="72|76.8|105" {"selected" if nom_v == 72 else ""}>72V 105Ah LiFePO4 (8,064 Wh)</option>
              </select>
            </div>
            <div>
              <label for="ctrlSelect" class="block text-xs font-medium text-slate-400 mb-1">Speed Controller Rating</label>
              <select id="ctrlSelect" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500">
                <option value="275" {"selected" if ctrl_a <= 300 else ""}>250A–300A Stock Controller</option>
                <option value="350" {"selected" if 300 < ctrl_a <= 380 else ""}>350A Heavy-Duty Controller</option>
                <option value="440" {"selected" if 380 < ctrl_a <= 460 else ""}>440A Navitas / Alltrax Controller</option>
                <option value="600" {"selected" if ctrl_a > 460 else ""}>600A Navitas 5kW AC Controller</option>
              </select>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <div class="flex justify-between text-xs font-medium mb-1">
                <label for="rpmSlider" class="text-slate-300">Motor Max RPM</label>
                <span class="text-emerald-400 font-bold"><span id="rpmVal">{m_rpm:,}</span> RPM</span>
              </div>
              <input id="rpmSlider" type="range" min="3200" max="6500" step="100" value="{m_rpm}" class="w-full accent-emerald-500 cursor-pointer">
            </div>
            <div>
              <div class="flex justify-between text-xs font-medium mb-1">
                <label for="tireSlider" class="text-slate-300">Tire Diameter (In)</label>
                <span class="text-emerald-400 font-bold"><span id="tireVal">{tire_in:g}</span>" Tires</span>
              </div>
              <input id="tireSlider" type="range" min="18.0" max="25.0" step="0.5" value="{tire_in}" class="w-full accent-emerald-500 cursor-pointer">
            </div>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="bg-slate-950 border border-emerald-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-emerald-400 font-bold">LiFePO4 Driving Range</span>
            <div class="text-2xl sm:text-3xl font-black text-white mt-1">~<span id="rangeOut">{rng_mi}</span> <span class="text-xs font-normal text-slate-400">miles</span></div>
            <p id="whNoteOut" class="text-xs text-emerald-400 font-semibold mt-1">{wh:,} Wh (-{wt_shed} lbs Shed)</p>
          </div>

          <div class="bg-slate-950 border border-amber-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-amber-400 font-bold">Top Speed & Min BMS</span>
            <div class="text-2xl sm:text-3xl font-black text-amber-400 mt-1"><span id="mphOut">{mph}</span> <span class="text-xs font-normal text-slate-400">MPH</span></div>
            <p id="bmsNoteOut" class="text-xs text-slate-300 font-semibold mt-1">Need {bms_c}A Cont / {bms_p}A Peak</p>
          </div>
        </div>
      </div>

      <div class="mt-6 bg-emerald-950/40 border border-emerald-500/30 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div id="cartAdviceBanner" class="text-sm text-emerald-100 font-medium"></div>
        <a id="dynamicCartBtn" href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="shrink-0 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold px-4 py-2.5 rounded-lg text-xs uppercase tracking-wider transition">
          Shop Matched LiFePO4 Kit & Solenoid on Amazon →
        </a>
      </div>
    </section>

    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">Complete {cart_name} LiFePO4, Controller & Reducer Kit</h2>
        <span class="text-xs text-slate-400">Grade-A Prismatic Cells & 200A+ High-Surge BMS</span>
      </div>
      <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{bundle_html}</div>
    </section>

    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-4">Golf Cart LiFePO4 Battery Capacity, Range, Weight Saved & BMS Chart</h2>
      <div class="overflow-x-auto bg-slate-900 border border-slate-800 rounded-xl">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-950/60 text-slate-400 uppercase text-xs">
              <th class="py-3.5 px-4">LiFePO4 Battery Pack</th>
              <th class="py-3.5 px-4 text-emerald-400">Real-World Range</th>
              <th class="py-3.5 px-4 text-amber-400">Lead-Acid Weight Shed</th>
              <th class="py-3.5 px-4">Required BMS Rating</th>
              <th class="py-3.5 px-4">Controller Match</th>
            </tr>
          </thead>
          <tbody>{matrix_rows_html}</tbody>
        </table>
      </div>
    </section>

    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">Golf Cart Lithium Conversion, 12V Reducer & 400A Solenoid Checklist</h2>
        <span id="cartBadge" class="text-xs font-bold bg-slate-800 text-emerald-400 px-3 py-1 rounded-full">0 / 4 Completed</span>
      </div>
      <div class="space-y-3">{checklist_html}</div>
    </section>

    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-5">Frequently Asked Questions ({cart_name})</h2>
      <div class="space-y-4">{faqs_html}</div>
    </section>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500 px-4">
    <p>© {datetime.now(timezone.utc).year} GolfCartLFPIndex. Independent EV Golf Cart LiFePO4 Conversion & Drivetrain Sizing Database. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const baseAxleRatio = {ax_rat};
    const amzDomain = "{amz_domain}";
    const amzTag = "{amz_tag}";

    const packSelect = document.getElementById('packSelect');
    const ctrlSelect = document.getElementById('ctrlSelect');
    const rpmSlider = document.getElementById('rpmSlider');
    const tireSlider = document.getElementById('tireSlider');
    const rpmVal = document.getElementById('rpmVal');
    const tireVal = document.getElementById('tireVal');
    const rangeOut = document.getElementById('rangeOut');
    const whNoteOut = document.getElementById('whNoteOut');
    const mphOut = document.getElementById('mphOut');
    const bmsNoteOut = document.getElementById('bmsNoteOut');
    const cartAdviceBanner = document.getElementById('cartAdviceBanner');
    const dynamicCartBtn = document.getElementById('dynamicCartBtn');

    function recalculateCart() {{
      const packParts = packSelect.value.split('|');
      const nomV = parseInt(packParts[0], 10);
      const lfpV = parseFloat(packParts[1]);
      const ah = parseInt(packParts[2], 10);
      const ctrlAmps = parseInt(ctrlSelect.value, 10);
      const rpm = parseInt(rpmSlider.value, 10);
      const tireIn = parseFloat(tireSlider.value);

      rpmVal.textContent = rpm.toLocaleString();
      tireVal.textContent = tireIn.toFixed(1);

      const totalWh = Math.round(lfpV * ah);
      const usableWh = totalWh * 0.95;
      const whPerMile = tireIn >= 22.0 ? 122.0 : 104.0;
      const rangeMiles = Math.round(usableWh / whPerMile);
      const wtShed = nomV === 36 ? 245 : 285;

      const mph = ((rpm * tireIn) / (baseAxleRatio * 336.0)).toFixed(1);
      const minBmsCont = ctrlAmps <= 300 ? 150 : (ctrlAmps <= 450 ? 200 : 250);
      const minBmsPeak = Math.max(350, Math.round((ctrlAmps * 1.15) / 10) * 10);

      rangeOut.textContent = rangeMiles;
      whNoteOut.textContent = `${{totalWh.toLocaleString()}} Wh (-${{wtShed}} lbs Shed)`;
      mphOut.textContent = mph;
      bmsNoteOut.textContent = `Need ${{minBmsCont}}A Cont / ${{minBmsPeak}}A Peak`;

      cartAdviceBanner.innerHTML = `⛳ <strong>Lithium Drivetrain Spec:</strong> Install a <strong>${{nomV}}V ${{ah}}Ah Metal-Case LiFePO4 Kit (${{minBmsCont}}A Continuous / ${{minBmsPeak}}A Peak BMS)</strong> + <strong>400A Silver Solenoid</strong> + <strong>${{nomV}}V-to-12V 30A Voltage Reducer</strong> for <strong>~${{rangeMiles}} miles of range</strong> at <strong>${{mph}} MPH</strong>.`;
      dynamicCartBtn.href = `https://${{amzDomain}}/s?k=${{nomV}}V+${{ah}}Ah+LiFePO4+Golf+Cart+Battery+Kit+${{minBmsCont}}A+BMS+Charger&tag=${{amzTag}}`;
    }}

    packSelect.addEventListener('change', recalculateCart);
    ctrlSelect.addEventListener('change', recalculateCart);
    rpmSlider.addEventListener('input', recalculateCart);
    tireSlider.addEventListener('input', recalculateCart);
    recalculateCart();

    const checks = document.querySelectorAll('.cart-check');
    const badge = document.getElementById('cartBadge');
    checks.forEach(ch => {{
      ch.addEventListener('change', () => {{
        const done = Array.from(checks).filter(c => c.checked).length;
        badge.textContent = `${{done}} / ${{checks.length}} Completed`;
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)


def rebuild_portal_sitemap_and_rss(published, mon_cfg):
    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "48V+105Ah+LiFePO4+Golf+Cart+Battery+Kit+200A+BMS"), mon_cfg)

    cards_html = ""
    for item in reversed(published):
        cards_html += f"""
        <a href="{item['slug']}.html" class="block bg-slate-900 border border-slate-800 hover:border-emerald-500/60 rounded-xl p-5 transition group">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-black uppercase bg-emerald-500 text-slate-950 px-2.5 py-0.5 rounded">{item.get('volts', 48)}V {item.get('ah', 105)}Ah (~{item.get('miles', 46)} Mi)</span>
            <span class="text-xs text-slate-400">{item.get('mph', 22.1)} MPH | {item.get('bms_c', 200)}A BMS</span>
          </div>
          <h2 class="text-base font-bold text-white group-hover:text-emerald-400 transition">{item['cart_name']}</h2>
          <p class="text-xs text-slate-400 mt-2 line-clamp-2">{item['description']}</p>
          <span class="inline-block mt-4 text-xs font-extrabold text-emerald-400">Calculate Range, BMS & Tire MPH →</span>
        </a>"""

    index_html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GolfCartLFPIndex — 36V/48V/72V Golf Cart LiFePO4 Range, BMS & MPH Speed Calculator (2026)</title>
  <meta name="description" content="Calculate exact 36V, 48V, and 72V LiFePO4 golf cart battery range, BMS continuous/peak surge amp sizing for 400A-600A controllers, and tire/axle MPH speed for Club Car, EZGO, Yamaha, and Icon carts.">
  <link rel="canonical" href="{SITE_BASE_URL}/">
  <link rel="alternate" type="application/rss+xml" title="GolfCartLFPIndex RSS Feed" href="{SITE_BASE_URL}/rss.xml">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 sticky top-0 z-30 backdrop-blur">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <div class="text-lg font-black text-white flex items-center gap-2">
        <span class="bg-emerald-500 text-slate-950 px-2 py-0.5 rounded font-black">GOLFCART</span>LFPIndex
      </div>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop Golf Cart LiFePO4 Kits →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-12 flex-1 w-full">
    <div class="text-center max-w-2xl mx-auto mb-10">
      <h1 class="text-3xl sm:text-5xl font-black text-white tracking-tight">Golf Cart LiFePO4 Battery Range, BMS Amp & MPH Speed Database</h1>
      <p class="text-slate-400 mt-3 text-base sm:text-lg">Select your Club Car, EZGO, or Yamaha golf cart setup below to calculate LiFePO4 driving range after shedding 285 lbs of lead-acid weight, BMS surge amps for 400A–600A controllers, and tire/gear MPH speed.</p>
      <div class="mt-6">
        <input id="filterInput" type="text" placeholder="Search golf cart or battery (e.g. Club Car Precedent, EZGO TXT, Yamaha G29, 48V 105Ah, Navitas 600A, 23 Inch Tires...)" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-emerald-500">
      </div>
    </div>

    <div id="cartGrid" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">{cards_html}</div>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500">
    <p>© {datetime.now(timezone.utc).year} GolfCartLFPIndex. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const filterInput = document.getElementById('filterInput');
    const cards = Array.from(document.getElementById('cartGrid').children);
    filterInput.addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase();
      cards.forEach(c => {{
        c.style.display = c.textContent.toLowerCase().includes(q) ? 'block' : 'none';
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls_xml = f"""  <url>
    <loc>{SITE_BASE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>\n"""

    for item in published:
        urls_xml += f"""  <url>
    <loc>{SITE_BASE_URL}/{item['slug']}.html</loc>
    <lastmod>{item.get('date', today)}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>\n"""

    with open(os.path.join(DOCS_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls_xml}</urlset>""")

    rss_items = ""
    for item in list(reversed(published))[:30]:
        rss_items += f"""    <item>
      <title>{item['title']}</title>
      <link>{SITE_BASE_URL}/{item['slug']}.html</link>
      <guid>{SITE_BASE_URL}/{item['slug']}.html</guid>
      <description>{item['description']}</description>
    </item>\n"""

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>GolfCartLFPIndex Golf Cart Lithium Conversion & Speed Database</title>
    <link>{SITE_BASE_URL}/</link>
    <description>Interactive 36V/48V/72V Golf Cart LiFePO4 Range, BMS Amp & Tire MPH Speed Calculators</description>
    <atom:link href="{SITE_BASE_URL}/rss.xml" rel="self" type="application/rss+xml" />
    <atom:link href="https://pubsubhubbub.appspot.com/" rel="hub" />
{rss_items}  </channel>
</rss>"""

    with open(os.path.join(DOCS_DIR, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(rss_xml)

    with open(os.path.join(DOCS_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n")

    with open(os.path.join(DOCS_DIR, f"{INDEXNOW_KEY}.txt"), "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)


def notify_search_engines(new_urls):
    """Multi-Endpoint Search Engine Pinger (IndexNow Global + Bing + Google WebSub)."""
    if not SITE_BASE_URL or not new_urls:
        return
    parsed_host = urllib.parse.urlparse(SITE_BASE_URL).netloc
    payload = {
        "host": parsed_host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_BASE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": new_urls
    }
    for idx_endpoint in ["https://api.indexnow.org/indexnow", "https://www.bing.com/indexnow"]:
        try:
            req = urllib.request.Request(
                idx_endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                print(f"[INDEXNOW] Pushed {len(new_urls)} URLs to {idx_endpoint} (HTTP {resp.status})")
                break
        except Exception as e:
            print(f"[WARN] IndexNow ({idx_endpoint}) notice: {e}")

    try:
        hub_data = urllib.parse.urlencode({
            "hub.mode": "publish",
            "hub.url": f"{SITE_BASE_URL}/rss.xml"
        }).encode("utf-8")
        req_hub = urllib.request.Request(
            "https://pubsubhubbub.appspot.com/",
            data=hub_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        with urllib.request.urlopen(req_hub, timeout=15) as resp_hub:
            print(f"[WEBSUB] Google PubSubHubbub ping status: {resp_hub.status}")
    except Exception as e:
        print(f"[WARN] WebSub ping notice: {e}")


def main():
    published = load_json(PUBLISHED_FILE, [])
    mon_cfg = load_json(MONETIZATION_FILE, {})
    published_slugs = {item["slug"] for item in published if "slug" in item}

    candidates = []
    if CUSTOM_CART:
        candidates.append((CUSTOM_CART.strip(), 48, 105, 400, 4500, 20.5, 12.44))
    candidates.extend(SEED_CARTS)
    candidates.extend(discover_google_cart_queries(published_slugs))

    new_urls = []
    count = 0

    for cart_tuple in candidates:
        if count >= PAGES_PER_RUN:
            break
        c_name = cart_tuple[0]
        slug = slugify(f"{c_name}-range-mph-calculator")
        if slug in published_slugs:
            continue

        print(f"[ENGINE] Generating golf cart LiFePO4 range & MPH speed calculator for: {c_name}...")
        try:
            data = generate_cart_data(cart_tuple)
            build_cart_html_page(data, slug, mon_cfg)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            sp = data.get("specs", {})

            published.append({
                "cart_name": data.get("cart_name", c_name),
                "slug": slug,
                "title": data.get("seo_title", f"{c_name} Golf Cart Calculator"),
                "description": data.get("meta_description", ""),
                "volts": int(safe_float(sp.get("nominal_voltage", cart_tuple[1]), cart_tuple[1])),
                "ah": int(safe_float(sp.get("battery_capacity_ah", cart_tuple[2]), cart_tuple[2])),
                "miles": int(safe_float(sp.get("estimated_range_miles", 46), 46)),
                "mph": round(safe_float(sp.get("top_speed_mph", 22.1), 22.1), 1),
                "bms_c": int(safe_float(sp.get("min_bms_continuous_amps", 200), 200)),
                "date": today
            })
            published_slugs.add(slug)
            if SITE_BASE_URL:
                new_urls.append(f"{SITE_BASE_URL}/{slug}.html")
            count += 1
            if count < PAGES_PER_RUN:
                time.sleep(15)
        except Exception as e:
            print(f"[ERROR] Failed building {c_name}: {e}")

    save_json(PUBLISHED_FILE, published)
    rebuild_portal_sitemap_and_rss(published, mon_cfg)
    if new_urls and SITE_BASE_URL:
        new_urls.append(f"{SITE_BASE_URL}/")
        notify_search_engines(new_urls)
    print(f"[DONE] Published {count} new golf cart LiFePO4 range & speed calculator pages.")


if __name__ == "__main__":
    main()
