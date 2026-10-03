"""Generate the synthetic datasets for every scenario.

Each scenario samples hidden facts (loyalty tier, delay length, invoice
amount, ...), writes a realistic message that states those facts, and labels
it by applying the company's policy (see scenarios/<name>/policy.md) to the
facts. Labels are therefore always consistent with the policy, which is what
lets a fine-tuned model learn the policy from examples alone.

Usage:  python scripts/generate_data.py          # rewrites scenarios/*/*.csv
"""

import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "scenarios"
N_TRAIN, N_TEST = 600, 100
NOISE_RATE = 0.30  # share of rows in train_noisy.csv with one wrong label

FIRST = ["Maria", "James", "Priya", "Chen", "Fatima", "Diego", "Aisha", "Tom", "Olu", "Sofia",
         "Kenji", "Rachel", "Mateo", "Hannah", "Ibrahim", "Grace", "Luca", "Mei", "Noah", "Zara",
         "Arjun", "Elena", "Samuel", "Yara", "Ben", "Camila", "Dev", "Nina", "Omar", "Lily"]
LAST = ["Garcia", "Okafor", "Shah", "Wang", "Haddad", "Rossi", "Kim", "Murphy", "Novak", "Silva",
        "Tanaka", "Cohen", "Mensah", "Patel", "Larsen", "Dubois", "Reyes", "Singh", "Brooks", "Ali"]
NUM_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
             8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


def name(r):
    return f"{r.choice(FIRST)} {r.choice(LAST)}"


def num(r, n):
    """Write a small number as digits or words."""
    return NUM_WORDS[n] if n in NUM_WORDS and r.random() < 0.4 else str(n)


def money(x, r):
    return f"${x:,.2f}" if r.random() < 0.6 else f"${x:,.0f}" if x == int(x) else f"${x:,.2f}"


def tidy(text):
    return " ".join(text.split())


# ---------------------------------------------------------------- airline ---

CITIES = ["Boston", "Chicago", "Denver", "Atlanta", "Seattle", "Miami", "Dallas", "Newark",
          "Phoenix", "Toronto", "London", "Mexico City", "Austin", "Orlando"]


