import re
import uuid
import email.utils
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from core import decrypt_secret

VARIABLE_KEYS = [
    "first_name", "last_name", "full_name", "company", "position",
    "email", "phone", "city", "country", "website", "today",
]


def build_variable_map(contact: dict) -> dict:
    first = contact.get("first_name", "") or ""
    last = contact.get("last_name", "") or ""
    values = {
        "first_name": first,
        "last_name": last,
        "full_name": (first + " " + last).strip(),
        "company": contact.get("company", "") or "",
        "position": contact.get("position", "") or "",
        "email": contact.get("email", "") or "",
        "phone": contact.get("phone", "") or "",
        "city": contact.get("city", "") or "",
        "country": contact.get("country", "") or "",
        "website": contact.get("website", "") or "",
        "today": datetime.now().strftime("%d/%m/%Y"),
    }
    for key, val in (contact.get("custom_fields") or {}).items():
        values[key] = str(val)
    return values


def substitute(text: str, variables: dict) -> str:
    if not text:
        return ""
    def repl(match):
        key = match.group(1).strip()
        return str(variables.get(key, match.group(0)))
    return re.sub(r"\{([a-zA-Z0-9_]+)\}", repl, text)


def rewrite_links(html: str, base_url: str, tracking_id: str) -> str:
    if not html:
        return ""
    def repl(match):
        quote = match.group(1)
        url = match.group(2)
        if url.startswith("mailto:") or url.startswith("#"):
            return match.group(0)
        tracked = f"{base_url}/api/track/click/{tracking_id}?url={email.utils.quote(url)}"
        return f'href={quote}{tracked}{quote}'
    return re.sub(r'href=(["\'])(.*?)\1', repl, html)


def inject_open_pixel(html: str, base_url: str, tracking_id: str) -> str:
    pixel = f'<img src="{base_url}/api/track/open/{tracking_id}.png" width="1" height="1" alt="" style="display:none" />'
    if "</body>" in html.lower():
        idx = html.lower().rfind("</body>")
        return html[:idx] + pixel + html[idx:]
    return html + pixel


async def send_email(
    smtp_account: dict,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
):
    password = decrypt_secret(smtp_account.get("password_enc", ""))
    from_name = smtp_account.get("from_name", "")
    from_email = smtp_account.get("from_email", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email.utils.formataddr((from_name, from_email))
    msg["To"] = to_email
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=from_email.split("@")[-1] if "@" in from_email else None)
    msg["MIME-Version"] = "1.0"
    reply_to = smtp_account.get("reply_to")
    if reply_to:
        msg["Reply-To"] = reply_to

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    use_ssl = smtp_account.get("use_ssl", False)
    use_tls = smtp_account.get("use_tls", True)
    port = smtp_account.get("port", 587)
    host = smtp_account.get("host")

    username = smtp_account.get("username") or None
    await aiosmtplib.send(
        msg,
        hostname=host,
        port=port,
        username=username,
        password=password if username else None,
        use_tls=use_ssl,          # implicit SSL (usually port 465)
        start_tls=use_tls and not use_ssl,  # STARTTLS (usually port 587)
        timeout=30,
    )
    return msg["Message-ID"]


async def test_smtp_connection(host, port, username, password, use_ssl, use_tls):
    try:
        smtp = aiosmtplib.SMTP(
            hostname=host,
            port=port,
            use_tls=use_ssl,
            start_tls=False,
            timeout=20,
        )
        await smtp.connect()
        if use_tls and not use_ssl:
            try:
                await smtp.starttls()
            except aiosmtplib.SMTPException:
                pass
        if username:
            await smtp.login(username, password)
        await smtp.quit()
        return True, "Ligação estabelecida com sucesso."
    except Exception as e:
        return False, f"Falha na ligação: {str(e)}"
