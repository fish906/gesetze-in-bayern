import smtplib
import os
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("mail")

_host = os.environ.get("SMTP_HOST")
_port = int(os.environ.get("SMTP_PORT", 587))
_user = os.environ.get("SMTP_USER")
_password = os.environ.get("SMTP_PASSWORD")
_from = os.environ.get("SMTP_FROM") or _user

_configured = bool(_host and _user and _password)
if not _configured:
    logger.warning("SMTP not configured — mails will not be sent (set SMTP_HOST, SMTP_USER, SMTP_PASSWORD)")


def send_mail(to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
    """Send an email via SMTP with STARTTLS.

    Silently skips if SMTP is not configured. Raises on connection/auth errors.
    """
    if not _configured:
        logger.warning(f"Mail not sent (SMTP unconfigured): to={to} subject={subject!r}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = _from
    msg["To"] = to

    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    if _port == 465:
        with smtplib.SMTP_SSL(_host, _port) as smtp:
            smtp.login(_user, _password)
            smtp.sendmail(_from, to, msg.as_string())
    else:
        with smtplib.SMTP(_host, _port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(_user, _password)
            smtp.sendmail(_from, to, msg.as_string())

    logger.info(f"Mail sent to {to!r}: {subject!r}")
