"""Hard-coded reply templates for the compose page. {first_name} and {slots} are filled in."""

TEMPLATES = {
    "pricing": (
        "Hi {first_name}, fair question. Cost depends on your order volume, how many channels "
        "you sell on and how clean the books are today, so we scope it on a short call rather "
        "than guess. Would one of these work? {slots}"
    ),
    "has_accountant": (
        "Hi {first_name}, makes sense. Many of our clients keep their CPA for tax and use us for "
        "the monthly books, so the CPA gets clean numbers. Is your accountant doing the monthly "
        "reconciliation too, or mainly year-end?"
    ),
    "not_now": (
        "Hi {first_name}, understood. I'll check back after the busy season. If anything "
        "changes before then, just reply here."
    ),
    "send_info": (
        "Hi {first_name}, short version: we do monthly bookkeeping and close for e-commerce "
        "brands, reconcile Shopify, Amazon and other payouts, and track sales tax across "
        "states. Which is more painful today: month-end close or sales tax?"
    ),
    "booking_confirmation": (
        "Hi {first_name}, booked for {slots}. You'll get a calendar invite. Talk soon."
    ),
}
