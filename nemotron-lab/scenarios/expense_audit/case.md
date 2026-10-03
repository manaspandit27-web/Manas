# Meridian Advisory: who audits the auditors?

Meridian is a 2,400-person strategy consulting firm. Consultants travel constantly and file about **35,000 expense lines a month**. A shared-services team in Manila audits a 15% random sample against the travel & expense (T&E) policy; the rest are paid automatically.

**The problem.** The internal-audit team estimates that **4–6% of expense spend is out of policy**: over-limit dinners, business-class seats on short flights, minibar charges. Most of it is never caught, because 85% of lines are never looked at. Consultants also complain that the policy is enforced inconsistently, since the same dinner gets approved one month and flagged the next.

**The proposal.** The CFO would like to audit **100% of lines** automatically and send only exceptions to humans. Expense data includes client names and travel patterns, so Legal prefers a model the firm hosts itself. The proposal is to **fine-tune a small NVIDIA Nemotron model on a year of expense lines that auditors already reviewed**.

**Your job today.** Using 600 audited expense lines (and a noisier file reflecting inconsistent past audits), fine-tune the model and advise the CFO. Can it audit every line? Which policy rules does it learn easily, and which ones (like per-person limits that require arithmetic) does it struggle with? What would you tell consultants about how they are being audited?
