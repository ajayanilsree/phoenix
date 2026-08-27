from django.urls import path

from .views import chatbot_message

urlpatterns = [
    path("message/", chatbot_message, name="chatbot_message"),
]
