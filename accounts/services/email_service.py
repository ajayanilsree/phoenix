from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string


def send_password_reset_otp(user, otp):
    context = {"otp": otp, "user": user}
    text_body = render_to_string("emails/password_reset_otp.txt", context)
    html_body = render_to_string("emails/password_reset_otp.html", context)
    message = EmailMultiAlternatives(
        subject="Reset your Phoenix Interior Hub password",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def send_test_email(recipient):
    return send_mail(
        "Phoenix Interior Hub Email Test",
        "Brevo SMTP integration is working correctly.",
        settings.DEFAULT_FROM_EMAIL,
        [recipient],
        fail_silently=False,
    )
