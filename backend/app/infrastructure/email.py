"""SMTP delivery for account emails; no token or email body is logged."""

import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode, urlsplit, urlunsplit

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError


def require_email_configuration() -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        raise ServiceUnavailableError("Email delivery is not configured.")
    if settings.smtp_ssl and settings.smtp_starttls:
        raise ServiceUnavailableError("Choose either SMTP SSL or STARTTLS.")


def action_link(url: str, token: str) -> str:
    # A fragment keeps the token out of web-server query logs and referrers.
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            parts.query,
            urlencode({"token": token}),
        )
    )


def send_action_email(recipient: str, token: str, *, reset_password: bool) -> None:
    require_email_configuration()
    url = (
        settings.password_reset_url
        if reset_password
        else settings.email_verification_url
    )
    subject = (
        "Reset your TalkFiesta password"
        if reset_password
        else "Verify your TalkFiesta email"
    )
    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(
        f"{subject}\n\n{action_link(url, token)}\n\n"
        "This link expires and can only be used once. "
        "If you did not request it, you can ignore this email.\n"
    )
    context = ssl.create_default_context()
    options = {
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "timeout": settings.smtp_timeout_seconds,
    }
    connection = (
        smtplib.SMTP_SSL(**options, context=context)
        if settings.smtp_ssl
        else smtplib.SMTP(**options)
    )
    with connection as smtp:
        if settings.smtp_starttls:
            smtp.starttls(context=context)
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
