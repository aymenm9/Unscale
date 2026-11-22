"""Local demo data: one login and a few FICTIONAL sample companies.

Run:  .venv/bin/python -m app.seed
The real pipeline (research agent) replaces these with real companies and real sources.
Sample evidence points to example.com and is marked source_type="sample" so it is never
mistaken for real research.
"""

import os

from sqlalchemy import select

from app.auth import hash_password
from app.db import SessionLocal
from app.guards.email import check_email
from app.models import (
    Campaign,
    Company,
    Contact,
    Draft,
    Evidence,
    Qualification,
    Rejection,
    User,
)

SAMPLE_CHECK = {"name": "fact_check", "passed": True, "detail": "Sample data, checked by hand."}


def strategy(voice, trigger, pain, angles):
    return {
        "voice": voice,
        "trigger_evidence_id": trigger,
        "pain": pain,
        "follow_up_angles": [
            {"step": i + 1, "angle": a, "evidence_id": None} for i, a in enumerate(angles)
        ],
        "avoid": ["revenue numbers"],
    }


SAMPLES = [
    {
        "name": "Fernhill Goods",
        "domain": "fernhill.example",
        "platform": "shopify",
        "revenue_band": "$1-10M (est.)",
        "employee_band": "11-50",
        "summary": "Home goods brand selling on Shopify and Amazon.",
        "contact": ("Ana Ruiz", "Co-founder & COO", "ana@fernhill.example"),
        "evidence": [
            (
                "Hiring an operations manager",
                "We're hiring an Operations Manager to own inventory and 3PL relationships.",
                "careers",
            ),
            ("Sells on Shopify and Amazon", "Shop direct or find us on Amazon.", "website"),
            (
                "Raised a seed round",
                "Fernhill Goods closed a $2.1M seed round to expand wholesale.",
                "news",
            ),
        ],
        "score": 82,
        "verdict": "good",
        "reasons": [
            ("Shopify storefront plus Amazon: multi-channel reconciliation", 25, [1]),
            ("Ops hire means growing complexity in inventory", 20, [0]),
            ("Recent funding: investors expect clean books", 20, [2]),
            ("Team size fits Ledgerwise's sweet spot", 17, []),
        ],
        "subject": "wholesale at fernhill",
        "body": (
            "Hi Ana,\n\nCongrats on the seed round to expand wholesale [1]. Adding wholesale next "
            "to Shopify and Amazon [2] usually means three sets of payouts to match every month.\n\n"
            "Ledgerwise does the monthly bookkeeping for e-commerce brands, including inventory and "
            "COGS, so your team can focus on the launch. Worth a short call to see if it fits?"
        ),
        "cite": [2, 1],
        "voice": "numbers_operator",
        "pain": "Three payout streams to reconcile once wholesale starts.",
        "angles": [
            "Wholesale invoices and net-30 terms",
            "Inventory and COGS across channels",
            "Polite last note",
        ],
    },
    {
        "name": "Saltmarsh Supply Co.",
        "domain": "saltmarsh.example",
        "platform": "shopify",
        "revenue_band": "$1-10M (est.)",
        "employee_band": "5-10",
        "summary": "Outdoor apparel brand, DTC on Shopify.",
        "contact": ("Ben Okafor", "Founder", "ben@saltmarsh.example"),
        "evidence": [
            (
                "Ships to all 50 states",
                "Free shipping to all 50 states on orders over $75.",
                "website",
            ),
            (
                "Opened a second warehouse",
                "Our new Reno warehouse means faster delivery out West.",
                "news",
            ),
        ],
        "score": 68,
        "verdict": "maybe",
        "reasons": [
            ("Ships nationwide: sales tax exposure in many states", 25, [0]),
            ("Second warehouse adds inventory locations", 20, [1]),
            ("Small team, founder may still do the books", 13, []),
        ],
        "subject": "the reno warehouse",
        "body": (
            "Hi Ben,\n\nSaw the new Reno warehouse [1]. A second location plus shipping to all 50 "
            "states [2] often changes where you owe sales tax, and adds inventory to track in two "
            "places.\n\nLedgerwise keeps the books and sales tax tracking for e-commerce brands "
            "your size. Open to a short call to see if we can help?"
        ),
        "cite": [1, 0],
        "voice": "peer_founder",
        "pain": "Sales tax and inventory get harder with a second warehouse.",
        "angles": [
            "Sales tax nexus questions",
            "Two inventory locations at month-end",
            "Polite last note",
        ],
    },
    {
        "name": "Northpine Kitchen",
        "domain": "northpine.example",
        "platform": "shopify",
        "revenue_band": "$1-10M (est.)",
        "employee_band": "11-50",
        "summary": "Pantry foods brand, Shopify plus retail stockists.",
        "contact": ("Chloe Martin", "Head of Finance", "chloe@northpine.example"),
        "evidence": [
            ("Sold in 300 stores", "Find Northpine in 300+ independent grocers.", "website"),
        ],
        "score": 74,
        "verdict": "good",
        "reasons": [
            ("Retail plus DTC: two revenue streams to reconcile", 30, [0]),
            ("Has a finance lead who would own this decision", 24, []),
            ("Fits size band", 20, []),
        ],
        "subject": "northpine stockists",
        "body": (
            "Hi Chloe,\n\nNorthpine in 300+ independent grocers [1] is a real milestone. Retail "
            "invoices next to Shopify payouts can make month-end close slow, especially with net "
            "terms and deductions.\n\nLedgerwise handles the monthly close and payout "
            "reconciliation for e-commerce brands like yours, so your team gets clean numbers. "
            "Would a short call be useful?"
        ),
        "cite": [0],
        "voice": "finance_peer",
        "pain": "Retail deductions and DTC payouts slow the month-end close.",
        "angles": [
            "Retailer deductions and chargebacks",
            "Faster month-end close",
            "Polite last note",
        ],
    },
]


