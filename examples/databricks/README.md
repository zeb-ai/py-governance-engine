# Z-GRC on Databricks

Databricks is where the spend happens and Z-GRC is the system of record
for budgets: usage is measured on Databricks, converted to a dollar cost, and
reported to Z-GRC, which tracks each user's quota and decides when they should
be cut off. When a user runs over budget, Z-GRC's verdict is enforced back on
Databricks by removing their access.

## AI Gateway cost tracker

For LLM traffic routed through a Databricks AI Gateway endpoint, we track cost
per user in dollars. Each user's token usage is priced with the exact same
pricing table and per-token math that Z-GRC's own engine uses, so the numbers
line up with the rest of the platform. Those costs are reported to Z-GRC as
consumed quota, and Z-GRC keeps the running budget for every user - creating the
user automatically the first time it sees them. The moment a user's remaining
quota hits zero, Z-GRC's decision is applied at the gateway by dropping that
user's rate limits to zero, which stops any further spend without touching
anyone else. Run it on a schedule and every cycle re-measures usage and
re-enforces limits.

## Genie cost tracker

For Genie (natural-language SQL), the cost that matters is warehouse compute,
not tokens, so we measure it in DBUs from Databricks' own system tables and turn
that into a dollar cost per user. Those costs feed Z-GRC the same way reported
as quota consumption against each user's budget, with new users onboarded
automatically, so Genie spend is governed by the same budgets and policies as
everything else in Z-GRC. When Z-GRC signals a user is out of budget, that
verdict is enforced by revoking their access to the Genie space. It runs as a
scheduled Databricks job, only doing work when there's new activity and sending
each cost to Z-GRC exactly once.
