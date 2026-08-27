import json
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .services import GeminiChatService, default_actions


def client_key(request):
    session_key = request.session.session_key
    if not session_key:
        request.session.save()
        session_key = request.session.session_key
    ip_address = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")).split(",")[0]
    return f"chatbot:{session_key or ip_address}"


def rate_limited(request):
    key = client_key(request)
    now = time.time()
    recent = cache.get(key, [])
    recent = [timestamp for timestamp in recent if now - timestamp < 60]
    if recent and now - recent[-1] < 1.5:
        return True
    if len(recent) >= 18:
        return True
    recent.append(now)
    cache.set(key, recent, 70)
    return False


@require_POST
def chatbot_message(request):
    content_type = request.headers.get("Content-Type", "")
    if "application/json" not in content_type:
        return JsonResponse({"success": False, "message": "Please send a valid chatbot request.", "products": [], "categories": [], "actions": default_actions()}, status=400)

    if rate_limited(request):
        return JsonResponse(
            {
                "success": False,
                "message": "Please wait a moment before sending another message.",
                "products": [],
                "categories": [],
                "actions": default_actions(),
            },
            status=429,
        )

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"success": False, "message": "Sorry, I couldn't process that request. Please try again.", "products": [], "categories": [], "actions": default_actions()}, status=400)

    message = str(payload.get("message", "")).strip()
    max_length = settings.CHATBOT_MAX_MESSAGE_LENGTH
    if not message:
        return JsonResponse({"success": False, "message": "Please enter a question about Phoenix products.", "products": [], "categories": [], "actions": []}, status=400)
    if len(message) > max_length:
        return JsonResponse({"success": False, "message": f"Please keep your message under {max_length} characters.", "products": [], "categories": [], "actions": []}, status=400)

    history = payload.get("history", [])
    if not isinstance(history, list):
        history = []
    clean_history = []
    for item in history[-settings.CHATBOT_MAX_HISTORY :]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = str(item.get("content", ""))[:500]
        if role in {"user", "assistant"} and text:
            clean_history.append({"role": role, "content": text})

    page_context = payload.get("page_context", {})
    if not isinstance(page_context, dict):
        page_context = {}

    result = GeminiChatService().ask(message, history=clean_history, page_context=page_context, request=request)
    return JsonResponse(
        {
            "success": bool(result.get("success", True)),
            "message": str(result.get("message", ""))[:1000],
            "products": result.get("products", [])[:4],
            "categories": result.get("categories", [])[:5],
            "actions": result.get("actions", [])[:6],
        },
        status=200 if result.get("success", True) else 503,
    )
