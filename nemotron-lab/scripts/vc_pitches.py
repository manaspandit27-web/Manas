"""Synthetic pitches for the Bramblewood Ventures screening scenario (scenarios/vc_screening).

Each pitch is built from hidden facts (stage, round size, headquarters, market, founders, the sector's
must-have, traction, who made the intro), written out as a founder's email, and labelled by `screen`,
which applies the dealbook (scenarios/vc_screening/policy.md) step by step. `screen` is the only place
the rules live, so the labels always follow the dealbook.

The long tail is set by SECTOR_SKEW (how fast thesis sectors get rarer) and NEAR_MISS (how often a
pitch sits just either side of a threshold). See scenarios/vc_screening/NOTES.md.
"""

import math
from dataclasses import dataclass, field

SECTOR_SKEW = 1.0   # thesis sector k (1 = most common) has weight 1 / k**SECTOR_SKEW
NEAR_MISS = 0.35    # share of numeric facts drawn close to the threshold that decides them

STAGE_RANGES = {"pre-seed": (0.5, 2.5), "seed": (2.0, 6.0), "Series A": (6.0, 20.0)}  # $M
QUALIFYING_EXIT_M = 50
BARS = {  # Table E meeting bars: (seed, Series A)
    "b2b": (150_000, 1_000_000),
    "marketplace": (100_000, 750_000),
    "consumer": (5_000, 40_000),
    "hardware": (250_000, 2_000_000),
}
FAST_MULTIPLE = 3

# ------------------------------------------------------------- geography ---

US = ["Boston", "New York", "San Francisco", "Austin", "Chicago", "Denver", "Seattle", "Atlanta", "Miami",
      "Pittsburgh", "Los Angeles", "Nashville", "Minneapolis", "Philadelphia", "Salt Lake City"]
CANADA = ["Toronto", "Montreal", "Vancouver", "Waterloo", "Calgary"]
UK = ["London", "Manchester", "Edinburgh", "Bristol"]
IRELAND = ["Dublin", "Cork"]
OTHER = ["Berlin", "Paris", "Tel Aviv", "Bangalore", "Singapore", "São Paulo", "Sydney", "Amsterdam",
         "Stockholm", "Mexico City", "Lagos", "Madrid"]
ORIGINS = ["Lagos", "Mumbai", "Seoul", "Bogotá", "Kyiv", "Manila", "Cairo", "Warsaw", "Lima", "Hanoi"]


def region(city):
    if city in US or city in CANADA:
        return "us_ca"
    if city in UK or city in IRELAND:
        return "uk_ie"
    return "other"


# --------------------------------------------------------------- markets ---
# Each market: sector, business model, ways to describe it, and for some the buyer (education and HR
# must-haves depend on who pays). Portfolio markets carry the portfolio company's name.

@dataclass
class Market:
    key: str
    sector: str
    model: str
    phrases: list
    buyer: str = ""        # "institution"/"learner" (education) or "employer"/"worker" (HR)
    industry: str = ""     # vertical software: the industry the founder must have worked in
    portfolio: str = ""


PORTFOLIO_STATUS = {
    "Ladle": "active", "Trowel": "active", "Molar": "active", "Brieflet": "active", "Fernbank": "active",
    "Ledgerline": "active", "Hearthwise": "active", "Tendwell": "active", "Stitchpoint": "active",
    "Cindertrack": "active", "Gridnote": "active", "Patchbay": "active", "Querylane": "active",
    "Scribeleaf": "active", "Tallyhand": "active", "Kilnworks": "active", "Moatline": "active",
    "Chalkline": "active", "Palletwise": "active", "Haulbridge": "active", "Rowbot": "active",
    "Greenshelf": "active", "Rotaline": "active", "Perkwell": "active",
    "Quaywise": "exited", "Pennywhistle": "exited", "Brightvault": "exited", "Tutorly": "exited",
    "Voltwise": "exited", "Crumbline": "exited",
}

