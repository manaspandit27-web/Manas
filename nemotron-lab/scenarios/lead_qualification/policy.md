# Lumen Analytics — Lead Routing Rules (internal)

**Segment** (by employee count) — `smb` (< 200), `mid_market` (200 – 1,999), `enterprise` (2,000+), `unknown` (disqualified leads).

**Intent**
- `high` — asks for a demo, pricing or a call; mentions budget, timeline, RFP or readiness to buy.
- `medium` — comparing vendors, asking about features or integrations, early exploration.
- `low` — content downloads, newsletter, webinar recordings, "just browsing". Disqualified leads are always `low`.

**Route** (first match wins)
1. `disqualify` — students/researchers, job seekers, and vendors or agencies pitching *us*.
2. `account_management` — already a Lumen customer.
3. `partner_channel` — prospect located in **APAC** (Lumen sells in APAC only through resellers).
4. `nurture` — `low` intent (marketing email sequence).
5. `self_serve` — `smb` (credit-card signup flow, no salesperson).
6. `enterprise_ae` — `enterprise` with `high` intent.
7. `sdr` — everything else (a sales development rep qualifies it further).