def airline(r):
    issue = r.choices(
        ["delay", "cancellation", "baggage", "refund", "booking_change", "staff",
         "accessibility", "other"],
        weights=[22, 12, 14, 10, 10, 8, 8, 8])[0]
    tier = r.choices(["none", "Silver", "Gold", "Platinum"], weights=[55, 15, 18, 12])[0]
    hours = r.choice([1, 2, 2, 3, 4, 4, 5, 6, 7, 8, 9]) if issue == "delay" else 0
    flight = f"SK{r.randint(100, 2999)}"
    a, b = r.sample(CITIES, 2)
    who = name(r)

    tier_line = "" if tier == "none" else r.choice([
        f"I'm a Skyward {tier} member.",
        f"As a {tier} member of Skyward Miles, I expected better.",
        f"I have held {tier} status with you for {num(r, r.randint(2, 9))} years.",
        f"({tier} member, by the way.)",
        f"My Skyward Miles tier is {tier}.",
    ])
    trip = r.choice([f"flight {flight} from {a} to {b}", f"{flight} ({a} to {b})",
                     f"my {a}-{b} flight, {flight}"])

    if issue == "delay":
        h = num(r, hours)
        body = r.choice([
            f"My {trip} was delayed by {h} hours and nobody at the gate could tell us why.",
            f"We sat at the gate for {h} hours waiting for {trip}. Zero updates.",
            f"{trip} left {h} hours late. I missed a client dinner because of it.",
            f"Your app kept pushing back {trip} until it finally departed {h} hours behind schedule.",
            f"A {hours}-hour delay on {trip} is unacceptable. My whole day was ruined.",
        ])
    elif issue == "cancellation":
        body = r.choice([
            f"You cancelled {trip} the night before and rebooked me two days later.",
            f"{trip} was cancelled at the gate. I had to buy a ticket on another airline.",
            f"I got a text at 5am that {trip} was cancelled. No alternatives offered.",
            f"Cancelling {trip} with no explanation left my family stranded in {a}.",
        ])
    elif issue == "baggage":
        body = r.choice([
            f"My checked bag never arrived after {trip}. It has been {num(r, r.randint(2, 6))} days.",
            f"My suitcase came off {trip} with a broken handle and a cracked shell.",
            f"You lost my luggage on {trip}. All my work clothes are in it.",
            f"The stroller we gate-checked on {trip} came back bent and unusable.",
        ])
    elif issue == "refund":
        body = r.choice([
            f"I cancelled my ticket for {trip} within 24 hours and still have not been refunded.",
            f"I want my money back for {trip}. I paid for a seat I never got to use.",
            f"Please refund the $89 seat upgrade on {trip} that I was charged twice for.",
            f"I was promised a refund for {trip} {num(r, r.randint(3, 8))} weeks ago. Still nothing.",
        ])
    elif issue == "booking_change":
        body = r.choice([
            f"I need to move {trip} to the following Tuesday. The website keeps erroring out.",
            f"How do I change the name on my booking for {trip}? My ticket has a typo.",
            f"Can I switch {trip} to an earlier departure? I can't find the option online.",
            f"I'd like to add my daughter to my reservation on {trip}.",
        ])
    elif issue == "staff":
        body = r.choice([
            f"The gate agent for {trip} was rude and yelled at my elderly father.",
            f"A flight attendant on {trip} mocked me in front of other passengers.",
            f"The check-in staff for {trip} refused to help and rolled their eyes at me.",
            f"I was treated with real hostility by a crew member on {trip}.",
        ])
    elif issue == "accessibility":
        body = r.choice([
            f"I booked wheelchair assistance for {trip} and nobody showed up. I had to crawl down the jet bridge.",
            f"My service dog was refused boarding on {trip} even though I had all the paperwork.",
            f"I am deaf and no one told me the gate for {trip} had changed. I nearly missed it.",
            f"The aisle chair I requested for {trip} was never brought to the aircraft.",
        ])
    else:
        body = r.choice([
            f"The wifi on {trip} didn't work at all even though I paid for it.",
            f"The food on {trip} was cold and the seat-back screen was broken.",
            f"Your new boarding process is confusing. I saw it on {trip}.",
            f"The cabin on {trip} was filthy. Crumbs everywhere and a sticky tray table.",
        ])

    opener = r.choice(["", "Hello,", "Hi Skyward,", "To whom it may concern,", "Hey,", "Dear Customer Care,", ""])
    closer = r.choice(["", "Please fix this.", "I expect a response.", f"- {who}", f"Thanks, {who.split()[0]}",
                       "Very disappointed.", "What are you going to do about it?", ""])
    parts = [opener, body, tier_line, closer] if r.random() < 0.5 else [opener, tier_line, body, closer]
    text = tidy(" ".join(parts))

    category = {"delay": "flight_delay", "cancellation": "cancellation", "baggage": "baggage",
                "refund": "refund_request", "booking_change": "booking_change",
                "staff": "staff_conduct", "accessibility": "accessibility", "other": "other"}[issue]
    if category in ("accessibility", "staff_conduct") or tier == "Platinum":
        priority = "P1"
    elif tier == "Gold" or category == "cancellation" or hours >= 3:
        priority = "P2"
    else:
        priority = "P3"
    route = {"baggage": "baggage_services", "accessibility": "accessibility_desk",
             "staff_conduct": "customer_relations", "refund_request": "refunds"}.get(category, "customer_care")
    if category == "cancellation" or hours >= 6:
        comp = "voucher_250"
    elif hours >= 3:
        comp = "voucher_100"
    elif category == "refund_request":
        comp = "refund_review"
    else:
        comp = "none"
    return text, {"category": category, "priority": priority, "route_to": route, "compensation": comp}


# ---------------------------------------------------------------- invoices ---

APPROVED = {  # vendor -> goods category (the approved vendor master list)
    "Green Valley Produce": "produce", "Sunrise Farms Co-op": "produce",
    "Hilltop Creamery": "dairy", "Bay State Dairy": "dairy",
    "Atlantic Catch Seafood": "meat_seafood", "Prime Cut Meats": "meat_seafood",
    "CleanPro Supply": "cleaning", "Metro Linen Service": "linens",
    "KitchenTech Repair": "repair",
}
NEW_VENDORS = ["Rivera Family Farms", "Northshore Fish Market", "Sparkle Janitorial", "Blue Ox Butchers",
               "Coastal Linen Partners", "FixIt Appliance Pros", "Golden Meadow Dairy", "Urban Greens LLC",
               "Ace Restaurant Services", "Pinecrest Provisions"]