M = Market
MARKETS = [
    # vertical software
    M("restaurant_payroll", "vertical_software", "b2b", ["payroll and tip-sharing software for restaurants",
      "a payroll and tip-pooling platform for restaurant groups", "software that runs payroll and splits tips for restaurants"],
      industry="restaurant", portfolio="Ladle"),
    M("restaurant_scheduling", "vertical_software", "b2b", ["shift scheduling software for restaurants",
      "a staff scheduling app for restaurant managers"], industry="restaurant"),
    M("restaurant_ap", "vertical_software", "b2b", ["accounts-payable automation for restaurants",
      "invoice and bill-pay software for restaurant groups"], industry="restaurant", portfolio="Pennywhistle"),
    M("construction_bids", "vertical_software", "b2b", ["bid management software for construction subcontractors",
      "a tool that helps construction subcontractors find and price bids"], industry="construction", portfolio="Trowel"),
    M("construction_safety", "vertical_software", "b2b", ["jobsite safety inspection software for general contractors",
      "a safety-checklist app for construction sites"], industry="construction"),
    M("dental_scheduling", "vertical_software", "b2b", ["patient scheduling software for dental practices",
      "online booking and appointment reminders for dental offices"], industry="dental", portfolio="Molar"),
    M("dental_billing", "vertical_software", "b2b", ["insurance billing software for dental practices",
      "claims and billing automation for dental offices"], industry="dental"),
    M("law_intake", "vertical_software", "b2b", ["client intake software for small law firms",
      "a tool that screens and onboards new clients for small law firms"], industry="legal", portfolio="Brieflet"),
    M("law_billing", "vertical_software", "b2b", ["time-tracking and billing software for small law firms"], industry="legal"),
    M("bakery_inventory", "vertical_software", "b2b", ["inventory software for bakeries",
      "ingredient and stock tracking for bakeries"], industry="bakery", portfolio="Crumbline"),
    M("butcher_inventory", "vertical_software", "b2b", ["inventory software for independent butcher shops"], industry="butcher"),
    M("trucking_dispatch", "vertical_software", "b2b", ["dispatch software for small trucking fleets",
      "load-planning and dispatch tools for owner-operator trucking companies"], industry="trucking"),
    M("salon_booking", "vertical_software", "marketplace", ["a booking marketplace for independent hair salons"], industry="salon"),
    M("vet_billing", "vertical_software", "b2b", ["billing software for veterinary clinics"], industry="veterinary"),
    M("auto_repair", "vertical_software", "b2b", ["shop management software for auto repair garages"], industry="auto repair"),
    # AI applications
    M("vet_scribe", "ai_applications", "b2b", ["AI note-taking for veterinary clinics",
      "an AI scribe that writes up veterinary visits"], portfolio="Scribeleaf"),
    M("vet_phone_ai", "ai_applications", "b2b", ["an AI phone receptionist for veterinary clinics"]),
    M("lease_review", "ai_applications", "b2b", ["AI review of commercial real-estate leases",
      "AI that abstracts and flags terms in commercial leases"], portfolio="Tallyhand"),
    M("rental_screening_ai", "ai_applications", "b2b", ["AI screening of rental applications for residential landlords"]),
    M("contract_ai", "ai_applications", "b2b", ["AI contract review for in-house legal teams"]),
    M("claims_ai", "ai_applications", "b2b", ["AI that drafts claim summaries for insurance adjusters"]),
    M("sales_email_ai", "ai_applications", "b2b", ["AI that writes sales follow-up emails for B2B sales teams"]),
    M("permit_ai", "ai_applications", "b2b", ["AI that fills out building-permit applications for architects"]),
    # developer tools
    M("feature_flags", "developer_tools", "b2b", ["feature-flag and release tooling for software teams",
      "feature flags and staged rollouts for engineering teams"], portfolio="Patchbay"),
    M("timeseries_db", "developer_tools", "b2b", ["an open-source time-series database"], portfolio="Querylane"),
    M("graph_db", "developer_tools", "b2b", ["an open-source graph database"]),
    M("api_testing", "developer_tools", "b2b", ["an API testing tool", "automated testing for public APIs"]),
    M("ci_runners", "developer_tools", "b2b", ["faster build runners for continuous integration"]),
    M("mobile_errors", "developer_tools", "b2b", ["error monitoring for mobile apps"]),
    M("dev_docs", "developer_tools", "b2b", ["a documentation platform for developer products"]),
    # fintech infrastructure
    M("embedded_banking", "fintech_infrastructure", "b2b", ["embedded business bank accounts for vertical software companies",
      "an API that lets software platforms offer bank accounts to their business customers"], portfolio="Fernbank"),
    M("ar_automation", "fintech_infrastructure", "b2b", ["accounts-receivable automation for mid-size B2B companies",
      "software that automates invoicing and collections for mid-market companies"], portfolio="Ledgerline"),
    M("ap_midmarket", "fintech_infrastructure", "b2b", ["accounts-payable automation for mid-size companies"]),
    M("card_issuing", "fintech_infrastructure", "b2b", ["a card-issuing API for fintech startups"]),
    M("payroll_api", "fintech_infrastructure", "b2b", ["an embedded payroll API for HR software companies"]),
    M("cross_border", "fintech_infrastructure", "b2b", ["cross-border payouts for online marketplaces"]),
    # digital health
    M("heart_failure_rpm", "digital_health", "b2b", ["remote monitoring for patients with heart failure",
      "a remote-monitoring program for heart-failure patients"], portfolio="Tendwell"),
    M("diabetes_rpm", "digital_health", "b2b", ["remote monitoring for patients with type 2 diabetes"]),
    M("prior_auth", "digital_health", "b2b", ["prior-authorization automation for clinics"]),
    M("sleep_app", "digital_health", "consumer", ["a sleep-coaching app for adults with insomnia"]),
    M("home_pt", "digital_health", "consumer", ["at-home physical therapy programs delivered by app"]),
    # cybersecurity
    M("phishing_training", "cybersecurity", "b2b", ["phishing simulation and security training for employees",
      "security-awareness training with simulated phishing for staff"], portfolio="Moatline"),
    M("email_security", "cybersecurity", "b2b", ["email security that blocks phishing attacks"]),
    M("medical_backup", "cybersecurity", "b2b", ["cloud backup for small medical practices"], portfolio="Brightvault"),
    M("cloud_posture", "cybersecurity", "b2b", ["cloud security posture management"]),
    M("contractor_access", "cybersecurity", "b2b", ["access management for contractors and vendors"]),
    M("code_scanning", "cybersecurity", "b2b", ["code scanning for security vulnerabilities"]),
    # supply chain and logistics
    M("warehouse_slotting", "supply_chain", "b2b", ["warehouse slotting optimization",
      "software that decides where each product goes in a warehouse"], portfolio="Palletwise"),
    M("warehouse_labor", "supply_chain", "b2b", ["labour planning software for warehouses"]),
    M("freight_matching", "supply_chain", "marketplace", ["a freight-matching marketplace for regional trucking carriers"],
      portfolio="Haulbridge"),
    M("customs_paperwork", "supply_chain", "b2b", ["customs paperwork automation for importers"], portfolio="Quaywise"),
    M("returns", "supply_chain", "b2b", ["returns management for online retailers"]),
    M("cold_chain", "supply_chain", "b2b", ["temperature tracking for cold-chain shipments"]),
    # AI infrastructure
    M("gpu_scheduling", "ai_infrastructure", "b2b", ["GPU scheduling software for AI training clusters"], portfolio="Kilnworks"),
    M("gpu_rental", "ai_infrastructure", "marketplace", ["a marketplace for renting spare GPUs"]),
    M("llm_evals", "ai_infrastructure", "b2b", ["an evaluation platform for LLM applications"]),
    M("vector_db", "ai_infrastructure", "b2b", ["a vector database for AI applications"]),
    M("inference_serving", "ai_infrastructure", "b2b", ["inference serving for open-weight models"]),
    # HR and workforce
    M("hospital_shifts", "hr_workforce", "b2b", ["shift scheduling for hourly hospital staff"], buyer="employer",
      portfolio="Rotaline"),
    M("retail_shifts", "hr_workforce", "b2b", ["shift scheduling for retail store staff"], buyer="employer"),
    M("smb_benefits", "hr_workforce", "b2b", ["benefits administration for companies under 200 employees"], buyer="employer",
      portfolio="Perkwell"),
    M("enterprise_benefits", "hr_workforce", "b2b", ["benefits administration for companies with 5,000+ employees"],
      buyer="employer"),
    M("onboarding", "hr_workforce", "b2b", ["employee onboarding software sold to HR teams"], buyer="employer"),
    M("worker_coaching", "hr_workforce", "consumer", ["a career-coaching app that hourly workers subscribe to themselves"],
      buyer="worker"),
    M("gig_benefits", "hr_workforce", "consumer", ["portable benefits that gig workers buy for themselves"], buyer="worker"),
    # education
    M("sub_teachers", "education", "b2b", ["substitute-teacher scheduling for school districts"], buyer="institution",
      portfolio="Chalkline"),
    M("college_tutoring", "education", "marketplace", ["an online tutoring marketplace where college students book tutors"],
      buyer="learner", portfolio="Tutorly"),
    M("district_reading", "education", "b2b", ["a reading-assessment platform sold to school districts"], buyer="institution"),
    M("university_advising", "education", "b2b", ["advising software for universities"], buyer="institution"),
    M("employer_training", "education", "b2b", ["compliance-training courses sold to employers"], buyer="institution"),
    M("language_app", "education", "consumer", ["a language-learning app that adults subscribe to directly"], buyer="learner"),
    M("test_prep", "education", "consumer", ["an SAT-prep subscription that families buy directly"], buyer="learner"),
    # climate hardware
    M("industrial_heat_pumps", "climate_hardware", "hardware", ["industrial heat pumps for food-processing plants"],
      portfolio="Cindertrack"),
    M("home_heat_pumps", "climate_hardware", "hardware", ["heat pumps for single-family homes"]),
    M("green_cement", "climate_hardware", "hardware", ["low-carbon cement additives"]),
    M("grid_batteries", "climate_hardware", "hardware", ["long-duration batteries for utilities"]),
    M("carbon_capture", "climate_hardware", "hardware", ["carbon-capture units for factory smokestacks"]),
    # energy and grid software
    M("demand_response", "energy_software", "b2b", ["demand-response forecasting for utilities"], portfolio="Gridnote"),
    M("solar_forecasting", "energy_software", "b2b", ["solar-output forecasting for utilities"]),
    M("ev_install", "energy_software", "b2b", ["installation scheduling for EV chargers"], portfolio="Voltwise"),
    M("building_energy", "energy_software", "b2b", ["energy-management software for commercial buildings"]),
    M("interconnection", "energy_software", "b2b", ["software that speeds up grid-interconnection applications"]),
    # insurtech
    M("str_insurance", "insurtech", "consumer", ["home insurance for short-term rental hosts"], portfolio="Hearthwise"),
    M("renters_insurance", "insurtech", "consumer", ["renters insurance for college students"]),
    M("pet_insurance", "insurtech", "consumer", ["monthly pet insurance"]),
    M("broker_quoting", "insurtech", "b2b", ["quoting software for independent insurance brokers"]),
    # robotics and automation
    M("robotic_weeding", "robotics", "hardware", ["robotic weeding for vegetable farms"], portfolio="Rowbot"),
    M("robotic_harvesting", "robotics", "hardware", ["robotic strawberry harvesting"]),
    M("truck_unloading", "robotics", "hardware", ["robots that unload trucks at warehouses"]),
    M("hospital_delivery", "robotics", "hardware", ["delivery robots for hospital supplies"]),
    M("window_cleaning", "robotics", "hardware", ["window-cleaning robots for office towers"]),
    # food and agriculture tech
    M("produce_shelf_life", "food_agtech", "b2b", ["shelf-life prediction for grocery produce"], portfolio="Greenshelf"),
    M("dairy_shelf_life", "food_agtech", "b2b", ["shelf-life prediction for dairy products"]),
    M("vertical_farms", "food_agtech", "hardware", ["indoor vertical farms for leafy greens"]),
    M("soil_sensors", "food_agtech", "hardware", ["soil-moisture sensors for orchards"]),
    # medical devices
    M("wound_closure", "medical_devices", "hardware", ["a single-use device for closing surgical wounds"],
      portfolio="Stitchpoint"),
    M("infection_device", "medical_devices", "hardware", ["a device that lowers surgical-site infections"]),
    M("glucose_patch", "medical_devices", "hardware", ["a wearable glucose patch"]),
    M("cardiac_implant", "medical_devices", "hardware", ["a cardiac implant for heart-failure patients"]),
    M("otc_hearing", "medical_devices", "hardware", ["an over-the-counter hearing aid"]),
    M("single_use_scope", "medical_devices", "hardware", ["a single-use endoscope"]),
    # outside thesis (step 5)
    M("drug_discovery", "drug_discovery", "b2b", ["AI-driven drug discovery for rare diseases", "a small-molecule therapeutics platform"]),
    M("consumer_social", "consumer_social", "consumer", ["a social app for college students", "a photo-sharing app for close friends"]),
    M("games", "games", "consumer", ["a mobile puzzle game", "a multiplayer strategy game for PC"]),
    M("d2c", "d2c_brands", "consumer", ["a direct-to-consumer sneaker brand", "a direct-to-consumer skincare brand"]),
    M("media", "media", "consumer", ["a newsletter network for local news", "a podcast studio"]),
    M("restaurants", "restaurants_retail", "consumer", ["a chain of fast-casual salad restaurants", "a chain of neighbourhood coffee shops"]),
    M("space", "space", "hardware", ["small satellites that photograph farmland", "a reusable rocket for small payloads"]),
    M("semis", "semiconductors", "hardware", ["a chip for running AI models on phones", "a power-management chip for data centres"]),
    # excluded (step 3)
    M("gambling", "gambling", "consumer", ["a sports-betting app", "an online poker platform"]),
    M("vaping", "tobacco_vaping", "consumer", ["a vape brand", "a nicotine-pouch brand"]),
    M("cannabis", "cannabis", "b2b", ["point-of-sale software for cannabis dispensaries", "a cannabis delivery service"]),
    M("weapons", "weapons", "hardware", ["smart rifle scopes", "armed drones for border patrols"]),
    M("crypto_tokens", "crypto_tokens", "consumer", ["a token-funded decentralized storage network", "a play-to-earn crypto token"]),
    M("payday", "payday_lending", "consumer", ["payday loans through a mobile app", "high-interest installment loans for gig workers"]),
    M("adult", "adult_content", "consumer", ["a subscription platform for adult creators"]),
    M("fossil", "fossil_extraction", "hardware", ["an oil and gas exploration company", "fracking services for shale producers"]),
]
MARKET = {m.key: m for m in MARKETS}