def run() -> None:
    db = SessionLocal()
    email = os.environ.get("SEED_USER_EMAIL", "sales@ledgerwise.test")
    password = os.environ.get("SEED_USER_PASSWORD", "ledgerwise-demo")
    if not db.scalar(select(User).where(User.email == email)):
        db.add(User(email=email, name="Ledgerwise Sales", password_hash=hash_password(password)))

    campaign = db.scalar(select(Campaign).where(Campaign.name == "Sample data (fictional)"))
    if not campaign:
        campaign = Campaign(
            name="Sample data (fictional)",
            status="done",
            stage="write",
            message="Fictional sample companies so the app is not empty. Start a real campaign.",
            settings={
                "categories": ["Home goods", "Apparel", "Food and drink"],
                "channels": ["Shopify", "Amazon"],
                "revenue_min": 1,
                "revenue_max": 10,
                "staff_min": 5,
                "staff_max": 50,
                "location": "Anywhere in the US",
                "signals": ["Raised money recently"],
                "roles": ["founder", "ops", "finance"],
                "voice": "auto",
                "target": 5,
            },
            created_by=email,
        )
        db.add(campaign)
        db.flush()
        for name, domain, stage, reason in [
            (
                "Big Lantern Home",
                "biglantern.example",
                "qualifier",
                "Too large: 300 staff and an in-house finance team.",
            ),
            (
                "Maple Pixel Agency",
                "maplepixel.example",
                "quick_filter",
                "A design agency, not a store.",
            ),
            ("Kelpie Goods", "kelpie.example", "code_check", "Store is outside the US (CA)."),
        ]:
            db.add(
                Rejection(
                    campaign_id=campaign.id, name=name, domain=domain, stage=stage, reason=reason
                )
            )

    for s in SAMPLES:
        if db.scalar(select(Company).where(Company.domain == s["domain"])):
            continue
        c = Company(
            campaign_id=campaign.id,
            channels=["Shopify", "Amazon"] if "Amazon" in s["summary"] else ["Shopify"],
            revenue_confidence="low",
            employee_confidence="medium",
            name=s["name"],
            domain=s["domain"],
            platform=s["platform"],
            revenue_band=s["revenue_band"],
            employee_band=s["employee_band"],
            summary=s["summary"],
            status="qualified",
        )
        db.add(c)
        db.flush()
        ev = []
        for claim, quote, kind in s["evidence"]:
            e = Evidence(
                company_id=c.id,
                claim=claim,
                quote=quote,
                url=f"https://{s['domain']}/{kind}",
                source_type="sample",
            )
            db.add(e)
            ev.append(e)
        name, title, addr = s["contact"]
        contact = Contact(
            company_id=c.id,
            name=name,
            title=title,
            email=addr,
            source_url=f"https://{s['domain']}/about",
        )
        db.add(contact)
        db.flush()
        db.add(
            Qualification(
                company_id=c.id,
                score=s["score"],
                verdict=s["verdict"],
                reasons=[
                    {"text": t, "points": p, "evidence_ids": [ev[i].id for i in idx]}
                    for t, p, idx in s["reasons"]
                ],
                confidence=0.8,
                summary=s["summary"],
            )
        )
        citations = [ev[i].id for i in s["cite"]]
        db.add(
            Draft(
                company_id=c.id,
                contact_id=contact.id,
                subject=s["subject"],
                body=s["body"],
                citations=citations,
                strategy=strategy(s["voice"], citations[0], s["pain"], s["angles"]),
                checks=check_email(
                    "first", s["subject"], s["body"], citations, {e.id for e in ev}, addr, set()
                )
                + [SAMPLE_CHECK],
            )
        )
    db.commit()
    print(f"Seeded. Login: {email}")


if __name__ == "__main__":
    run()
