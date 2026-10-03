# Harvest Table — Accounts Payable Intake Policy (internal)

**Extraction** — `vendor` (company name as it appears), `invoice_number` (exactly as written, including prefixes like `INV-`), `amount_usd` (total due as a plain number with two decimals, e.g. `1284.60`).

**GL code** — based on *what was purchased*, not who sold it:

| Purchase | GL code |
|---|---|
| Produce (fruit, vegetables, herbs) | `5100` |
| Dairy (milk, cream, butter, cheese, yogurt) | `5110` |
| Meat & seafood | `5120` |
| Cleaning & janitorial supplies, gloves, liners | `6200` |
| Equipment repair & service calls | `6300` |
| Linen & uniform service | `6400` |

**Approval path** (first match wins)
1. `hold_new_vendor` if the vendor is **not** on the approved vendor master list — no payment until Procurement completes vendor setup (fraud control).
2. `cfo` if the amount is **$10,000 or more**.
3. `manager` if the amount is **$2,500 – $9,999.99**.
4. `auto_approve` otherwise.

**Approved vendor master list:** Green Valley Produce, Sunrise Farms Co-op, Hilltop Creamery, Bay State Dairy, Atlantic Catch Seafood, Prime Cut Meats, CleanPro Supply, Metro Linen Service, KitchenTech Repair.