THESIS = ["vertical_software", "ai_applications", "developer_tools", "fintech_infrastructure", "digital_health",
          "cybersecurity", "supply_chain", "ai_infrastructure", "hr_workforce", "education", "climate_hardware",
          "energy_software", "insurtech", "robotics", "food_agtech", "medical_devices"]
OUTSIDE = ["drug_discovery", "consumer_social", "games", "d2c_brands", "media", "restaurants_retail", "space",
           "semiconductors"]
EXCLUDED = ["gambling", "tobacco_vaping", "cannabis", "weapons", "crypto_tokens", "payday_lending", "adult_content",
            "fossil_extraction"]
SHARE_OUTSIDE, SHARE_EXCLUDED = 0.08, 0.05
PORTFOLIO_MARKET_SHARE = 0.18  # within a sector, chance the pitch is in a portfolio company's market


# ----------------------------------------------------------------- facts ---

@dataclass
class Facts:
    stage: str
    amount_m: float
    city: str
    market: str
    must_have: bool
    exit_kind: str = "none"   # none | cofounder | employee | shutdown
    exit_value_m: int = 0
    traction: float = 0.0     # in the business model's unit; 0 = pre-revenue
    intro: str = "none"       # none | portfolio | other
    intro_company: str = ""
    extra: dict = field(default_factory=dict)  # details for the text (years, stars, partners, ...)


