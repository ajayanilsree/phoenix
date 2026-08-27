import json
import logging
import re
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.db import DatabaseError, OperationalError
from django.urls import reverse

from .models import ChatbotFAQ
from .prompts import PHOENIX_SYSTEM_INSTRUCTION
from .selectors import CATALOGUE_GROUPS, find_relevant_catalogue_context

logger = logging.getLogger(__name__)

UNRELATED_PATTERNS = re.compile(
    r"\b(weather|president|python code|write code|recipe|movie|song|football|cricket score|stock market)\b",
    re.IGNORECASE,
)
SENSITIVE_PATTERNS = re.compile(r"\b(api key|system prompt|environment variable|password|cvv|otp|secret)\b", re.IGNORECASE)
GREETING_PATTERNS = re.compile(r"^\s*(hi|hello|hey|hai|good morning|good afternoon|good evening)\s*[!.]?\s*$", re.IGNORECASE)


def default_actions():
    return [
        {"label": "Browse Products", "url": reverse("shop")},
        {"label": "Contact Phoenix", "url": "/#contact"},
    ]


def static_navigation_response(message, request):
    lowered = message.lower()
    if GREETING_PATTERNS.match(message):
        return {
            "success": True,
            "message": "Hi, welcome to Phoenix Interior Hub. I can help you find products, explore our catalogue, or reach the right store page. What are you looking for today?",
            "products": [],
            "categories": [],
            "actions": [
                {"label": "Shop Products", "url": reverse("shop")},
                {"label": "Boards & Panels", "url": reverse("shop_catalogue_main", kwargs={"main_slug": "boards-panels"})},
                {"label": "Kitchen Fittings", "url": reverse("shop_catalogue_main", kwargs={"main_slug": "kitchen-fittings-accessories"})},
            ],
        }
    if any(term in lowered for term in ["what can you help", "how can you help", "help me find", "what do you sell"]):
        return {
            "success": True,
            "message": "I can help you find Phoenix products, browse boards and panels, explore kitchen or wardrobe fittings, compare available catalogue items, and reach account or support pages.",
            "products": [],
            "categories": [],
            "actions": [
                {"label": "Shop Products", "url": reverse("shop")},
                {"label": "Boards & Panels", "url": reverse("shop_catalogue_main", kwargs={"main_slug": "boards-panels"})},
                {"label": "Modular Furniture", "url": reverse("shop_catalogue_main", kwargs={"main_slug": "modular-furniture"})},
                {"label": "Contact Phoenix", "url": "/#contact"},
            ],
        }
    if SENSITIVE_PATTERNS.search(message):
        return {
            "success": True,
            "message": "I can't provide private system information. I can help you with Phoenix Interior Hub products and store assistance.",
            "products": [],
            "categories": [],
            "actions": default_actions(),
        }
    if UNRELATED_PATTERNS.search(message):
        return {
            "success": True,
            "message": "I'm here to help with Phoenix Interior Hub products and store-related questions. What interior product can I help you find?",
            "products": [],
            "categories": [],
            "actions": default_actions(),
        }
    if any(term in lowered for term in ["order", "track", "delivery status", "my orders"]):
        if request.user.is_authenticated:
            return {
                "success": True,
                "message": "You can view your current and previous Phoenix orders from My Orders.",
                "products": [],
                "categories": [],
                "actions": [{"label": "View My Orders", "url": reverse("customer_orders")}],
            }
        return {
            "success": True,
            "message": "Please sign in to your Phoenix account to view your orders.",
            "products": [],
            "categories": [],
            "actions": [{"label": "Sign In", "url": reverse("login")}],
        }
    if any(term in lowered for term in ["contact", "phone", "email", "support", "whatsapp"]):
        return {
            "success": True,
            "message": "You can contact Phoenix from the support section of the website for current product help and pricing assistance.",
            "products": [],
            "categories": [],
            "actions": [{"label": "Contact Phoenix", "url": "/#contact"}],
        }
    return None


def faq_response(message):
    message_tokens = {token for token in re.findall(r"[a-z0-9]+", message.lower()) if len(token) > 2}
    if not message_tokens:
        return None
    try:
        for faq in ChatbotFAQ.objects.filter(is_active=True):
            keywords = {item.strip().lower() for item in faq.keywords.split(",") if item.strip()}
            question_tokens = {token for token in re.findall(r"[a-z0-9]+", faq.question.lower()) if len(token) > 2}
            if message_tokens & (keywords | question_tokens):
                return {
                    "success": True,
                    "message": faq.answer,
                    "products": [],
                    "categories": [],
                    "actions": default_actions(),
                }
    except (DatabaseError, OperationalError):
        return None
    return None


