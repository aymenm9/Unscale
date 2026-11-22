"""Shopify App Store review pages. Reviewers are real stores, and the app they use is a
signal (3PL app = warehouse, wholesale app = wholesale). robots.txt allows /reviews."""

from app.tools import web

# Apps whose users are likely multi-channel / growing brands.
SIGNAL_APPS = {
    "shipbob": "uses a 3PL warehouse",
    "shiphero": "uses a 3PL warehouse",
    "faire-wholesale": "sells wholesale",
    "wholesale-pricing-discount": "sells wholesale",
    "taxjar": "tracks sales tax",
    "a2x-accounting": "reconciles marketplace payouts",
}


def read_reviews(app: str, page: int = 1) -> str | None:
    """Text of one review page: store names, countries, how long they used the app."""
    return web.read_page(f"https://apps.shopify.com/{app}/reviews?page={page}", max_chars=6000)
