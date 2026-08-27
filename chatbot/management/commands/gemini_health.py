import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Safely checks Gemini connectivity without printing the API key."

    def handle(self, *args, **options):
        if not settings.GEMINI_API_KEY:
            raise CommandError("GEMINI_API_KEY is not configured.")

        self.stdout.write(f"API key configured: YES")
        self.stdout.write(f"Model configured: {settings.GEMINI_MODEL}")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
        payload = json.dumps(
            {
                "contents": [
                    {
                        "parts": [
                            {"text": "Reply exactly: Phoenix API working"},
                        ]
                    }
                ]
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": settings.GEMINI_API_KEY,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            body = body.replace(settings.GEMINI_API_KEY, "[REDACTED_KEY]")
            safe_message = body[:500]
            raise CommandError(
                f"Gemini health check failed. Type: HTTPError. Status: {exc.code}. Model: {settings.GEMINI_MODEL}. Message: {safe_message}"
            ) from exc
        except Exception as exc:
            safe_message = str(exc).replace(settings.GEMINI_API_KEY, "[REDACTED_KEY]")[:500]
            raise CommandError(
                f"Gemini health check failed. Type: {exc.__class__.__name__}. Status: unknown. Model: {settings.GEMINI_MODEL}. Message: {safe_message}"
            ) from exc

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise CommandError(f"Gemini health check returned malformed content. Model: {settings.GEMINI_MODEL}.") from exc
        text = " ".join(text.strip().split())
        self.stdout.write(f"Gemini response: {text}")