def qualifying_exit(f):
    return f.exit_kind == "cofounder" and f.exit_value_m >= QUALIFYING_EXIT_M


def screen(f):
    """The dealbook, step by step. Returns (decision, reason)."""
    m = MARKET[f.market]
    lo_hi = STAGE_RANGES.get(f.stage)
    if lo_hi is None or not lo_hi[0] <= f.amount_m <= lo_hi[1]:
        return "pass", "stage_or_size"
    reg = region(f.city)
    if reg == "other" or (reg == "uk_ie" and f.stage != "Series A"):
        return "pass", "geography"
    if m.sector in EXCLUDED:
        return "pass", "excluded_sector"
    if m.portfolio and PORTFOLIO_STATUS[m.portfolio] == "active":
        return "pass", "portfolio_conflict"
    if m.sector not in THESIS:
        return "pass", "outside_thesis"
    exit_ok = qualifying_exit(f)
    if not f.must_have:
        return ("meeting", "repeat_founder") if exit_ok else ("pass", "thesis_requirement_missing")
    if exit_ok:
        return "fast_track", "repeat_founder_exit"
    if f.stage == "pre-seed":
        return "meeting", "thesis_fit"
    bar = BARS[m.model][0 if f.stage == "seed" else 1]
    if f.traction >= FAST_MULTIPLE * bar:
        return "fast_track", "strong_traction"
    if f.traction >= bar:
        return "meeting", "thesis_fit"
    if f.intro == "portfolio":
        return "meeting", "portfolio_intro"
    return "pass", "insufficient_traction"


