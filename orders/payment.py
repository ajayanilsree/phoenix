import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def razorpay_is_configured():
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def razorpay_sdk_available():
    try:
        import razorpay  # noqa: F401
    except ImportError:
        return False
    return True


def get_razorpay_client():
    logger.info("Razorpay configured: %s", razorpay_is_configured())
    if not razorpay_is_configured():
        raise ImproperlyConfigured(
            "Razorpay credentials are not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET."
        )
    try:
        import razorpay
    except ImportError as exc:
        raise ImproperlyConfigured("The Razorpay Python SDK is not installed.") from exc
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
