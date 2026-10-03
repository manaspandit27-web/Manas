# Skyward Airways: 4,000 complaints a day

Skyward is a mid-size U.S. carrier with 310 aircraft and a loyal, but restless, frequent-flyer base. Its Customer Care center receives about **4,000 written complaints a day** across email, chat, and social media. Today, 140 Tier-1 agents read each message, tag it, set a priority, route it to one of five teams, and decide whether the customer is owed a travel voucher under the published compensation policy.

**The problem.** It takes an agent ~3 minutes to triage a message, at a loaded cost of about $0.90 per complaint. Worse, a 2025 internal audit found that **18% of complaints were mis-triaged**: Platinum flyers waited days in the routine queue, accessibility failures (a regulatory risk with the DOT) were mis-routed, and agents handed out vouchers inconsistently, costing an estimated $6M per year in over-compensation.

**The proposal.** The VP of Customer Experience wants an AI model to do first-pass triage, with agents reviewing only the hard cases. An off-the-shelf chatbot did well at summarizing complaints but kept inventing priority levels and voucher amounts. The CIO argues that Skyward should **fine-tune a small open model (NVIDIA Nemotron) on its own historical, correctly-triaged complaints** so it learns Skyward's rules and can run cheaply on Skyward's own servers, keeping customer data in-house.

**Your job today.** You have 600 historical complaints that senior agents triaged correctly (plus a messier version of the same file that reflects what the data *actually* looks like after years of inconsistent tagging). Decide how much data to use and how clean it needs to be, fine-tune the model, and tell the VP whether it is good enough to deploy, and where a human must stay in the loop.
