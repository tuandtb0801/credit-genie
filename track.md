Agentic credit decision engine: explainable, real-time underwriting across personal loans and BNPL
Personal loan and BNPL underwriting relies on static scorecards, rule trees, and engineering releases, while BNPL decisions must resolve in under two seconds.

**Problem statement**
Personal loan and BNPL underwriting relies on static scorecards, rule trees, and engineering releases, while BNPL decisions must resolve in under two seconds.

**Build direction**
Build an explainable underwriting agent that ingests mock applicant profiles, applies policy rules, returns approve/decline/refer decisions with cited rationale, and demonstrates policy changes without code deployment.

**Expected outcomes**
Reduce personal-loan decision turnaround from hours to under 60 seconds for 80% of applications.
Keep BNPL checkout decisions under two seconds end-to-end including agent reasoning.
Produce plain-language, regulator-defensible decline rationales and decision lineage.
**Data notes**
Bureau data, existing exposures, delinquency history, income documents, affordability data, scorecard rules, and historic decision outcomes.
Mock applicant datasets for 4-5 test cases.
Human override and audit sign-off before policy changes reach production.
