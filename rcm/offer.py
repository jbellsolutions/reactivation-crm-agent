"""The offer as data (offer/offer.json), and the terms one client signed on top of it."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFER_FILE = ROOT / "offer" / "offer.json"


class OfferError(ValueError):
    pass


def load(path=OFFER_FILE):
    return json.loads(Path(path).read_text())


def terms(offer, agreed=None):
    """The offer's defaults with the client's agreed values on top. Refuses while no price is set."""
    agreed = agreed or {}
    qa = offer["qualified_appointment"]
    price = agreed.get("price_per_appointment_usd", offer["price_per_qualified_appointment_usd"])
    if price is None:
        raise OfferError("no price per qualified appointment is set; Justin sets it (GO-LIVE.md, step 1)")
    out = {
        "price_usd": float(price),
        "deposit_usd": float(agreed.get("deposit_usd", offer["deposit_usd"])),
        "intro_days": int(agreed.get("intro_days", offer["intro_days"])),
        "dispute_hours": int(agreed.get("dispute_hours", qa["dispute_hours"])),
        "duplicate_days": int(agreed.get("duplicate_days", qa["duplicate_days"])),
        "existing_customer_days": int(agreed.get("existing_customer_days", qa["existing_customer_days"])),
    }
    if out["price_usd"] <= 0 or out["deposit_usd"] < 0:
        raise OfferError("price must be above 0 and the deposit can't be negative")
    return out
