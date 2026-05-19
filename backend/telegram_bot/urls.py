from django.urls import path
from . import views

urlpatterns = [
    path("webhook/", views.telegram_webhook, name="telegram-webhook"),
    path("message/", views.chatbot_message, name="chatbot-message"),
    path("history/<int:chat_id>/", views.chatbot_history, name="chatbot-history"),
    path("link-user/", views.chatbot_link_user, name="chatbot-link-user"),
]
