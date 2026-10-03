# Skyward Airways — Complaint Triage Policy (internal)

Apply the rules in order. The first rule that matches wins.

**Category** — `flight_delay`, `cancellation`, `baggage` (lost or damaged, incl. strollers), `refund_request`, `booking_change`, `staff_conduct`, `accessibility` (wheelchair, service animal, hearing/vision), `other` (wifi, food, cleanliness, process).

**Priority**
1. `P1` if the category is `accessibility` or `staff_conduct`, **or** the customer is a **Platinum** member.
2. `P2` if the customer is a **Gold** member, **or** the category is `cancellation`, **or** a delay was **3 hours or more**.
3. `P3` otherwise. (Silver status does *not* change priority.)

**Route to**
- `baggage` → `baggage_services`
- `accessibility` → `accessibility_desk`
- `staff_conduct` → `customer_relations`
- `refund_request` → `refunds`
- everything else → `customer_care`

**Compensation**
1. `voucher_250` for any `cancellation`, or a delay of **6 hours or more**.
2. `voucher_100` for a delay of **3–5 hours**.
3. `refund_review` for a `refund_request`.
4. `none` otherwise (baggage is compensated through the baggage claim process, not here).