# --------------------------------------------------------------- sampling ---

def _near(r, threshold):
    """A value within about 25% of a threshold, on either side, never exactly on it."""
    while True:
        v = threshold * r.uniform(0.75, 1.3)
        if abs(v - threshold) / threshold > 0.02:
            return v


def sample_market(r):
    u = r.random()
    if u < SHARE_EXCLUDED:
        sector = r.choice(EXCLUDED)
    elif u < SHARE_EXCLUDED + SHARE_OUTSIDE:
        sector = r.choice(OUTSIDE)
    else:
        weights = [1 / (k + 1) ** SECTOR_SKEW for k in range(len(THESIS))]
        sector = r.choices(THESIS, weights=weights)[0]
    options = [m for m in MARKETS if m.sector == sector]
    port = [m for m in options if m.portfolio]
    rest = [m for m in options if not m.portfolio]
    if port and (not rest or r.random() < PORTFOLIO_MARKET_SHARE):
        return r.choice(port)
    return r.choice(rest)


def sample_amount(r, stage):
    if stage == "Series B":
        return round(r.uniform(20, 60), 1)
    lo, hi = STAGE_RANGES[stage]
    if r.random() < 0.07:  # outside its own stage's range, usually just outside
        return round(r.choice([lo * r.uniform(0.5, 0.95), hi * r.uniform(1.05, 1.6)]), 1)
    v = round(r.uniform(lo, hi), 1)
    return min(max(v, lo), hi)


def sample_traction(r, model, stage):
    if stage == "pre-seed":
        v = 0.0 if r.random() < 0.55 else BARS[model][0] * r.uniform(0.05, 0.6)
        return float(round(v, -2 if model == "consumer" else -3))
    bar = BARS[model][0 if stage == "seed" else 1]
    u = r.random()
    if u < NEAR_MISS * 0.6:
        v = _near(r, bar)
    elif u < NEAR_MISS:
        v = _near(r, FAST_MULTIPLE * bar)
    else:
        v = bar * math.exp(r.uniform(math.log(0.08), math.log(7)))
    if model == "consumer":
        return float(round(v, -2) or 100)
    return float(round(v, -3) or 1000)


def sample_facts(r):
    stage = r.choices(["pre-seed", "seed", "Series A", "Series B"], weights=[24, 45, 28, 3])[0]
    city = r.choices([r.choice(US), r.choice(CANADA), r.choice(UK), r.choice(IRELAND), r.choice(OTHER)],
                     weights=[76, 8, 7, 3, 6])[0]
    m = sample_market(r)
    f = Facts(stage=stage, amount_m=sample_amount(r, stage), city=city, market=m.key,
              must_have=r.random() < 0.7)
    u = r.random()
    if u < 0.13:
        f.exit_kind = "cofounder"
        f.exit_value_m = r.choice([12, 20, 30, 38, 45, 48, 55, 60, 75, 90, 120, 180, 300, 650])
    elif u < 0.18:
        f.exit_kind = "employee"
        f.exit_value_m = r.choice([150, 400, 900, 2000])
    elif u < 0.22:
        f.exit_kind = "shutdown"
    f.traction = sample_traction(r, m.model, stage)
    u = r.random()
    if u < 0.10:
        f.intro = "portfolio"
        f.intro_company = r.choice(sorted(PORTFOLIO_STATUS))
    elif u < 0.22:
        f.intro = "other"
    if m.sector == "education":
        f.must_have = m.buyer == "institution"
    if m.sector == "hr_workforce":
        f.must_have = m.buyer == "employer"
    return f