GOODS = {
    "produce": ["romaine, heirloom tomatoes and fresh herbs", "this week's citrus and stone fruit",
                "organic baby spinach and root vegetables", "avocados, limes and cilantro"],
    "dairy": ["heavy cream, butter and cultured yogurt", "the weekly cheese order", "whole milk and creme fraiche",
              "mozzarella and ricotta for the pizza line"],
    "meat_seafood": ["dry-aged ribeyes and short rib", "fresh cod, scallops and littleneck clams",
                     "chicken thighs and pork shoulder", "salmon fillets and shrimp"],
    "cleaning": ["degreaser, sanitizer and floor cleaner", "dish machine detergent and rinse aid",
                 "nitrile gloves and trash liners", "the monthly chemical restock"],
    "linens": ["napkin and tablecloth service", "chef coats and aprons laundering", "bar towels and linens rental"],
    "repair": ["repair of the walk-in cooler compressor", "service call on the combi oven", "fryer thermostat replacement",
               "emergency dishwasher repair"],
}
GL = {"produce": "5100", "dairy": "5110", "meat_seafood": "5120", "cleaning": "6200", "linens": "6400", "repair": "6300"}
LOCATIONS = ["the Back Bay location", "your Cambridge restaurant", "the Seaport kitchen", "Harvest Table Somerville",
             "the commissary kitchen", "your Brookline site"]


def invoices(r):
    if r.random() < 0.7:
        vendor = r.choice(list(APPROVED))
        cat = APPROVED[vendor]
    else:
        vendor = r.choice(NEW_VENDORS)
        cat = r.choice(list(GOODS))
    band = r.choices(["small", "mid", "large"], weights=[45, 35, 20])[0]
    lo, hi = {"small": (180, 2200), "mid": (2900, 9200), "large": (11000, 42000)}[band]
    amount = round(r.uniform(lo, hi), 2) if r.random() < 0.7 else float(r.randint(lo, hi))
    inv = r.choice([f"INV-{r.randint(10000, 99999)}", f"{r.randint(100000, 999999)}",
                    f"HT-{r.randint(1000, 9999)}-{r.choice('ABCDE')}", f"{r.choice(['A', 'B', 'C'])}{r.randint(1000, 9999)}"])
    terms = r.choice(["Net 30", "Net 15", "due on receipt", "Net 45", "2/10 Net 30"])
    who = name(r)
    goods = r.choice(GOODS[cat])
    loc = r.choice(LOCATIONS)
    amt = money(amount, r)

    body = r.choice([
        f"Please find attached invoice {inv} for {goods} delivered to {loc}. Total due: {amt}, terms {terms}.",
        f"Invoice #{inv} is attached for {goods} ({loc}). Amount: {amt}. Payment terms: {terms}.",
        f"Attached is our invoice {inv} totaling {amt} for {goods}. This covers the delivery to {loc}. Terms are {terms}.",
        f"We are writing to submit invoice no. {inv} in the amount of {amt} for {goods} at {loc}, payable {terms}.",
        f"Reminder: invoice {inv} ({amt}) for {goods} to {loc} has been issued. Terms {terms}. Thank you for your business.",
    ])
    opener = r.choice(["Hi Harvest Table AP team,", "Hello,", "Good morning,", "Dear Accounts Payable,", ""])
    sign = r.choice([f"Best, {who}, Accounts Receivable, {vendor}", f"Thanks, {who} | {vendor}",
                     f"{vendor} Billing Dept.", f"Regards,\n{who}\n{vendor}"])
    text = tidy(f"{opener} {body} {sign}")

    if vendor not in APPROVED:
        approval = "hold_new_vendor"
    elif amount >= 10000:
        approval = "cfo"
    elif amount >= 2500:
        approval = "manager"
    else:
        approval = "auto_approve"
    return text, {"vendor": vendor, "invoice_number": inv, "amount_usd": f"{amount:.2f}",
                  "gl_code": GL[cat], "approval": approval}


# ------------------------------------------------------------------ claims ---

