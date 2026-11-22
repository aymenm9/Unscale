# Sourcing real e-commerce leads for free (research, 2026-11-20)

Legend: **[LIVE]** = verified with curl from this machine on 2026-11-20. Everything else is cited.

## Recommendation (TL;DR)

1. **Discover** from two structured sources that carry their own evidence: **SEC Form D** (`industryGroupType=Retailing`, executives named) [LIVE] and **Shopify App Store review pages** for e-com ops apps (3PLs, wholesale, inventory). Each review lists the merchant name, country, and how long they've used the app [LIVE].
2. **Resolve and qualify** each brand on its own Shopify storefront. `/meta.json` returns `country`, `province`, `city`, `published_products_count`, and `ships_to_countries` [LIVE]. `/products.json?limit=250&page=N` gives prices [LIVE]. Read the About/Team pages through **Jina Reader** (no key needed) [LIVE].
3. **Size** with Tranco rank (free API) [LIVE], ATS job counts (Ashby/Greenhouse/Lever), Form D amounts, and SKU x price. Store a *band + confidence*, never a single number.
4. **Search API:** Tavily (1,000 free credits/mo) as the main engine, Exa ($10/mo free) as a backup, and self-hosted Crawl4AI for any page Jina can't read.
5. **Avoid:** LinkedIn scraping, Kickstarter scraping (403), scraping Google/DDG HTML, and SMTP mailbox probing from cloud hosts.

---

## 1. Discovery sources