# ------------------------------------------------------------------ text ---

FIRST = ["Maria", "James", "Priya", "Chen", "Fatima", "Diego", "Aisha", "Tom", "Olu", "Sofia", "Kenji", "Rachel",
         "Mateo", "Hannah", "Ibrahim", "Grace", "Luca", "Mei", "Noah", "Zara", "Arjun", "Elena", "Samuel", "Yara",
         "Ben", "Camila", "Dev", "Nina", "Omar", "Lily", "Tariq", "Ingrid", "Kwame", "Rosa", "Felix", "Anya"]
LAST = ["Garcia", "Okafor", "Shah", "Wang", "Haddad", "Rossi", "Kim", "Murphy", "Novak", "Silva", "Tanaka", "Cohen",
        "Mensah", "Patel", "Larsen", "Dubois", "Reyes", "Singh", "Brooks", "Ali", "Moreau", "Nakamura", "Adeyemi"]
NAME_A = ["Brine", "Cobalt", "Fable", "Harbor", "Juniper", "Kestrel", "Lattice", "Marrow", "Nimbus", "Orchard",
          "Pebble", "Quarry", "Ridge", "Saltbox", "Thistle", "Umber", "Vellum", "Wren", "Yarrow", "Zephyr", "Alder",
          "Basalt", "Cinder", "Drift", "Ember", "Flint", "Gable", "Heron", "Iris", "Jetty", "Kiln", "Loam"]
NAME_B = ["works", "ly", "base", "stack", "loop", "field", "line", "path", "grid", "labs", "hq", "wise", "craft",
          "point", "shift", "ware", "io", "bay", "mark", "post"]
OTHER_BACKGROUNDS = ["a former McKinsey consultant", "an ex-Google engineer", "a former product lead at a large bank",
                     "a Stanford computer-science graduate", "a former Amazon operations manager",
                     "an ex-Shopify engineer", "a former Bain consultant", "an MIT mechanical engineer",
                     "a former Deloitte analyst", "a self-taught engineer"]
INDUSTRY_ROLE = {
    "restaurant": ["ran a restaurant group", "was a restaurant general manager", "worked as a line cook and then a restaurant owner"],
    "construction": ["was a general contractor", "ran a drywall subcontracting business", "worked as a construction estimator"],
    "dental": ["was a practising dentist", "managed a group of dental offices", "worked as a dental-practice manager"],
    "legal": ["was a litigator at a small firm", "ran operations at a law firm", "worked as a paralegal and then a lawyer"],
    "bakery": ["owned a bakery", "was a head baker", "ran a wholesale bakery"],
    "butcher": ["ran the family butcher shop", "worked as a butcher", "managed a chain of butcher shops"],
    "trucking": ["ran a small trucking company", "drove long-haul trucks and then ran dispatch", "managed a trucking fleet"],
    "salon": ["owned a hair salon", "worked as a hair stylist", "managed a chain of salons"],
    "veterinary": ["was a veterinarian", "managed veterinary clinics", "worked as a vet tech and clinic manager"],
    "auto repair": ["owned an auto repair garage", "worked as a mechanic", "ran service at a car dealership"],
}


def _company(r):
    while True:
        c = r.choice(NAME_A) + r.choice(NAME_B)
        if c not in PORTFOLIO_STATUS:
            return c.capitalize()


def _money(r, x):
    """$ amounts as founders write them: $210k, $1.4M, $1,400,000."""
    if x >= 1_000_000:
        return r.choice([f"${x / 1e6:.1f}M", f"${x:,.0f}", f"${x / 1e6:.2f} million"]).replace(".0M", "M")
    return r.choice([f"${x / 1e3:.0f}k", f"${x:,.0f}", f"${x / 1e3:.0f}K"])


def _raise(r, amount_m):
    if amount_m >= 1:
        return r.choice([f"${amount_m:g}M", f"${amount_m:g} million", f"${amount_m * 1e6:,.0f}"])
    return r.choice([f"${amount_m * 1000:.0f}k", f"${amount_m * 1e6:,.0f}"])


def _count(r, n):
    return r.choice([f"{n:,.0f}", f"{n / 1000:.1f}k".replace(".0k", "k")]) if n >= 1000 else f"{n:.0f}"


