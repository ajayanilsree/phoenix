from django.db import models


class ChatbotFAQ(models.Model):
    question = models.CharField(max_length=220)
    answer = models.TextField()
    keywords = models.CharField(max_length=300, blank=True, help_text="Comma-separated keywords that should match this FAQ.")
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "question"]
        verbose_name = "Chatbot FAQ"
        verbose_name_plural = "Chatbot FAQs"

    def __str__(self):
        return self.question
