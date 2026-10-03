# Meridian Advisory — Travel & Expense Policy (audit rules)

**Expense type** — `meals`, `lodging`, `airfare`, `ground_transport` (taxi, rideshare, rental car), `office_supplies`, `entertainment` (personal entertainment: minibar, movies, spa, sports tickets, gym, drinks-only bar tabs, subscriptions).

**Decision and reason** (first match wins)
1. `reject` / `non_reimbursable` — any `entertainment` expense.
2. `reject` / `class_of_service` — **business class** airfare on a flight **under 6 hours**. (Economy and premium economy are always allowed; business is allowed for flights of 6+ hours.)
3. `needs_receipt` / `missing_receipt` — no receipt for an expense **over $25**. (Lodging and airfare always need a receipt.)
4. `needs_manager` / `over_limit` — over the policy limit:
   - Meals: **$75 per person**; client meals **$125 per person** (total ÷ attendees)
   - Lodging: **$300 per night**, or **$450 per night** in New York, San Francisco, Boston and London
   - Ground transport: **$150** per ride
   - Office supplies: **$200** per purchase
5. `approve` / `within_policy` otherwise.
