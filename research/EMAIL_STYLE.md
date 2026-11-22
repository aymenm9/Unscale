# Email style research: Ledgerwise AI SDR

Researched 2026-11-20. Nearly all of these numbers come from vendors measuring their own platforms, so their metrics and samples differ. Read them as direction, not as exact figures. Where sources disagree, both figures are shown.

## Recommendation (TL;DR)

- **First email: 50-90 words, 3-4 sentences, one question as the CTA, no pitch paragraph.** Gong (28M+ emails, Jul 2025): 100 words or fewer is ideal, and pitching cuts replies by up to 57% ([Gong](https://www.gong.io/blog/does-cold-email-even-work-any-more-heres-what-the-data-says)). Instantly's best senders stay under 80 words ([Instantly 2026](https://instantly.ai/cold-email-benchmark-report-2026)).
- **Subject: 2-5 words, lowercase, specific to them.** No numbers, no hype.
- **CTA: an interest question** ("worth a quick look?"). Offer specific times only after they reply ([Gong, 304k emails](https://www.gong.io/blog/this-surprising-cold-email-cta-will-help-you-book-a-lot-more-meetings)).
- **Sequence: 3-4 emails, 3-4 days apart.** Each follow-up should add something new and read like a reply in the same thread.
- **Format: "plain-looking HTML".** One text column, system font, no images, no tracking pixel, no link in email 1 except the unsubscribe. Always send a text/plain alternative.
- **Personalize from one evidence item (a trigger), not five.** Every fact traces to a stored `[n]`. If there is no evidence, write a segment-level email or hand it to a human.

---

## 1. What works in 2025-2026 (data)

| Lever | Finding | Source (sample, date) |
|---|---|---|
| Baseline reply rate | Instantly: 3.43% average, top 10% at 10.7%+. Hunter: 4.5% per sequence (3% for sales). Belkins: 0.45% excluding auto-replies. The definitions differ a lot. | [Instantly](https://instantly.ai/cold-email-benchmark-report-2026) (2025 platform data); [Hunter](https://hunter.io/the-state-of-cold-email) (31M, 2025); [Belkins](https://belkins.io/blog/cold-email-response-rates) (7.5M, 2025) |
| Length | 100 words or fewer, 3-4 sentences (Gong). Execs: replies drop sharply above 100 words, best range 50-100 (Gong, Jan 2026). Hunter's peaks are at 61-80 and 181-200 words. | [Gong](https://www.gong.io/blog/does-cold-email-even-work-any-more-heres-what-the-data-says); [Gong execs](https://www.gong.io/blog/do-execs-really-reply-to-cold-email-here-s-what-the-data-says); [Hunter](https://hunter.io/the-state-of-cold-email) |
| Reading level | Lavender is widely quoted as saying 3rd-5th grade writing gets about 67% more replies. I could not find this in Lavender's primary report, so treat it as unverified. Execs spend about 9 seconds reading an email. | [Hunter summary of Lavender](https://hunter.io/blog/cold-email-word-count); [Gong execs](https://www.gong.io/blog/do-execs-really-reply-to-cold-email-here-s-what-the-data-says) |
| Subject length | 2-4 words had the best open rate (46%) and it falls past 7 words (Belkins, 5.5M, 2024). Gong execs: 1-4 words. Hunter: 5-6 words. | [Belkins](https://belkins.io/blog/b2b-cold-email-subject-line-statistics); [Hunter](https://hunter.io/the-state-of-cold-email) |
| Subject style | Personalized subjects: 46% vs 35% open rate, 7% vs 3% reply rate. Questions do well. Urgency words ("ASAP", "now") hurt. Case makes almost no difference: lowercase 29% vs title case 29%. Buzzwords and numbers cut opens by up to 17.9% (Gong). | [Belkins](https://belkins.io/blog/b2b-cold-email-subject-line-statistics); [Gong](https://www.gong.io/blog/does-cold-email-even-work-any-more-heres-what-the-data-says) |
| Personalization | No personalization 3.6% vs two custom attributes 5.6% reply rate. Manually edited 5.2% vs fully automated 4.4%. 67% of decision makers say personalization from public info makes them more likely to reply. Gong: a company-specific topic triples exec reply rates. | [Hunter](https://hunter.io/the-state-of-cold-email); [Gong](https://www.gong.io/blog/cold-email-stats) |
| Trigger-based | Widely recommended as the top tactic, but I found **no rigorous published lift number**. Apollo only proposes an A/B design. | [Apollo](https://www.apollo.io/insights/what-personalization-strategies-actually-improve-cold-email-reply-rates) |
| CTA | Interest CTAs win for cold email. Specific-time CTAs win once a deal is underway (37% vs 25%). Asking for "thoughts?" lowers meetings booked by about 20%. Use one CTA only. | [Gong CTA](https://www.gong.io/blog/this-surprising-cold-email-cta-will-help-you-book-a-lot-more-meetings); [Gong](https://www.gong.io/blog/cold-email-stats); [Instantly](https://instantly.ai/cold-email-benchmark-report-2026) |
| Follow-ups | 42% of replies come from follow-ups. Space them 3-4 days apart, 4-7 touches. A step 2 that reads like a reply does about 30% better (Instantly). Hunter: 3 emails is optimal (6.8% vs 3.3% for 1 email). Belkins: 3-5 steps, and step 3 books 35.6% of meetings. | [Instantly](https://instantly.ai/cold-email-benchmark-report-2026); [Hunter](https://hunter.io/the-state-of-cold-email); [Belkins](https://belkins.io/blog/sales-follow-up-statistics) |
| Timing | Belkins: weekday mornings 8am-12pm local time do best (0.54% reply rate, about 4x the meeting rate of other windows). Tue-Thu are slightly better. Hunter found **no effect from day of week**. | [Belkins timing](https://belkins.io/blog/choosing-the-best-timing-for-your-emails-how-should-you-do); [Hunter](https://hunter.io/the-state-of-cold-email) |
| Targeting | Small sequences do better: 21-50 recipients 6.2% vs 500+ at 2.4%. Contact 1-2 people per company, not 3 or more. | [Hunter](https://hunter.io/the-state-of-cold-email) |
| Executives | C-level execs are 30.2% less likely to reply. Avoid "AI", "platform" and vague ROI claims. | [Gong execs](https://www.gong.io/blog/do-execs-really-reply-to-cold-email-here-s-what-the-data-says) |
| AI perception | 69% of US decision makers are bothered if an AI wrote the email. 65% say cold emails are too sales-focused. | [Hunter](https://hunter.io/the-state-of-cold-email) |

**Skepticism notes:** open rates are no longer reliable because Apple MPP and bot opens inflate them ([Belkins](https://belkins.io/blog/choosing-the-best-timing-for-your-emails-how-should-you-do)). Optimize for replies and meetings. Gong's own pages contradict each other on the size of the interest-CTA advantage (2x vs 30%).

## 2. Voices

Who reads what: founders (time-poor, care about cash and the cost of their own time), COOs (process, month-end close speed, inventory), finance leads (accuracy, reconciliation, audit and tax readiness).

| Voice | Best for | Do | Don't |
|---|---|---|---|
| **Peer Founder** | Founders | First person, informal, one observation, empathy about doing the books at 11pm | Flattery ("love what you're building"), long backstory |
| **Numbers-First Operator** | COOs | Name the process pain (close timing, COGS, multi-channel payouts), concrete nouns | Invented metrics, ROI promises, prices |
| **Finance Peer** | Finance leads, controllers | Precise terms (accrual, payout reconciliation, sales-tax nexus), calm and exact | Jargon you can't back up, implying their work is bad |
| **Short & Plain** | Anyone, and all follow-ups | 2-3 sentences, a yes/no question | Fillers like "just bumping", guilt trips |

**Sample: Peer Founder** (Driftwood Candle Co. is fictional; markers are shown to the reviewer only)
> Subject: wholesale at driftwood
>
> Hi Maya, saw Driftwood just started selling wholesale to boutiques [1]. That usually means invoices, net-30 terms and Shopify payouts all hitting the same books. Ledgerwise does the monthly bookkeeping for e-commerce brands, so founders can stop reconciling at night. Worth a short call to see if it fits?
>
> Sam, Ledgerwise

**Sample: Numbers-First Operator**
> Subject: amazon + shopify close
>
> Hi Luis, noticed Northpine now sells on both Amazon and Shopify [1] and is hiring a second ops lead [2]. Matching two payout schedules to inventory is where month-end close usually slips. We handle that reconciliation monthly for e-commerce teams. Open to seeing how we'd set it up for you?

**Sample: Finance Peer**
> Subject: sales tax after the expansion
>
> Hi Priya, Kelp & Co announced shipping to Canada and the EU in March [1]. New regions tend to mean new sales-tax and VAT tracking on top of payout reconciliation. Ledgerwise keeps books accrual-ready for brands at this stage, so tax season isn't a scramble. Worth comparing notes for 15 minutes?

**Sample: Short & Plain (follow-up 2, same thread)**
> Hi Maya, one more thought: brands adding wholesale often split DTC and wholesale margins in the books from day one. Happy to show how we do it, or I'll close the loop here.

## 3. HTML vs plain text

- **Evidence:** HTML campaigns bounced 652-674% more than plain text (Hunter, 2.2M emails, 2025). This was **not a controlled test**, as the author admits ([Hunter](https://hunter.io/blog/is-html-harming-your-cold-email-deliverability/)). Snov reports 1.30% vs 1.08% reply rate for plain text ([Snov via search](https://snov.io/knowledgebase/how-to-send-plain-text-email-campaigns/)). HubSpot: well-coded HTML with a plain-text part doesn't hurt deliverability, but that data came from newsletters ([HubSpot](https://blog.hubspot.com/marketing/plain-text-vs-html-emails-data)). Turning off open tracking: 7.4% vs 4.4% reply rate ([Hunter](https://hunter.io/the-state-of-cold-email)).
- **"Beautiful but safe" means it looks like a person typed it:** `multipart/alternative` with an equivalent text/plain part, a system font at 15-16px, a max width of about 560px, no images (logo included), no tracking pixel, no buttons, no colored blocks, no link shorteners. Use at most one link (the unsubscribe) in email 1. A calendar link can come later, after a reply.

**Template (inline CSS only; email clients strip `<style>` blocks inconsistently):**
```html
<!doctype html><html><body style="margin:0;padding:0;">
<div style="max-width:560px;padding:16px;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;font-size:15px;line-height:1.5;color:#1a1a1a;">
  <p style="margin:0 0 12px;">Hi {{first_name}},</p>
  <p style="margin:0 0 12px;">{{observation_sentence}}</p>
  <p style="margin:0 0 12px;">{{relevance_sentence}}</p>
  <p style="margin:0 0 16px;">{{cta_question}}</p>
  <p style="margin:0 0 4px;">{{sender_first_name}}</p>
  <p style="margin:0;color:#555;font-size:13px;">{{sender_full_name}}, Ledgerwise · {{postal_address}}</p>
  <p style="margin:16px 0 0;color:#888;font-size:12px;">Not relevant? Reply "stop" or <a href="{{unsubscribe_url}}" style="color:#888;">unsubscribe</a>.</p>
</div></body></html>
```
Headers: `List-Unsubscribe: <https://.../u/{{token}}>, <mailto:unsub@...>` plus `List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058). The `[n]` citation markers are **stripped** before sending. They live only in the reviewer UI.

## 4. Reply handling

| Situation | Response pattern |
|---|---|
| **"How much?"** | Acknowledge, give the real reason, offer the call: "Fair question. Pricing depends on order volume, number of channels and how clean the books are today, so we scope it on a short call rather than guess. Would Tue 10:00 or Wed 14:00 ET work?" Never give a number or range (business rule 1). Gong finds discussing price on the first call goes with higher win rates, which supports moving it onto the call quickly ([Gong](https://www.gong.io/blog/data-reveals-the-best-time-to-talk-price-and-budget)). |
| "We have an accountant" | Agree, then separate the roles: "Makes sense. Many of our clients keep their CPA for tax and use us for the monthly books, so the CPA gets clean numbers. Is your accountant doing the monthly reconciliation too, or mainly year-end?" |
| "Too busy" | Respect it, then lower the ask: "Understood. Should I check back after Q4 peak, say mid-January?" Store the follow-up date and send nothing until then. |
| "Send info" | Send a short 3-bullet summary and ask one qualifying question: "Which is more painful today: month-end close or sales tax?" Avoid PDFs and attachments. |
| Stop / unsubscribe / not interested | Suppress immediately (deterministic, not LLM). Optional one-line confirmation: "Done, you won't hear from us again." |
| "Are you a bot?" | Answer honestly and gracefully: "Yes, I'm an AI assistant working with the Ledgerwise team. A person reviews these conversations, and I can bring in {{human_name}} anytime." California's SB 1001 already prohibits bots that hide their identity to influence a sale ([Perkins Coie](https://perkinscoie.com/insights/blog/i-am-robot-californias-new-law-requires-disclosure-use-bots)). |
| Low confidence / angry / legal / existing client | Hand off to a human with a reason. No auto-reply. |

**Proposing times:** once someone has replied, switch to a specific CTA ([Gong](https://www.gong.io/blog/this-surprising-cold-email-cta-will-help-you-book-a-lot-more-meetings)). Offer 2 slots in the prospect's time zone, on different days, plus "or grab any time here: {{link}}".

## 5. Deliverability and compliance (demo)

- **Auth:** SPF + DKIM (2048-bit) + DMARC (`p=none` minimum, aligned with the From domain), TLS, and a valid PTR record. Gmail requires this from senders of 5k+/day and has enforced it more strictly since Nov 2025 ([Google](https://support.google.com/a/answer/81126), [Google FAQ](https://support.google.com/a/answer/14229414)). Yahoo has the same rules ([Yahoo](https://senders.yahooinc.com/faqs)). Outlook.com has required it for 5k+/day since May 5 2025 ([Microsoft](https://techcommunity.microsoft.com/blog/exchange/strengthening-email-ecosystem-outlooks-new-requirements-for-high-volume-senders/4399730)). Do it anyway at demo volume.
- **Spam rate** below 0.1%, and never 0.3% or higher. **Honor unsubscribes within 48h** (Google). Bounce rate under 2% ([Instantly](https://instantly.ai/cold-email-benchmark-report-2026)).
- **CAN-SPAM:** truthful From and subject, identified as an ad (flexible wording), a physical postal address, a clear opt-out honored within 10 business days, and a working opt-out for 30 days. Fines go up to $53,088 per email ([FTC](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business)).
- **Demo:** use a separate sending subdomain and send only to allowlisted test inboxes (project rule). Keep volume low and steady. Hunter: 20-49 emails/day per inbox, and custom domains get 5.2% vs 2.5% for freemail ([Hunter](https://hunter.io/the-state-of-cold-email)).

## 6. EmailWriterAgent style guide (paste into system prompt)

```
ROLE: You write first-touch and follow-up cold emails for Ledgerwise, a US bookkeeping firm for e-commerce brands.

HARD RULES
- Never mention a price, range, discount, "affordable", "cheap" or "fraction of the cost".
- Every factual claim about the prospect MUST cite an evidence id from EVIDENCE as [n]. No evidence => no claim. If EVIDENCE is empty or weak, write a segment-level email (about e-commerce brands in general) and set confidence="low".
- Never invent metrics, clients, results or testimonials.
- Never claim to be human. Sign as the configured sender.
- One CTA only, phrased as a yes/no interest question (first touch). Specific times only in replies.

STRUCTURE (first touch)
1. Greeting: "Hi {first_name},"
2. Observation (1 sentence): one specific, cited trigger.
3. Relevance (1 sentence): the bookkeeping consequence of that trigger.
4. Offer (1 sentence): what Ledgerwise does, in plain words.
5. CTA (1 question).
- 50-90 words total (follow-ups 25-60). Max 4 sentences in the body. Max 20 words per sentence.
- Grade 5-7 reading level. Short common words. No bullet lists in email 1.
- Subject: 2-5 words, lowercase, specific (company or trigger). No numbers, no "?" spam, no emojis.
- Follow-ups: same thread ("Re:"), add ONE new angle or fact; never "just bumping/circling back".
- Voice = {voice_id}; obey its do/don't list.

BANNED PHRASES
"I hope this finds you well", "I hope you're doing well", "My name is", "I wanted to reach out",
"just following up", "just checking in", "bumping this", "circling back", "touch base",
"quick question" (subject), "synergy", "leverage", "game-changer", "revolutionize",
"cutting-edge", "AI-powered", "platform", "solution", "best-in-class", "world-class",
"seamless", "unlock", "skyrocket", "ROI", "guarantee", "free", "act now", "ASAP",
"limited time", "no obligation", "I'd love to", "Love what you're building", "Hello friend",
"Dear Sir/Madam", "thoughts?" (as the CTA).

OUTPUT (zod-validated JSON)
{ subject, body_text, body_html, citations: [{marker, evidence_id}], voice_id,
  word_count, confidence: "high"|"medium"|"low", handoff_reason?: string }
```

**Deterministic checks after generation (code, not LLM):** reject on currency symbols, `\d+\s?(k|K|dollars|USD|/mo|per month)`, banned phrases, word count over the limit, more than one `?` in the CTA paragraph, any `[n]` that doesn't map to stored evidence, or any link in email 1 other than unsubscribe. Then strip the `[n]` markers before the send step.
