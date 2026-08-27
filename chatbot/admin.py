from django.contrib import admin

from .models import ChatbotFAQ


@admin.register(ChatbotFAQ)
class ChatbotFAQAdmin(admin.ModelAdmin):
    list_display = ("question", "display_order", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("question", "answer", "keywords")
    ordering = ("display_order", "question")
