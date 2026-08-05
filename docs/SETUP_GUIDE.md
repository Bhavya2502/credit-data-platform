# Setup Guide — Phase 0 Foundations

_Written for a non-technical owner. Every step says what it is, why we need it, what your options
are, exactly what to do, and what you should see when it worked._

**Total time:** ~60–90 minutes across 6 steps. **Total cost:** $0 (all free tiers).

You do the account creation (things needing your email, card-on-file, or a password).
Claude does the code, configuration and pipelines.

---

## Before you start — what we're actually building

In plain language, a data platform needs five things. Here's the analogy and what we chose:

| Need | Analogy | Our choice |
|---|---|---|
| A place to keep the instructions | The recipe book | **GitHub** |
| A place to put raw downloaded files | The warehouse | **Cloudflare R2** |
| A place to query organised data | The filing cabinet you can search | **MotherDuck** |
| Something that runs jobs on schedule | The kitchen timer that starts cooking | **GitHub Actions** |
| A safe for passwords/keys | The safe | **GitHub Secrets** |

You already have the sixth: **OpenRouter**, for AI-assisted reading of PDFs.

**A note on "accounts with a card":** several services ask for a card even on free tiers, to prevent
abuse. Cloudflare R2 does. If you'd rather avoid that entirely, say so — there's an alternative
path noted in Step 2 that avoids any card.

---

## Step 1 — GitHub (the recipe book)

**What it is.** A website that stores code and documents, keeps every version, and can run
scheduled jobs for us for free. It's the spine of the whole platform.

**Why we need it.** Three jobs in one: version history (nothing is ever lost), the place scheduled
pipelines run, and the safe for our keys.

**Options.**

| Option | Pros | Cons |
|---|---|---|
| **GitHub** (recommended) | Free, universal, best scheduled-jobs support, best AI tooling | — |
| GitLab | Similar features, more built-in CI minutes | Smaller ecosystem |
| No version control | Nothing to set up | Any mistake is permanent; no scheduling; not viable |

**What to do.**
1. Go to **github.com** → *Sign up*. Use your work email.
2. Choose the **Free** plan.
3. Verify your email.
4. Create a repository: click **+** (top right) → *New repository*.
   - Name: `credit-data-platform`
   - Visibility: **Private** ← important
   - Do **not** tick "Add a README" (we already have files)
   - Click *Create repository*
5. Leave the page open and send me the repository URL.

**You'll know it worked when:** you see a mostly-empty page with setup instructions and a URL like
`github.com/<yourname>/credit-data-platform`.