def traction_sentence(r, f, m):
    if f.traction == 0:
        return r.choice(["We are pre-revenue.", "We're pre-launch, with a waitlist.", "No revenue yet; we launch next quarter."])
    if m.model == "b2b":
        x = _money(r, f.traction)
        return r.choice([f"We're at {x} ARR.", f"Annual recurring revenue is {x}.", f"We have {x} in annual recurring revenue."])
    if m.model == "marketplace":
        x = _money(r, f.traction)
        return r.choice([f"Monthly GMV is {x}.", f"We process {x} a month in gross transaction volume.",
                         f"Gross transaction volume last month was {x}."])
    if m.model == "consumer":
        x = _count(r, f.traction)
        return r.choice([f"We have {x} paying subscribers.", f"{x} people pay us every month.", f"Paying subscribers: {x}."])
    x = _money(r, f.traction)
    return r.choice([f"We have {x} in signed contracts and paid pilots.", f"Signed contracts plus paid pilots total {x}.",
                     f"Booked hardware orders and paid pilots come to {x}."])


def must_have_sentences(r, f, m, founder):
    """Sentences for the sector's must-have. Missing ones are often near-misses, not just silence."""
    s, ok = m.sector, f.must_have
    if s == "vertical_software":
        role = r.choice(INDUSTRY_ROLE[m.industry])
        years = r.randint(5, 16) if ok else r.randint(1, 4)
        if ok or r.random() < 0.7:
            return [f"Before this, {founder} {role} for {years} years."]
        return [f"{founder} is {r.choice(OTHER_BACKGROUNDS)}."]
    if s == "fintech_infrastructure":
        if ok:
            return [r.choice(["We've signed a partner-bank agreement with a regional bank.",
                              "We hold our own money transmitter licence.", "Our partner bank agreement is signed."])]
        return [r.choice(["We're in talks with three partner banks.", "We've applied for a money transmitter licence.", ""])]
    if s == "insurtech":
        if ok:
            return [r.choice(["Policies are written by our signed carrier partner, an A-rated insurer.",
                              "We have a signed MGA partner.", "Our licensed carrier partnership is signed."])]
        return [r.choice(["We're in conversations with carriers.", "We plan to find a carrier partner after this round.", ""])]
    if s == "digital_health":
        if ok:
            return [r.choice([f"My co-founder is a practising cardiologist (MD).", "An RN with 15 years in hospitals is on our founding team.",
                              "A nurse practitioner sits on our board.", "Our CMO is a DO and co-founder."])]
        return [r.choice(["We're advised by a former hospital administrator.", "My co-founder has a PhD in public health.",
                          "We plan to hire a medical director next year.", ""])]
    if s == "medical_devices":
        if ok:
            return [r.choice(["We're pursuing a 510(k) clearance.", "Our regulatory path is De Novo.",
                              "FDA confirmed a 510(k) pathway in our pre-submission meeting."])]
        return [r.choice(["The device will need PMA approval.", "We're still scoping our regulatory path.",
                          "We expect a PMA submission in two years."])]
    if s == "climate_hardware":
        if ok:
            return [r.choice(["We're running a paid pilot with a cement plant.", "A utility is paying for a pilot of our first unit.",
                              "We have a paid pilot at a food-processing plant."])]
        return [r.choice(["We have an unpaid pilot with a university lab.", "A manufacturer signed a letter of intent.",
                          "Our first prototype is running in our own warehouse.", ""])]
    if s == "energy_software":
        if ok:
            return [r.choice(["A municipal utility is a paying customer.", "We're piloting with a regional grid operator.",
                              "Two utilities use the product today."])]
        return [r.choice(["Our customers are commercial building owners.", "We're talking to utilities but none have signed.", ""])]
    if s == "developer_tools":
        stars = r.choice([1200, 2500, 4800, 11000]) if ok else r.choice([150, 400, 700, 950])
        paying = r.randint(10, 60) if ok and r.random() < 0.4 else r.randint(0, 9)
        parts = [f"The open-source project has {stars:,} GitHub stars."]
        if paying:
            parts.append(f"{paying} companies pay for the hosted version.")
        return parts
    if s == "ai_applications":
        if ok:
            return [r.choice(["We have an exclusive data partnership covering 4M records.", "The product is trained on our proprietary dataset.",
                              "A large association gives us exclusive access to its member data."])]
        return [r.choice(["We build on top of the leading frontier models.", "The models are fine-tuned on public data.", ""])]
    if s == "ai_infrastructure":
        n = r.randint(3, 9) if ok else r.randint(1, 2)
        word = "paying enterprise design partners" if n > 1 else "paying enterprise design partner"
        if not ok and r.random() < 0.4:
            return [f"We have {r.randint(3, 8)} enterprise design partners on free pilots."]
        return [f"We have {n} {word}."]
    if s == "cybersecurity":
        years = r.randint(3, 12) if ok else r.randint(1, 2)
        team = r.choice(["on the security team at a large bank", "in the U.S. Army cyber command", "on a big tech company's red team",
                         "at a national cybersecurity agency"])
        if ok or r.random() < 0.7:
            return [f"{founder} spent {years} years {team}."]
        return [f"{founder} is {r.choice(OTHER_BACKGROUNDS)}."]
    if s == "supply_chain":
        if ok:
            rev = r.choice([120, 250, 400, 900, 2000])
            rev_s = f"${rev / 1000:g}B" if rev >= 1000 else f"${rev}M"
            return [f"Customers include a distributor with {rev_s} in annual revenue."]
        rev = r.choice([15, 30, 60, 85])
        return [f"Our largest customer has about ${rev}M in annual revenue."]
    if s == "robotics":
        if ok:
            return [r.choice(["Units are deployed at two paying customers.", "Twelve robots are working at a paying customer's site.",
                              "Our first paying customer has had units deployed since spring."])]
        return [r.choice(["Units are in an unpaid trial with a farm.", "We're at the prototype stage.", ""])]
    if s == "food_agtech":
        if ok:
            return [r.choice(["We've signed a distribution agreement with a farm-supply distributor.",
                              "A regional grocery chain signed a retail agreement with us.", "Our distribution agreement is signed."])]
        return [r.choice(["We're in talks with grocery chains.", "We sell at farmers' markets for now.", ""])]
    return [""]  # education, HR: decided by the buyer, already in the product sentence