def claims(r):
    ctype = r.choices(["collision", "theft", "glass", "weather", "vandalism"], weights=[40, 15, 15, 15, 15])[0]
    injury = ctype == "collision" and r.random() < 0.35
    band = r.choices(["under_2k", "2k_to_10k", "over_10k"], weights=[35, 45, 20])[0]
    if ctype == "glass":
        band = "under_2k"
    lo, hi = {"under_2k": (250, 1700), "2k_to_10k": (2600, 9200), "over_10k": (11500, 45000)}[band]
    est = r.randint(lo // 50, hi // 50) * 50
    delay = r.choice([0, 1, 1, 2, 3, 4, 5, 10, 12, 14, 21])  # days between incident and report
    new_policy = r.random() < 0.15
    policy_days = r.choice([5, 9, 12, 16, 20]) if new_policy else None
    car = r.choice(["2019 Honda CR-V", "2022 Toyota Camry", "2017 Ford F-150", "2021 Tesla Model 3",
                    "2015 Subaru Outback", "2020 Hyundai Tucson", "2018 Jeep Wrangler", "2023 Kia Telluride"])
    when = {0: "this morning", 1: "yesterday"}.get(delay, f"{num(r, delay) if delay <= 12 else delay} days ago")
    if delay == 14:
        when = r.choice(["two weeks ago", "14 days ago"])
    if delay == 21:
        when = r.choice(["three weeks ago", "21 days ago"])

    if ctype == "collision":
        what = r.choice([
            f"I was rear-ended at a red light {when} in my {car}.",
            f"{when.capitalize()} another driver ran a stop sign and T-boned my {car}.",
            f"I slid into a guardrail {when} and the front of my {car} is crushed.",
            f"Someone merged into my lane on the highway {when} and sideswiped my {car}.",
        ])
    elif ctype == "theft":
        what = r.choice([
            f"My {car} was stolen from my driveway {when}.",
            f"I came out of work {when} and my {car} was gone. Police report filed.",
            f"Someone broke in and drove off with my {car} {when}.",
        ])
    elif ctype == "glass":
        what = r.choice([
            f"A rock hit my windshield on the highway {when} and it cracked across the driver's side.",
            f"My rear window on the {car} shattered {when}, no other damage.",
            f"{when.capitalize()} a stone chipped my windshield and the crack is spreading.",
        ])
    elif ctype == "weather":
        what = r.choice([
            f"Hail dented the hood and roof of my {car} {when}.",
            f"A tree branch fell on my {car} during the storm {when}.",
            f"My {car} was sitting in a flooded parking lot {when} and water got inside.",
        ])
    else:
        what = r.choice([
            f"Someone keyed both sides of my {car} {when}.",
            f"My tires were slashed and mirrors smashed {when} while parked on the street.",
            f"Vandals spray-painted my {car} {when}.",
        ])

    if ctype == "collision":
        hurt = r.choice([
            "My neck and back are hurting and I went to urgent care.",
            "My passenger broke her wrist and was taken to the ER.",
            "I hit my head on the steering wheel and an ambulance took me to the hospital.",
            "The other driver complained of chest pain and was taken away by ambulance.",
        ]) if injury else r.choice(["Nobody was hurt.", "No injuries, thankfully.", "Everyone is fine.", ""])
    else:
        hurt = ""

    estimate = r.choice([f"The body shop quoted ${est:,}.", f"Repair estimate is about ${est:,}.",
                         f"I'd guess the damage is around ${est:,}.", f"The shop says roughly ${est:,} to fix."])
    if ctype == "theft":
        estimate = r.choice([f"The car is worth about ${est:,}.", f"Kelley Blue Book value is around ${est:,}."])

    if new_policy:
        tenure = r.choice([f"I just took out this policy {policy_days} days ago.",
                           f"My Granite Shield policy started {policy_days} days ago.",
                           f"I only switched to Granite Shield {policy_days} days ago."])
    else:
        tenure = r.choice(["", "", f"I've been a Granite Shield customer for {num(r, r.randint(1, 12))} years.",
                           f"Customer since {r.randint(2008, 2024)}.", ""])
    who = name(r)
    style = r.random()
    if style < 0.5:
        text = f"{what} {hurt} {estimate} {tenure} Policyholder: {who}."
    else:
        text = (f"FNOL call notes - insured {who}. " + what.replace("I ", "Insured ").replace("my ", "their ")
                .replace("My ", "Their ") + f" {hurt} {estimate} {tenure}")
    text = tidy(text)

    if (ctype == "theft" and delay > 7) or new_policy:
        route = "special_investigations"
    elif injury:
        route = "senior_adjuster"
    elif ctype == "glass" or band == "under_2k":
        route = "fast_track"
    else:
        route = "standard_adjuster"
    return text, {"claim_type": ctype, "injury": "yes" if injury else "no", "estimate_band": band, "route": route}


# ---------------------------------------------------------------- expenses ---

PRICEY = ["New York", "San Francisco", "Boston", "London"]
OTHER_CITIES = ["Chicago", "Dallas", "Denver", "Atlanta", "Columbus", "Charlotte", "Minneapolis", "Phoenix"]


def expenses(r):
    kind = r.choices(["meal", "client_meal", "lodging", "airfare", "ground", "supplies", "personal"],
                     weights=[18, 16, 18, 16, 14, 8, 10])[0]
    receipt = r.random() < 0.8
    city = r.choice(PRICEY + OTHER_CITIES)
    over = r.random() < 0.3
    reason, decision = "within_policy", "approve"
    rcpt = r.choice(["Receipt attached.", "Receipt uploaded.", "(receipt attached)"]) if receipt else \
        r.choice(["Lost the receipt.", "No receipt - the restaurant's printer was down.", "Receipt to follow.",
                  "I don't have a receipt for this one."])

    if kind in ("meal", "client_meal"):
        people = r.randint(1, 4) if kind == "meal" else r.randint(2, 6)
        limit = 75 if kind == "meal" else 125
        pp = r.uniform(limit * 1.3, limit * 2.2) if over else r.uniform(limit * 0.2, limit * 0.8)
        amount = round(pp * people, 2)
        place = r.choice(["Oleana", "the hotel restaurant", "Shake Shack", "a sushi place near the office",
                          "Capital Grille", "an Italian spot downtown", "the airport Chili's"])
        if kind == "meal":
            ppl = "just me" if people == 1 else f"{num(r, people)} of us from the team"
            text = f"Team dinner at {place} in {city}, {ppl}, total {money(amount, r)}. {rcpt}" if people > 1 else \
                f"Dinner at {place} in {city}, {ppl}, {money(amount, r)}. {rcpt}"
        else:
            client = r.choice(["Acme Corp", "Northbridge Health", "Vantage Retail", "Halcyon Energy", "Orbit Bank"])
            text = r.choice([
                f"Client dinner with {client} at {place}, {city}. {num(r, people).capitalize()} attendees total. {money(amount, r)}. {rcpt}",
                f"Business meal with the {client} team ({people} people incl. me) at {place} - {money(amount, r)}. {rcpt}",
            ])
        etype = "meals"
        if over:
            reason, decision = "over_limit", "needs_manager"
    elif kind == "lodging":
        nights = r.randint(1, 5)
        limit = 450 if city in PRICEY else 300
        rate = r.uniform(limit * 1.2, limit * 1.6) if over else r.uniform(limit * 0.45, limit * 0.85)
        rate = round(rate)
        hotel = r.choice(["Marriott", "Hilton Garden Inn", "Hyatt Regency", "Four Seasons", "Hampton Inn", "Westin"])
        text = r.choice([
            f"{hotel} {city}, {num(r, nights)} night{'s' if nights > 1 else ''} at ${rate}/night, total ${rate * nights:,}. {rcpt}",
            f"Hotel for the {city} engagement: {hotel}, ${rate} per night x {nights}. {rcpt}",
        ])
        etype = "lodging"
        if over:
            reason, decision = "over_limit", "needs_manager"
    elif kind == "airfare":
        hours = r.choice([1, 2, 2, 3, 4, 5, 7, 8, 11, 13])
        cls = r.choices(["economy", "premium economy", "business"], weights=[50, 10, 40])[0]
        price = r.randint(180, 900) if cls == "economy" else r.randint(700, 6500)
        dest = r.choice(PRICEY + OTHER_CITIES + ["Tokyo", "Sao Paulo", "Singapore", "Frankfurt"])
        text = r.choice([
            f"Flight to {dest} for client kickoff, {cls} class, {num(r, hours)}-hour flight, ${price:,}. {rcpt}",
            f"Airfare: {cls} seat, {hours} hrs flight time, ${price:,} round trip to {dest}. {rcpt}",
        ])
        etype = "airfare"
        if cls == "business" and hours < 6:
            reason, decision = "class_of_service", "reject"
    elif kind == "ground":
        amt = round(r.uniform(170, 320), 2) if over else round(r.uniform(14, 120), 2)
        how = r.choice(["Uber", "Lyft", "taxi", "car service", "rental car"])
        text = r.choice([
            f"{how.capitalize()} from the airport to the client site in {city}, {money(amt, r)}. {rcpt}",
            f"{how.capitalize()} to {city} office - {money(amt, r)}. {rcpt}",
        ])
        etype = "ground_transport"
        if over:
            reason, decision = "over_limit", "needs_manager"
        amount = amt
    elif kind == "supplies":
        amt = round(r.uniform(230, 600), 2) if over else round(r.uniform(12, 170), 2)
        item = r.choice(["printer toner and paper", "a portable monitor", "flip charts and markers for a workshop",
                         "a USB-C dock", "notebooks and sticky notes"])
        text = f"Bought {item} for the project team, {money(amt, r)}. {rcpt}"
        etype = "office_supplies"
        if over:
            reason, decision = "over_limit", "needs_manager"
        amount = amt
    else:
        amt = round(r.uniform(18, 260), 2)
        item = r.choice(["Hotel minibar and in-room movie", "Spa treatment at the hotel", "Bar tab after the offsite (drinks only)",
                         "Celtics tickets for me and my partner", "Gym day pass", "Netflix subscription while traveling"])
        text = f"{item}, {city}, {money(amt, r)}. {rcpt}"
        etype = "entertainment"
        reason, decision = "non_reimbursable", "reject"
        amount = amt

    if decision != "reject":
        amt_val = amount if kind not in ("lodging", "airfare") else 999
        if not receipt and amt_val > 25:
            reason, decision = "missing_receipt", "needs_receipt"
    who = name(r)
    text = tidy(r.choice([f"{text}", f"{who}: {text}", f"Expense line - {text}", f"{text} Submitted by {who}."]))
    return text, {"expense_type": etype, "decision": decision, "reason": reason}


# ------------------------------------------------------------------- leads ---

COMPANIES = ["Brightwater Logistics", "Cobalt Health", "Fernhill Foods", "Quarry Capital", "Nimbus Retail",
             "Tidewater Energy", "Pelican Insurance", "Sable Manufacturing", "Juniper Schools", "Atlas Freight",
             "Marlow Hotels", "Redwood Biotech", "Ivory Media", "Keystone Credit Union", "Harbor Pharma"]
REGIONS = {"na": ["Chicago", "Toronto", "Austin", "Atlanta", "Boston", "Seattle"],
           "emea": ["London", "Berlin", "Paris", "Dubai", "Madrid", "Amsterdam"],
           "apac": ["Singapore", "Sydney", "Tokyo", "Mumbai", "Seoul", "Jakarta"]}


def leads(r):
    kind = r.choices(["prospect", "customer", "student", "job", "vendor"], weights=[76, 10, 5, 4, 5])[0]
    region = r.choices(["na", "emea", "apac"], weights=[50, 30, 20])[0]
    city = r.choice(REGIONS[region])
    seg = r.choices(["smb", "mid_market", "enterprise"], weights=[35, 35, 30])[0]
    emp = {"smb": r.choice([12, 25, 40, 60, 85, 120]), "mid_market": r.choice([300, 450, 600, 900, 1200, 1500]),
           "enterprise": r.choice([2800, 4000, 6500, 12000, 25000, 60000])}[seg]
    intent = r.choices(["high", "medium", "low"], weights=[35, 35, 30])[0]
    co = r.choice(COMPANIES)
    who = name(r)
    title = r.choice(["VP of Operations", "Head of Data", "Director of Finance", "CFO", "Analytics Manager",
                      "COO", "Senior Analyst", "Chief Digital Officer"])
    size = r.choice([f"about {emp:,} employees", f"~{emp:,} people", f"{emp:,} staff", f"a company of {emp:,}"])
    if emp < 100 and r.random() < 0.5:
        size = r.choice([f"a team of {emp}", f"just {emp} of us"])

    want = {
        "high": [f"We'd like a demo and pricing - budget is approved for this quarter.",
                 f"Can we get a demo next week? We need to pick a vendor by end of month.",
                 f"Please send pricing for {r.randint(20, 400)} seats; we're ready to sign if it fits.",
                 f"We have an RFP going out in two weeks and want Lumen in it. Can someone call me?"],
        "medium": ["We're comparing a few analytics platforms. How does Lumen differ from Tableau?",
                   "Does Lumen integrate with Snowflake and Salesforce?",
                   "Exploring options for next year's planning. What are typical implementation timelines?",
                   "Curious about your forecasting features - do you have case studies in our industry?"],
        "low": ["Downloaded your e-book on dashboards. Just browsing for now.",
                "Signing up for the newsletter.",
                "Not looking to buy anything, just wanted to see the webinar recording.",
                "Interested in the free template pack."],
    }[intent]
    msg = r.choice(want)

    if kind == "prospect":
        text = r.choice([
            f"Hi, I'm {who}, {title} at {co} ({size}, based in {city}). {msg}",
            f"{who} here from {co} in {city}. We're {size}. {msg}",
            f"Web form - Name: {who}. Company: {co}. Title: {title}. Location: {city}. Size: {size}. Message: {msg}",
        ])
    elif kind == "customer":
        text = r.choice([
            f"Hi, {who} from {co} in {city} - we're already a Lumen customer ({size}). {msg}",
            f"We've used Lumen for {num(r, r.randint(1, 5))} years at {co} ({size}, {city}). {msg}",
        ])
    elif kind == "student":
        text = r.choice([f"Hi! I'm an MBA student in {city} writing a paper on BI tools. Could I interview someone? {msg}",
                         f"University student here working on a class project about analytics vendors. {msg}"])
    elif kind == "job":
        text = r.choice([f"Hello, I'm {who}, a data analyst in {city}. Are you hiring? I'd love to join Lumen.",
                         f"I saw a job posting for a solutions engineer - who should I send my resume to? ({city})"])
    else:
        text = r.choice([f"Hi, I run partnerships at an SEO agency in {city}. We can triple your inbound leads - quick call?",
                         f"{who} from a cloud reseller in {city}. We'd like to sell you our data-labeling services."])
    text = tidy(text)

    if kind in ("student", "job", "vendor"):
        segment = "unknown"
        route, intent = "disqualify", "low"
    else:
        segment = seg
        if kind == "customer":
            route = "account_management"
        elif region == "apac":
            route = "partner_channel"
        elif intent == "low":
            route = "nurture"
        elif seg == "smb":
            route = "self_serve"
        elif seg == "enterprise" and intent == "high":
            route = "enterprise_ae"
        else:
            route = "sdr"
    return text, {"segment": segment, "intent": intent, "route": route}


# ------------------------------------------------------------------ driver ---

GENERATORS = {
    "airline_complaints": airline,
    "invoice_intake": invoices,
    "claims_triage": claims,
    "expense_audit": expenses,
    "lead_qualification": leads,
}
# Free-text fields are never corrupted in the noisy file.
NOISY_SKIP = {"vendor", "invoice_number", "amount_usd"}


def build(name, gen, seed):
    r = random.Random(seed)
    seen, rows = set(), []
    while len(rows) < N_TRAIN + N_TEST:
        text, out = gen(r)
        if text in seen:
            continue
        seen.add(text)
        rows.append({"input": text, **out})
    train, test = rows[:N_TRAIN], rows[N_TRAIN:]
    for i, row in enumerate(train):
        row["id"] = f"{name[:3]}-tr-{i:04d}"
    for i, row in enumerate(test):
        row["id"] = f"{name[:3]}-te-{i:04d}"

    fields = [k for k in train[0] if k not in ("id", "input")]
    values = {f: sorted({row[f] for row in rows}) for f in fields}
    noisy = []
    nr = random.Random(seed + 1)
    for row in train:
        row = dict(row)
        if nr.random() < NOISE_RATE:
            f = nr.choice([f for f in fields if f not in NOISY_SKIP])
            row[f] = nr.choice([v for v in values[f] if v != row[f]])
        noisy.append(row)

    out_dir = ROOT / name
    out_dir.mkdir(parents=True, exist_ok=True)
    cols = ["id", "input"] + fields
    for fname, data in [("train.csv", train), ("test.csv", test), ("train_noisy.csv", noisy)]:
        with open(out_dir / fname, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(data)
    print(f"{name:20s} train={len(train)} test={len(test)} fields={fields}")


if __name__ == "__main__":
    for i, (n, g) in enumerate(GENERATORS.items()):
        build(n, g, seed=1000 + i)
