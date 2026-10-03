# Harvest Table Restaurant Group: the AP inbox

Harvest Table operates 14 restaurants and a commissary kitchen around Boston. Its three-person accounts-payable team processes about **2,200 vendor invoices a month**, almost all arriving as emails with PDFs. For each one a clerk keys in the vendor, invoice number and amount, picks the general-ledger (GL) code, and routes it for approval under the company's approval matrix.

**The problem.** Month-end close takes nine days, partly because of AP backlog. Mis-coded GL entries distort food-cost reporting, the most-watched number in the business, and last year the company paid **$48,000 to a fake "new vendor"** in a classic invoice-fraud scheme because a clerk skipped the vendor-master check.

**The proposal.** The CFO wants to automate AP intake. A generic AI tool was great at pulling the amount off an invoice but had no idea what Harvest Table's GL codes are, or which vendors are approved. The controller suggests **fine-tuning a small NVIDIA Nemotron model on two years of correctly-processed invoices** so it learns the chart of accounts and the approval matrix, and can run inside the company's own cloud account.

**Your job today.** You have 600 processed invoices (and a messier version reflecting real-world clerical errors). Fine-tune the model, measure it field by field, and advise the CFO: which fields can be fully automated, and which must still be checked by a person?
