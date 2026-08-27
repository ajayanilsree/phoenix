from django.conf import settings


def chatbot_settings(request):
    return {"CHATBOT_ENABLED": settings.CHATBOT_ENABLED}