| Source | What it gives | Access | Limits / ToS risk | Quality for ICP |
|---|---|---|---|---|
| **SEC Form D full-text search** | Private raises, issuer state, executives/directors/promoters, offering amount, `revenueRange` | `efts.sec.gov/LATEST/search-index?q="Retailing"&forms=D&startdt=..&enddt=..` [LIVE: 132 hits Jun–Nov 2026]. Filing XML: `sec.gov/Archives/edgar/data/{cik}/{adsh}/primary_doc.xml` [LIVE] | 10 req/s and a declared User-Agent with a contact email ([SEC](https://www.sec.gov/os/accessing-edgar-data), [rate limits](https://www.sec.gov/oit/announcement/new-rate-control-limits)). A curl call with no email in the UA hung | High-trust facts. Many issuers are not DTC brands, so filter by website |
| **Shopify App Store reviews** | Merchant store name, country, "Over 1 year using the app" | `apps.shopify.com/{app-slug}/reviews?page=N` [LIVE on `shipbob`, about 29 pages] | robots.txt allows it; only `/internal`, `/services`, and `*q=*` are disallowed ([robots](https://apps.shopify.com/robots.txt)) | Very good. Picking the app *is* the signal: 3PL apps = warehouse, Faire/wholesale apps = wholesale. Gives a name only, so you need a search step to find the domain |
| **Shopify storefront JSON** | Confirms Shopify plus HQ location, SKU count, ship-to countries | `{domain}/meta.json`, `/products.json?limit=250&page=N`, `/sitemap.xml`; `powered-by: Shopify` header [all LIVE] | Public, but crawl politely. Community posts say paging isn't supported ([thread](https://community.shopify.com/t/how-to-paginate-or-get-a-list-of-all-products-using-domain-com-products-json/99991)), yet `page=2` worked live | Excellent for qualifying; not a discovery source |
| **Search operators via API** | Candidate domains | Tavily/Exa queries such as `"powered by shopify" "our story" founder candles Austin` | Allowed through the API's ToS | Medium. Noisy, so verify with `meta.json` |
| **Faire brand/category pages** | Brands selling wholesale | robots.txt explicitly allows `/category/*?page=1..11` and `/suppliers/*` ([robots](https://www.faire.com/robots.txt)) [LIVE] | JS-heavy, so use Crawl4AI. Keep volume low | Good wholesale signal |
| **Common Crawl index** | Every captured URL for a domain/pattern | `index.commoncrawl.org/CC-MAIN-2026-43-index?url=*.example.com&output=json` [LIVE, Oct 2026 crawl] ([docs](https://commoncrawl.org/blog/announcing-the-common-crawl-index)) | Free, slow, no technology filter | Low effort/benefit for 30 leads. Skip |
| **Wikidata SPARQL** | Notable companies | `query.wikidata.org/sparql` [LIVE 200] | Free | Poor: $1–10M brands are rarely notable |
| **Kickstarter** | Product alumni | `/discover/advanced?format=json` returned **403** [LIVE] | Bot-blocked | Skip |
| **Store Leads / BuiltWith / Minea** | Shopify store lists by niche/revenue | Free tiers show stats only; full data is paid ([Omnisend overview](https://www.omnisend.com/blog/search-shopify-store/)) | Paid | Skip (zero budget) |
| **OpenCorporates / state registries** | Legal entity, officers | API key required; free access is for public-benefit use only ([terms](https://opencorporates.com/legal-information/self-service-api-terms-of-service/), [pricing](https://opencorporates.com/pricing/)) | Commercial use is paid | Optional manual check only |
| **Product Hunt, Amazon brand stores** | Some DTC launches | Amazon blocks bots; PH is mostly software | High ToS risk / poor fit | Skip |

## 2. Estimating revenue band and headcount (honest)

No free source gives revenue for private brands. Combine proxies and show the evidence plus a confidence level in the UI.

| Proxy | Source | Accuracy |
|---|---|---|
| Form D `revenueRange` | Filing XML | Exact when present, but usually "Decline to Disclose" (seen live) |
| Form D `totalOfferingAmount` | Filing XML | Only shows the raise size. A $0.2–3M raise is consistent with a small brand. Weak |
| Traffic rank | Tranco: `tranco-list.eu/api/ranks/domain/{d}` [LIVE] | Rough. Calibrate thresholds on known brands first: Brooklinen, which is well above $10M, ranks about 97k |
| SKU count x median price | `meta.json` + `products.json` | Shows assortment, not sales volume. Use it only to rule out tiny hobby shops (<10 SKUs) |
| Open roles | Ashby / Greenhouse `boards-api.greenhouse.io/v1/boards/{slug}/jobs` / Lever `api.lever.co/v0/postings/{slug}?mode=json` [Lever LIVE] | 0–3 open roles fits 5–50 staff. Most small brands have no ATS at all |
| Team page headcount | About/Team page via Jina | Good lower bound when a team page exists |
| Press ("$X in sales") | Search API, then quote | Best evidence when it exists. Must be a quote with a URL |
| Years on app | App review ("Over 1 year using the app") | Shows the brand has been operating for a while |

**Rule:** output `revenue_band ∈ {<1M, 1–10M, >10M, unknown}` with `confidence` and the list of evidence IDs. Never state revenue as a fact without a quote (business rule 2).

## 3. "Needs bookkeeping" signals

| Signal | Where | How to detect |
|---|---|---|
| Hiring finance/ops (bookkeeper, controller, ops manager) | Ashby/Greenhouse/Lever APIs; `/careers` page | Keyword match on job titles |
| Recent funding | Form D `dateOfFirstSale`, filing date | Filed in the last 12 months |
| 3PL / new warehouse | App reviews on ShipBob/ShipHero/ShipStation-type apps; "ships from" text | The review itself is the evidence |
| Wholesale launch | Faire presence; `/pages/wholesale`; wholesale apps in the App Store | URL exists, plus a quote |
| Multi-channel (Amazon, Walmart, TikTok Shop, retail) | Links on the site and "Find us in stores" pages | Quote the link text |
| International expansion | `meta.json` `ships_to_countries` with more than 1 country; multi-currency | Structured field |
| Sales-tax nexus pressure | Selling nationally plus economic-nexus thresholds (commonly $100k or 200 transactions; varies by state) ([Tax Foundation](https://taxfoundation.org/data/all/state/economic-nexus-by-state-2024/), [Wikipedia](https://en.wikipedia.org/wiki/Economic_nexus_in_the_United_States)) | An *inference*, so phrase it as a question, never as a claim |
| Change over time | Wayback `archive.org/wayback/available?url=..&timestamp=..` [LIVE] | Compare old vs. new SKU counts or pages |

## 4. Right person and work email

1. **People:** Form D related persons (name plus "Executive Officer"/"Director") [LIVE]; the site's About/Team/"Our story" pages (founder names, quoted); press releases found via the search API.
2. **Email:** most small Shopify brands publish `hello@` or `info@` on their contact page. Use it, and address the founder by name. For a personal address, generate patterns (`first@`, `first.last@`) and check MX with dnspython. **Do not rely on SMTP RCPT probing.** Port 25 is blocked by default on AWS/GCP/Azure/DO, and catch-all domains accept any address ([DO forum](https://digitalocean.com/community/questions/smtp-handshake-not-working-blocked-on-port-25), [explainer](https://dev.to/apa512/theres-no-clean-way-to-verify-an-email-address-heres-what-works-anyway-36bn)).
3. **Hunter free:** 50 credits/month shared between finder and verifier ([pricing](https://hunter.io/pricing)). Use it only for the top 30 leads.
4. **Legal:** CAN-SPAM has no B2B exemption. You need a truthful header and subject, a postal address, a working opt-out honored within 10 business days, and the opt-out must keep working for 30 days after sending ([FTC guide](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business)). For this demo, all outbound mail goes to test inboxes only (project rule).

## 5. Search/scrape APIs (late 2026)

| Tool | Free tier | Fit |
|---|---|---|
| **Tavily** | 1,000 credits/mo, no card; basic search = 1 credit ([docs](https://docs.tavily.com/documentation/api-credits.md)) | **Primary.** LLM-ready snippets, Python SDK, LangChain integration |
| **Exa** | $10 on signup, reset to $10 monthly, no card; search $4–7 per 1k, contents $1 per 1k ([pricing](https://exa.ai/docs/reference/pricing)) | **Secondary.** Neural "find companies like X" works well for lookalike brands |
| **Firecrawl** | 1,000 credits/mo, 2 concurrent requests ([pricing](https://www.firecrawl.dev/pricing.md)) | Good extraction, but Jina + Crawl4AI cover it for free |
| **Jina Reader** `r.jina.ai/{url}` | No key: 20 RPM, search blocked; free key gives more ([rate limits](https://jina.ai/en-US/api-dashboard/rate-limit/)) [LIVE] | **Default page-to-markdown.** Ideal for evidence quotes |
| **Crawl4AI** | Open source, Apache-2.0, v0.9.6 on PyPI [LIVE] | **Fallback** for JS-heavy pages (Faire). Self-hosted Playwright |
| **Serper** | 2,500 queries, no card; one-time vs. monthly is unclear ([site](https://serper.dev/), [comparison](https://dev.to/darshan_sd/10-best-serper-alternatives-for-fast-reliable-serp-apis-2026-3dm6)) | Cheap Google SERPs. Good backup |
| **SerpAPI** | 250 searches/mo ([pricing](https://serpapi.com/pricing), [CostBench](https://costbench.com/software/web-scraping/serpapi/free-plan/)) | Too small |
| **Brave Search API** | Free tier dropped Feb 2026; now $5/mo credit, card required, attribution required ([Brave](https://brave.com/learn/google-api-shutdown/), [Implicator](https://www.implicator.ai/brave-drops-free-search-api-tier-puts-all-developers-on-metered-billing/)) | Avoid (needs a card) |
| **DuckDuckGo** (`ddgs` lib, v9.16.1) | Unofficial scraping; HTML endpoint returned 202 (bot challenge) [LIVE] | Avoid in production |
| Google CSE / Bing API | Google closed to new customers, shuts down 2027-01-01; Bing retired Aug 2025 ([Google](https://developers.google.com/custom-search/v1/overview), [Firecrawl](https://www.firecrawl.dev/blog/google-search-json-api-alternative)) | Not available |

## 6. Recommended pipeline (30–50 qualified companies)

1. **Seed (target about 150 candidates):**
   a. Form D: run `efts` queries for `Retailing` plus keywords ("apparel", "beverages", "consumer products", "e-commerce") over the last 18 months. Parse the XML for issuer, state, people, amount, and revenueRange.
   b. App reviews: crawl 3–5 pages each of about 6 e-com ops apps (3PL, wholesale, inventory, sales tax) and keep the `United States` reviewers.
2. **Resolve the domain:** Tavily query `"{name}" official site shop`. Accept a result only if `{domain}/meta.json` returns valid JSON whose `name` fuzzy-matches the brand.
3. **Hard filters (deterministic code):** `country == "US"`; `published_products_count` between 10 and 2,000; not a marketplace, agency, or public company; Tranco rank within calibrated bounds (drop brands as big as Brooklinen).
4. **Evidence harvest:** fetch the home, About, Team, Contact, Careers, and Wholesale pages via Jina, plus ATS APIs and one Tavily news query. Store each fact as `{url, exact_quote, fetched_at, sha256(page)}`. Reject any LLM claim whose quote isn't a substring of the cached page.
5. **Score (LLM, zod/pydantic-validated):** ICP fit, size band plus confidence, and need signals (section 3). Each score cites evidence IDs. Low confidence goes to human review (rule 5).
6. **Contact:** founder/COO name from Form D or the About page; email from the contact page, then pattern + MX; Hunter for the top 30. Check the suppression list before any send.
7. **Robustness:** one global HTTP client with a per-host token bucket (SEC ≤ 5 req/s, everything else ≤ 1 req/s), a `robots.txt` check via `urllib.robotparser`, a SQLite response cache keyed by URL (TTL 7 days, so reruns are free), retries with exponential backoff on 429/5xx, and an honest UA with a contact email. Log every fetch to the audit table.
8. **Budget for 50 leads:** about 300 Tavily credits, about 400 Jina reads (0 cost), about 50 Hunter credits. All within free tiers.

**Avoid:** LinkedIn scraping. Its user agreement anti-scraping terms were held enforceable, hiQ was permanently enjoined, and Proxycurl was shut down by suit ([Morgan Lewis](https://www.morganlewis.com/ja/blogs/sourcingatmorganlewis/2022/12/linkedin-v-hiq-landmark-data-scraping-suit-provides-guidance-to-data-scrapers-and-web-operators), [LinkedIn](https://news.linkedin.com/2025/LinkedInWinsLegalBattleToProtectMemberData)). Also avoid scraping Google/DDG/Amazon HTML, bypassing captchas or 403s (Kickstarter), buying lists, SMTP probing, and stating inferred facts (revenue, nexus) as claims.
