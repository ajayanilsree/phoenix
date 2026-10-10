from decimal import Decimal, ROUND_UP
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


class ShippingError(Exception):
    pass


def _api_json(url, params):
    if not settings.DELHIVERY_API_TOKEN:
        raise ShippingError("Delivery charges are not configured yet.")
    request = Request(f"{url}?{urlencode(params)}", headers={"Authorization": f"Token {settings.DELHIVERY_API_TOKEN}", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=settings.DELHIVERY_REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        logger.warning("Delhivery request failed: %s", exc)
        raise ShippingError("Delhivery is temporarily unavailable. Please try again shortly.") from exc


def _number(value):
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return Decimal("0")


def _profile(item):
    product, variant = item.product, item.variant
    pickup = getattr(variant, "pickup_pincode", None) or product.pickup_pincode
    weight = getattr(variant, "package_weight_kg", None) or product.package_weight_kg
    variant_dimensions = [getattr(variant, f"package_{name}_cm", None) for name in ("length", "breadth", "height")]
    product_dimensions = [getattr(product, f"package_{name}_cm", None) for name in ("length", "breadth", "height")]
    dimensions = variant_dimensions if all(value is not None for value in variant_dimensions) else product_dimensions
    if not pickup or not weight or not all(dimensions) or not str(pickup).isdigit() or len(str(pickup)) != 6:
        raise ShippingError(f"Add pickup PIN, package weight, length, breadth and height for {product.name} before calculating delivery.")
    return {"o_pin": str(pickup), "weight_kg": _number(weight), "length": _number(dimensions[0]), "breadth": _number(dimensions[1]), "height": _number(dimensions[2])}


def _surface_quote(profile, delivery_pin):
    volumetric_kg = profile["length"] * profile["breadth"] * profile["height"] / Decimal("5000")
    chargeable_grams = int((max(profile["weight_kg"], volumetric_kg) * Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_UP))
    response = _api_json(settings.DELHIVERY_SHIPPING_COST_URL, {"md": "S", "ss": "Delivered", "d_pin": delivery_pin, "o_pin": profile["o_pin"], "cgm": chargeable_grams, "pt": "Pre-paid"})
    if isinstance(response, list) and response and isinstance(response[0], dict):
        response = response[0]
    if not isinstance(response, dict):
        raise ShippingError("Delivery charges could not be calculated right now. Please try again.")
    raw = response.get("total_amount", response.get("gross_amount", response.get("charge", response.get("amount"))))
    if raw is None:
        raise ShippingError("No Surface delivery rate is available for this address.")
    try:
        amount = Decimal(str(raw)).quantize(Decimal("0.01"))
    except Exception as exc:
        raise ShippingError("No Surface delivery rate is available for this address.") from exc
    if amount < 0:
        raise ShippingError("No Surface delivery rate is available for this address.")
    return amount, response.get("tat") or response.get("estimated_delivery_days") or response.get("expected_tat") or ""


def get_shipping_quote(cart, delivery_pin):
    delivery_pin = str(delivery_pin or "").strip()
    if len(delivery_pin) != 6 or not delivery_pin.isdigit():
        raise ShippingError("Enter a valid 6-digit delivery PIN code.")
    if not settings.DELHIVERY_SHIPPING_ENABLED:
        raise ShippingError("Delivery charges could not be calculated right now. Please try again.")
    total = Decimal("0.00")
    estimates = []
    for item in cart.items.select_related("product", "variant"):
        amount, tat = _surface_quote(_profile(item), delivery_pin)
        total += amount * item.quantity
        if tat:
            estimates.append(str(tat))
    return {"amount": total.quantize(Decimal("0.01")), "estimated_delivery": max(estimates, key=lambda value: int(value) if value.isdigit() else 0) if estimates else ""}