def exit_sentence(r, f, who):
    co = _company(r)
    if f.exit_kind == "cofounder":
        how = r.choice(["acquired", "bought by a public software company", "acquired by a private-equity firm"])
        if f.exit_value_m >= 300 and r.random() < 0.3:
            return f"{who} previously co-founded {co}, which went public at a ${f.exit_value_m}M valuation."
        return f"{who} previously co-founded {co}, {how} for ${f.exit_value_m}M."
    if f.exit_kind == "employee":
        return f"{who} was an early employee at {co}, which was acquired for ${f.exit_value_m / 1000:g}B." \
            if f.exit_value_m >= 1000 else f"{who} was employee #8 at {co}, acquired for ${f.exit_value_m}M."
    if f.exit_kind == "shutdown":
        return f"{who} previously founded {co}, which shut down in 2023."
    return ""


def intro_sentence(r, f):
    if f.intro == "portfolio":
        p = f"{r.choice(FIRST)} {r.choice(LAST)}"
        return r.choice([f"{p}, the founder of {f.intro_company}, suggested I reach out.",
                         f"{f.intro_company}'s founder, {p}, introduced us."])
    if f.intro == "other":
        return r.choice(["An angel investor in our round suggested we reach out.", "Our advisor, a former VP at Salesforce, introduced us.",
                         "One of your LPs suggested I send this.", "A partner at another fund pointed me your way."])
    return r.choice(["", "", "I found you through your website.", "Cold email, but I think we're a fit."])


def write_pitch(r, f):
    m = MARKET[f.market]
    founder = f"{r.choice(FIRST)} {r.choice(LAST)}"
    company = _company(r)
    first = founder.split()[0]
    who = r.choice(["I", f"My co-founder {r.choice(FIRST)}"])
    stage_word = f.stage
    raise_s = _raise(r, f.amount_m)
    product = r.choice(m.phrases)
    hq = r.choice([
        f"We're based in {f.city}.", f"{company} is headquartered in {f.city}.", f"HQ: {f.city}.",
        f"We're headquartered in {f.city}; the founders are originally from {r.choice(ORIGINS)}.",
    ])
    intro_line = r.choice([
        f"I'm {founder}, CEO of {company}. We're raising a {raise_s} {stage_word} round.",
        f"{company} is raising {raise_s} ({stage_word}).",
        f"We're {company}, and we're raising a {raise_s} {stage_word}.",
        f"{founder} here, from {company}. We're out raising our {stage_word}: {raise_s}.",
    ])
    product_line = r.choice([f"We build {product}.", f"{company} offers {product}.", f"What we do: {product}.",
                             f"In one line: {product}."])
    body = [hq, product_line]
    body += [x for x in must_have_sentences(r, f, m, first if r.random() < 0.5 else "our CEO") if x]
    ex = exit_sentence(r, f, who)
    if ex:
        body.append(ex)
    body.append(traction_sentence(r, f, m))
    middle = body[1:]
    r.shuffle(middle)
    body = [body[0]] + middle if r.random() < 0.5 else middle[:1] + [body[0]] + middle[1:]
    intro = intro_sentence(r, f)
    opener = r.choice(["Hi Bramblewood team,", "Hello,", "Dear Bramblewood partners,", ""])
    closer = r.choice(["Deck attached.", "Would love 20 minutes.", "Happy to send the deck.", f"Thanks, {first}"])
    parts = [opener, intro_line, *body, intro, closer]
    return " ".join(p for p in parts if p)


def generate(r):
    """One labelled pitch: (text, {"decision": ..., "reason": ...}) plus the facts behind it."""
    f = sample_facts(r)
    decision, reason = screen(f)
    return write_pitch(r, f), {"decision": decision, "reason": reason}, f
