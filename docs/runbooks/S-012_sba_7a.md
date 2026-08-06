# Runbook — S-012 · SBA 7(a) & 504 FOIA

**Status:** Deferred (ADR-011). Not blocked on data quality — blocked on access.

## What this source is worth

The only free dataset in existence with **loan-level charge-off amounts for small-business
lending**: ~1.79 million 7(a) loans, ~$517bn, spanning three recessions (early-90s, 2008-09, 2020).
Charge-off ÷ gross approval yields an SME loss-severity distribution with 30+ years of vintages.
Worth returning to.

## The problem

`data.sba.gov` returns **HTTP 404 to every programmatic request** — landing page, direct file URL,
and CKAN-style API paths — while serving its homepage normally and while search engines hold the
same URLs indexed.

Tested 2026-08-05 from two unrelated networks:

| Route | Dev sandbox | GitHub Actions (Virginia, US) |
|---|---|---|
| `/en/dataset/7-a-504-foia` (browser UA) | 404 | 404 |
| `/en/dataset/7-a-504-foia` (polite UA) | 404 | 404 |
| direct CSV download URL | 404 | 404 |
| `/api/3/action/package_show` | 404 | not tested |
| `catalog.data.gov` federal mirror | — | **200** |

**Diagnosis:** a WAF blocking datacenter IP ranges, cloaking the block as 404 rather than 403.
Not geo-blocking (a US Azure IP was blocked). Not user-agent based (browser UA was blocked).

## Routes to try when we return to it

1. **data.gov mirror resource links** — `catalog.data.gov` responds. Query its CKAN API
   (`/api/3/action/package_search?q=SBA+7(a)+FOIA`) for the dataset's resource URLs. If those
   URLs point somewhere other than `data.sba.gov`, we have a clean path. *Try this first — free.*
2. **Residential-proxy fetch service** — Firecrawl, ScrapingBee or Bright Data egress from
   residential IPs rather than datacenter ranges. Costs money, so requires an ADR-008 spend
   proposal. Quarterly refresh means very low volume — likely the cheapest paid tier.
3. **Manual-assist (archetype G)** — the files refresh only quarterly. A human downloads six CSVs
   from a normal browser four times a year and drops them in R2; the parser runs unchanged.
   Zero cost, ~10 minutes per quarter. *Perfectly reasonable for this cadence.*

## Notes for whoever picks this up

- Download **filenames embed an as-of date** that changes each refresh
  (`…asof-250331.csv` → `…asof-251231.csv`). Resource UUIDs are stable; filenames are not.
  Never hardcode a download URL — resolve the resource page each time.
- Six files total: four 7(a) files by decade, two 504 files by twenty-year block.
- A data dictionary XLSX is published alongside them — ingest it too, as parser documentation.
- **Modelling caveat:** the charge-off figure is loss *to the SBA* under its guarantee, not
  lender-level LGD. Document that wherever the gold panel is used.

## Related

- Config: [`config/sources/S-012_sba_7a.yaml`](../../config/sources/S-012_sba_7a.yaml)
- Decision: ADR-011 in [`DECISIONS.md`](../DECISIONS.md)
