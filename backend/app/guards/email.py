"""Style and safety checks for every email an agent writes (first email, follow-up, reply).

All plain Python. The writer prompt asks for the same rules; this code enforces them.
"""

import re

from app.guards import check_draft

BANNED_PHRASES = [
    "i hope this finds you well",
    "i hope you're doing well",
    "my name is",
    "i wanted to reach out",
    "just following up",
    "just checking in",
    "bumping this",
    "circling back",
    "touch base",
    "synergy",
    "leverage",
    "game-changer",
    "game changer",
    "revolutionize",
    "cutting-edge",
    "ai-powered",
    "platform",
    "solution",
    "best-in-class",
    "world-class",
    "seamless",
    "unlock",
    "skyrocket",
    "roi",
    "guarantee",
    "free",
    "act now",
    "asap",
    "limited time",
    "no obligation",
    "i'd love to",
    "love what you're building",
    "dear sir",
    "thoughts?",
]

# Word limits per email kind (body, without [n] markers).
WORD_LIMITS = {"first": (50, 90), "follow_up": (25, 60), "reply": (1, 120)}

LINK = re.compile(
    r"(https?://|www\.|\b[a-z0-9-]+\.(com|co|io|net|org|shop|store)\b)", re.IGNORECASE
)
MARKER = re.compile(r"\s?\[\d+\]")


def strip_markers(body: str) -> str:
    """Remove [n] citation markers. They are for the reviewer, never sent."""
    return MARKER.sub("", body)


def renumber_markers(body: str, citations: list[int], allowed: set[int]) -> tuple[str, list[int]]:
    """Code-side fix for a common model slip: writing the evidence id ([42]) instead of its
    position ([1]). If every marker is a known evidence id, renumber them 1, 2, ... in order
    of appearance and rebuild `citations`. Otherwise leave it for the checks to judge."""
    found = [int(m) for m in re.findall(r"\[(\d+)\]", body)]
    if not found or set(found) <= set(range(1, len(citations) + 1)):
        return body, citations
    if not set(found) <= allowed:
        return body, citations
    order: list[int] = []
    for evidence_id in found:
        if evidence_id not in order:
            order.append(evidence_id)
    new_body = re.sub(r"\[(\d+)\]", lambda m: f"[{order.index(int(m.group(1))) + 1}]", body)
    return new_body, order


def word_count(body: str) -> int:
    return len(strip_markers(body).split())


def banned_phrases_found(text: str) -> list[str]:
    t = text.lower().replace("’", "'")
    found = []
    for phrase in BANNED_PHRASES:
        # Word boundaries so "free" does not match "freelance". "thoughts?" ends in "?".
        pattern = r"\b" + re.escape(phrase) + (r"" if phrase.endswith("?") else r"\b")
        if re.search(pattern, t):
            found.append(phrase)
    return found


def has_link(text: str) -> bool:
    return bool(LINK.search(text))


def subject_problems(subject: str) -> list[str]:
    problems = []
    words = subject.split()
    if not 2 <= len(words) <= 5:
        problems.append(f"Subject has {len(words)} words; use 2-5.")
    if subject != subject.lower():
        problems.append("Subject must be lowercase.")
    if re.search(r"\d", subject):
        problems.append("Subject must not contain numbers.")
    if "?" in subject or "!" in subject:
        problems.append("Subject must not contain ? or !.")
    if any(ord(ch) > 0x2000 for ch in subject):
        problems.append("Subject must not contain emojis or symbols.")
    return problems


def check_email(
    kind: str,
    subject: str | None,
    body: str,
    citations: list[int],
    allowed_evidence_ids: set[int],
    recipient: str,
    suppressed_emails: set[str],
) -> list[dict]:
    """All checks for one email. kind is "first", "follow_up" or "reply".

    Starts from check_draft (price, citations, suppression) and adds the style rules from
    research/EMAIL_STYLE.md. A follow-up or reply may have no citation.
    """
    checks = check_draft(body, citations, allowed_evidence_ids, recipient, suppressed_emails)
    if kind != "first":
        checks = [c for c in checks if c["name"] != "has_personal_fact"]

    low, high = WORD_LIMITS[kind]
    n = word_count(body)
    banned = banned_phrases_found(f"{subject or ''} {body}")
    checks += [
        {
            "name": "length",
            "passed": low <= n <= high,
            "detail": f"{n} words; this kind of email needs {low}-{high}.",
        },
        {
            "name": "no_banned_phrases",
            "passed": not banned,
            "detail": "No spammy or pushy phrases."
            + (f" Found: {', '.join(banned)}." if banned else ""),
        },
        {
            "name": "no_links",
            "passed": not has_link(body),
            "detail": "No links in the body (the unsubscribe link is added by code).",
        },
    ]
    if kind == "first":
        problems = subject_problems(subject or "")
        checks += [
            {
                "name": "subject",
                "passed": not problems,
                "detail": " ".join(problems) or "Subject is 2-5 lowercase words.",
            },
            {
                "name": "one_question",
                "passed": strip_markers(body).count("?") == 1,
                "detail": "Exactly one question: the call to action.",
            },
        ]
    return checks


def failed(checks: list[dict]) -> list[str]:
    """Details of failed checks, ready to send back to the LLM for one retry."""
    return [f"{c['name']}: {c['detail']}" for c in checks if not c["passed"]]
