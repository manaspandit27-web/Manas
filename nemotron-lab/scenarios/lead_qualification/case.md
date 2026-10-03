# Lumen Analytics: speed-to-lead

Lumen is a $180M-revenue business-intelligence software company. Its website and events generate about **6,000 inbound leads a month**. A team of eight sales development reps (SDRs) reads each inquiry and decides who should own it: an enterprise account executive, an SDR, the self-serve funnel, a reseller partner in Asia-Pacific, the account-management team, or a marketing "nurture" sequence.

**The problem.** Research on B2B sales shows that responding to a hot lead within 5 minutes makes conversion several times more likely than responding within an hour, but Lumen's median response time is **11 hours**. SDRs also spend about 40% of their time on leads that should never reach them (students, job seekers, agencies pitching services), and enterprise AEs complain that SDRs "sit on" big deals.

**The proposal.** The CRO wants an AI model to qualify and route every lead within seconds. A rule-based scoring tool in the CRM was brittle, and a generic chatbot didn't know Lumen's routing rules (for example, that all APAC deals go through partners). RevOps proposes **fine-tuning a small NVIDIA Nemotron model on last year's leads**, as routed by the best-performing SDRs.

**Your job today.** Using 600 routed leads (and a noisier file that reflects how the whole SDR team, not just the best reps, actually routed them), fine-tune the model and advise the CRO. What is it worth to route every lead in seconds? What happens to the model when the sales org is reorganized next year?