class GeminiChatService:
    def __init__(self):
        self.model = settings.GEMINI_MODEL
        self.api_key = settings.GEMINI_API_KEY
        self.last_gemini_status = None

    def ask(self, message, history=None, page_context=None, request=None):
        local = static_navigation_response(message, request) if request else None
        if local:
            return local

        faq = faq_response(message)
        if faq:
            return faq

        catalogue_context = find_relevant_catalogue_context(message, page_context=page_context)
        if not settings.CHATBOT_ENABLED or not self.api_key:
            if settings.CHATBOT_ENABLED and not self.api_key:
                logger.warning("GEMINI_API_KEY is not configured; using local chatbot fallback.")
            return self.local_catalogue_answer(message, catalogue_context)

        prompt = self.build_prompt(message, history or [], catalogue_context)
        answer = self.generate_with_rest_retry(prompt)
        if answer is None:
            return self.local_catalogue_answer(message, catalogue_context)

        if not answer:
            logger.warning("Gemini chatbot returned an empty or malformed response.")
            return self.local_catalogue_answer(message, catalogue_context)
        answer = self.sanitize_answer(answer)

        return {
            "success": True,
            "message": answer[:900],
            "products": catalogue_context["products"][:4],
            "categories": catalogue_context["categories"],
            "actions": self.verified_actions(catalogue_context),
        }

    def build_prompt(self, message, history, catalogue_context):
        limited_history = history[-settings.CHATBOT_MAX_HISTORY :]
        compact_context = {
            "catalogue_groups": CATALOGUE_GROUPS,
            "matched_products": catalogue_context["products"],
            "matched_categories": catalogue_context["categories"],
            "available_actions": catalogue_context["actions"],
        }
        return (
            f"{PHOENIX_SYSTEM_INSTRUCTION}\n\n"
            "Return only 1 to 4 short customer-facing sentences in plain text. Do not include HTML, markdown tables, raw URLs, or route paths. Django will attach verified product and category buttons separately.\n\n"
            f"Recent conversation: {json.dumps(limited_history, ensure_ascii=False)[:2000]}\n\n"
            f"Phoenix context: {json.dumps(compact_context, ensure_ascii=False)[:5000]}\n\n"
            f"Customer question: {message}"
        )

    def sanitize_answer(self, answer):
        answer = re.sub(r"https?://\S+", "", answer)
        answer = re.sub(r"/(?:product|shop|category|account|auth)/\S+", "", answer)
        sentences = re.split(r"(?<=[.!?])\s+", " ".join(answer.split()))
        return " ".join(sentences[:4]).strip()

    def generate_with_rest_retry(self, prompt):
        for attempt in range(1, 3):
            answer, status = self.generate_with_rest(prompt, attempt)
            if answer is not None:
                return answer
            if status not in {500, 503} or attempt >= 2:
                return None
            time.sleep(0.6)
        return None

    def generate_with_rest(self, prompt, attempt=1):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=18) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            status = exc.code
            self.last_gemini_status = status
            body = exc.read().decode("utf-8", errors="replace")[:500]
            body = body.replace(self.api_key, "[REDACTED_KEY]")
            self.log_gemini_http_error(status, body, attempt)
            return None, status
        except TimeoutError as exc:
            self.last_gemini_status = None
            logger.exception(
                "Gemini API request timed out. Type: %s. Model: %s. Status: unknown. Attempt: %s.",
                exc.__class__.__name__,
                self.model,
                attempt,
            )
            return None, None
        except Exception as exc:
            self.last_gemini_status = None
            logger.exception(
                "Gemini request failed before an HTTP status was available. Type: %s. Model: %s. Attempt: %s. Message: %s",
                exc.__class__.__name__,
                self.model,
                attempt,
                str(exc).replace(self.api_key, "[REDACTED_KEY]")[:500],
            )
            return None, None

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            logger.warning("Gemini returned malformed content. Model: %s. Attempt: %s.", self.model, attempt)
            return None, 200
        return " ".join(text.strip().split()), 200

    def log_gemini_http_error(self, status, safe_message, attempt):
        if status in {401, 403}:
            reason = "Gemini authentication failed."
        elif status == 404:
            reason = "Configured Gemini model is unavailable or invalid."
        elif status == 429:
            reason = "Gemini rate limit reached."
        elif status in {500, 503}:
            reason = "Gemini service temporarily unavailable."
        else:
            reason = "Gemini request failed."
        logger.error(
            "%s Model: %s. Status: %s. Attempt: %s. Message: %s",
            reason,
            self.model,
            status,
            attempt,
            safe_message,
        )

    def verified_actions(self, catalogue_context):
        actions = []
        for product in catalogue_context["products"][:3]:
            actions.append({"label": f"View {product['name']}", "url": product["url"]})
        actions.extend(catalogue_context["actions"])
        seen = set()
        unique = []
        for action in actions:
            key = (action["label"], action["url"])
            if key not in seen:
                unique.append(action)
                seen.add(key)
        return unique[:6] or default_actions()

    def local_catalogue_answer(self, message, catalogue_context):
        if catalogue_context["products"]:
            names = ", ".join(product["name"] for product in catalogue_context["products"][:3])
            return {
                "success": True,
                "message": f"I found Phoenix products that may help: {names}. Please open the product details to confirm specifications for your project.",
                "products": catalogue_context["products"][:4],
                "categories": catalogue_context["categories"],
                "actions": self.verified_actions(catalogue_context),
            }
        if catalogue_context["actions"]:
            return {
                "success": True,
                "message": "Phoenix has catalogue sections related to that request. You can explore the matching category pages below.",
                "products": [],
                "categories": catalogue_context["categories"],
                "actions": catalogue_context["actions"],
            }
        return {
            "success": True,
            "message": "I don't have enough information about that in the Phoenix catalogue. Please contact our team for assistance.",
            "products": [],
            "categories": [],
            "actions": default_actions(),
        }

    def unavailable_response(self):
        return {
            "success": False,
            "message": "Phoenix Assistant is temporarily unavailable. You can still browse our products or contact our team.",
            "products": [],
            "categories": [],
            "actions": default_actions(),
        }
