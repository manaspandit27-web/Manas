# Granite Shield Insurance: the first 24 hours

Granite Shield writes personal auto insurance for 1.1 million drivers in the Northeast. It receives about **900 first notices of loss (FNOL) a day** by phone, app and web form. An intake specialist reads each report, classifies it, and routes it: simple claims to a same-day "fast track" payment, routine damage to a standard adjuster, injuries to senior adjusters, and suspicious claims to the Special Investigations Unit (SIU).

**The problem.** Speed drives customer satisfaction, since a claim paid within 24 hours retains the customer at nearly twice the rate of one paid in a week. But routing errors are expensive in both directions: an injury claim sent to fast track can turn into a lawsuit, and the industry estimates **~10% of claims involve some fraud**. Most of it shows up in the two red flags SIU looks for, brand-new policies and late-reported thefts.

**The proposal.** The COO wants straight-through processing for simple claims. Regulators and the General Counsel are wary of sending policyholder data to a third-party AI API. The data-science team proposes **fine-tuning a small NVIDIA Nemotron model in-house** on historical FNOL reports labeled by experienced intake specialists.

**Your job today.** Using 600 labeled FNOL reports (and a noisier version that reflects real labeling quality), fine-tune the model and recommend to the COO whether, and how, to use it. Pay attention to *which* mistakes it makes: are all errors equally costly?
