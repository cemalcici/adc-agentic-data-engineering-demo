"""Deterministic customer record generation.

A record's values depend only on its identifier and the seed — never on how
many records were generated before it. That is what lets the initial dataset
and every later arrival follow one rule, and what makes the source's contents a
function of how many arrival intervals have elapsed rather than of the order
things happened to run in.

See adr/0012-let-the-simulated-upstream-keep-operating.md
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import random
import unicodedata

FIRST_NAMES: tuple[str, ...] = (
    "Elif", "Deniz", "Mert", "Zeynep", "Can", "Ayse", "Emre", "Selin",
    "Burak", "Ece", "Kaan", "Naz", "Ali", "Irem", "Ozan", "Melis",
    "Anna", "Lukas", "Sofia", "Mateo", "Nora", "Felix", "Chloe", "Hugo",
    "Yuki", "Ravi", "Priya", "Omar", "Layla", "Noah", "Mia", "Liam",
)

LAST_NAMES: tuple[str, ...] = (
    "Yilmaz", "Kaya", "Demir", "Sahin", "Celik", "Yildiz", "Aydin", "Ozturk",
    "Arslan", "Dogan", "Kilic", "Aslan", "Cetin", "Kara", "Koc", "Kurt",
    "Novak", "Schmidt", "Rossi", "Garcia", "Dubois", "Silva", "Nowak", "Virtanen",
    "Tanaka", "Sharma", "Haddad", "Okafor", "Nguyen", "Andersen", "Murphy", "Bakker",
)

COUNTRIES: tuple[str, ...] = (
    "TR", "DE", "NL", "GB", "FR", "ES", "IT", "PL",
    "SE", "US", "CA", "JP", "IN", "BR", "AE", "AU",
)

EMAIL_DOMAINS: tuple[str, ...] = (
    "example.com", "example.net", "example.org", "mail.example.com",
)

# Signup dates come from a fixed window so the dataset does not shift with the
# wall clock. Data whose shape depends on when it was generated is not
# reproducible in the sense a rehearsed demo needs.
SIGNUP_WINDOW_START = dt.date(2023, 1, 1)
SIGNUP_WINDOW_DAYS = 1_000

# Mixing the seed and the identifier with a large prime keeps neighbouring
# identifiers from producing visibly similar records, while staying pure integer
# arithmetic — no reliance on how Python happens to hash other types.
_SEED_STRIDE = 1_000_003


def email_slug(text: str) -> str:
    """Reduce a name to plain ASCII suitable for an email local part."""
    normalised = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalised if c.isascii() and c.isalnum()).lower()


def build_row(customer_id: int, random_seed: int) -> tuple[object, ...]:
    """Build one customer record, determined entirely by its identifier."""
    rng = random.Random(random_seed * _SEED_STRIDE + customer_id)

    first_name = rng.choice(FIRST_NAMES)
    last_name = rng.choice(LAST_NAMES)
    domain = rng.choice(EMAIL_DOMAINS)
    country = rng.choice(COUNTRIES)
    signup_date = SIGNUP_WINDOW_START + dt.timedelta(
        days=rng.randrange(SIGNUP_WINDOW_DAYS)
    )
    # Most customers are active; a minority are not, so downstream aggregates
    # have something to distinguish.
    is_active = rng.random() < 0.82

    email = f"{email_slug(first_name)}.{email_slug(last_name)}{customer_id}@{domain}"

    return (
        customer_id,
        first_name,
        last_name,
        email,
        country,
        signup_date.isoformat(),
        "true" if is_active else "false",
    )


def build_csv(first_id: int, last_id: int, random_seed: int) -> io.StringIO:
    """Build a CSV buffer covering an inclusive range of identifiers."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for customer_id in range(first_id, last_id + 1):
        writer.writerow(build_row(customer_id, random_seed))
    buffer.seek(0)
    return buffer