**Cost:** Free. (Free tier includes 2,000 scheduled-job minutes/month — we'll use a fraction.)

---

## Step 2 — Cloudflare R2 (the warehouse)

**What it is.** Cloud storage for files — every PDF, CSV and ZIP we ever download lands here,
permanently.

**Why this one.** Most cloud storage charges you every time you *read* data back out ("egress
fees"), which is how surprise bills happen. R2 charges **nothing** for reading. For a platform
that re-processes its raw files often, that's the difference between predictable and unpredictable.

**Options.**

| Option | Storage cost | Egress (read) cost | Card needed |
|---|---|---|---|
| **Cloudflare R2** ← chosen (ADR-007) | $0.015/GB/mo, 10 GB free | **$0** | Yes |
| AWS S3 | $0.023/GB/mo | $0.09/GB — adds up fast | Yes |
| Backblaze B2 | $0.006/GB/mo, 10 GB free | Free up to 3× storage | Yes |
| Keep everything in MotherDuck instead | Included in free tier | — | No |

**What to do.**
1. Go to **cloudflare.com** → *Sign up* (free account).
2. Verify email, log in to the dashboard.
3. Left sidebar → **R2 Object Storage** → *Purchase R2* (it's the free tier; card required, no charge).
4. Click **Create bucket**. Name: `credit-data-lake`. Location: *Automatic*. Create.
5. Sidebar → **R2** → *Manage R2 API Tokens* → **Create API Token**.
   - Permission: **Object Read & Write**
   - Scope: the `credit-data-lake` bucket
   - Create, then **copy the three values shown** (Access Key ID, Secret Access Key, Endpoint URL).
     They're shown once only — paste them into a temporary note.

**You'll know it worked when:** the bucket appears in your R2 list and you hold three credential values.

**Cost:** Free up to 10 GB. Our first year likely lands well under $5/month.

**Important:** don't send me those keys in chat. Step 5 puts them straight into the safe.

---

## Step 3 — MotherDuck (the searchable filing cabinet)

**What it is.** A cloud database built on DuckDB, designed for analysis. This is where organised
data lands and where you'll run queries.

**Why this one.** It reads data files directly, has a genuine free tier, and its web interface lets
you query with plain SQL without installing anything. For our data sizes it's fast and simple.

**Options.**

| Option | Pros | Cons |
|---|---|---|
| **MotherDuck** (recommended) | Free tier, web UI, reads Parquet directly, minimal setup | Younger product |
| Google BigQuery | Enormous scale, generous free tier | More complex; needs GCP project & billing |
| Neon / Supabase (Postgres) | Familiar, great for reference tables | Weaker for large analytical scans |
| ClickHouse Cloud | Very fast | More operational complexity |

We may add **Neon** later purely for small reference tables (the source registry, entity
crosswalks). Not needed today.

**What to do.**
1. Go to **motherduck.com** → *Get started* → sign up (Google sign-in is fine).
2. Choose the **Free** plan.
3. Once in, find **Settings → Access Tokens** (or *Tokens*) → **Create token**.
   - Name: `credit-platform-pipelines`
   - Copy the token to your temporary note.

**You'll know it worked when:** you see a web SQL editor and hold a token starting with `eyJ...`.

**Cost:** Free tier. Paid tier (~$25/mo) only if we outgrow it, likely Phase 3+.

---

## Step 4 — OpenRouter (the AI reader) — you already have this

**What it is.** One account giving access to 340+ AI models.

**Why we need it.** India's most valuable data is trapped in PDFs with irregular layouts — NBFC
annual-report ECL notes especially. Where rule-based extraction fails, we use a vision model to
read the page. Everything it extracts gets checked against printed totals before we keep it
(see plan §6.1).

**What to do.**
1. Log in at **openrouter.ai** → *Keys* → **Create Key**.
   - Name: `credit-platform`
   - **Set a credit limit** — I'd suggest $20 to start. This caps spend even if something loops.
   - Copy the key (`sk-or-...`) to your temporary note.
2. Check *Credits* — keep a small balance ($10–20 is plenty for Phase 1).

**Cost:** Usage-based. Realistically $5–30/month during heavy extraction phases, near zero otherwise.

---

## Step 5 — Put the keys in the safe

**What it is.** GitHub Secrets — encrypted storage for credentials. Once stored, jobs can use them
but nobody (including me) can read them back.

**Why it matters.** Keys must never sit in code or documents. This is the one security rule that
genuinely matters here.

**What to do.**
1. In your GitHub repo → **Settings** (top bar of the repo, not your profile)
2. Left sidebar → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each, using these exact names:

| Secret name | Value | From |
|---|---|---|
| `R2_ACCESS_KEY_ID` | Access Key ID | Step 2 (skip if you skipped R2) |
| `R2_SECRET_ACCESS_KEY` | Secret Access Key | Step 2 |
| `R2_ENDPOINT` | Endpoint URL | Step 2 |
| `MOTHERDUCK_TOKEN` | Token | Step 3 |
| `OPENROUTER_API_KEY` | Key | Step 4 |

4. **Delete your temporary note** once all are saved.

**You'll know it worked when:** the Actions secrets page lists the names with values hidden.

---

## Step 6 — First pipeline (I do this; you watch it run)

Once Steps 1–5 are done, I will:

1. Push the project structure to your repo.
2. Build the first connector and run one source end-to-end — recommended: **SBA 7(a) loan data**
   (open US government data, ~1.8 million small-business loans with actual charge-off amounts;
   simple format, real credit-risk content).
3. Set it on a schedule.
4. Add the reconciliation check so it verifies itself against published totals.

**You'll know it worked when:** you can open MotherDuck, run
`SELECT COUNT(*) FROM silver.sba_7a_loans;` and see roughly 1.8 million — data you never
downloaded, refreshed on a schedule you never trigger.

Then we go straight at the IBBI insolvency data — the first dataset that will exist nowhere else.

---

## Glossary

| Term | Plain meaning |
|---|---|
| **Repository (repo)** | A project folder that tracks every change |
| **Pipeline** | An automated job: fetch → clean → store |
| **Bronze / silver / gold** | Raw files → cleaned tables → analysis-ready datasets |
| **Parquet** | A compact file format for data tables; much smaller and faster than CSV |
| **Object storage / bucket** | Cloud file storage; a bucket is a top-level folder |
| **API** | A machine-readable way to request data from a website |
| **API key / token** | A password that lets our code use a service |
| **Scraping** | Extracting data from web pages that don't offer a download |
| **Schema** | The defined structure of a table: columns, types, rules |
| **Reconciliation** | Checking our numbers against the publisher's printed totals |
| **Idempotent** | Safe to run twice — a re-run doesn't duplicate or corrupt anything |
| **Egress fees** | Charges for reading data *out* of cloud storage (R2 has none) |

---

## If something goes wrong

Nothing here is irreversible. Accounts can be deleted, buckets emptied, keys rotated (rotating a
key means creating a new one and deleting the old — do it any time you're unsure a key stayed private).

Send me the error text and where you were. Don't send me actual key values — describe the step instead.
