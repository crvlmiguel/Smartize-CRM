import re
import uuid
import email.utils
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from core import decrypt_secret

VARIABLE_KEYS = [
    "first_name", "last_name", "saudacao", "full_name", "company", "position",
    "email", "phone", "city", "country", "website", "today",
]


def build_variable_map(contact: dict) -> dict:
    first = contact.get("first_name", "") or ""
    last = contact.get("last_name", "") or ""
    values = {
        "first_name": first,
        "last_name": last,
        "saudacao": contact.get("saudacao", "") or "",
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
    # Supports both {var} and {{var}} syntaxes.
    return re.sub(r"\{\{?\s*([a-zA-Z0-9_]+)\s*\}?\}", repl, text)


def html_to_text(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", html)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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


EMAIL_FONT = "Arial, Helvetica, sans-serif"


def _ensure_img_email_safe(html: str) -> str:
    """Make every <img> resize gracefully in email clients without dropping an explicit width."""
    if not html:
        return ""
    def repl(m):
        tag = m.group(0)
        sm = re.search(r'style=(["\'])(.*?)\1', tag, flags=re.I)
        if sm:
            existing = sm.group(2).rstrip().rstrip(";")
            # Detect real CSS properties (not substrings like 'line-height'/'border-style').
            def has_prop(css, prop):
                return re.search(r'(^|;)\s*' + re.escape(prop) + r'\s*:', css, flags=re.I) is not None
            # Drop border-* shorthands the browser injects (e.g. border-style:initial).
            existing = re.sub(r'(^|;)\s*border(-[a-z]+)?\s*:[^;]*', r'\1', existing, flags=re.I)
            existing = re.sub(r';{2,}', ';', existing).strip(";").strip()
            extra = []
            if not has_prop(existing, "max-width"):
                extra.append("max-width:100%")
            if not has_prop(existing, "height"):
                extra.append("height:auto")
            extra.append("border:0")
            merged = ";".join([p for p in [existing] + extra if p])
            return tag[:sm.start()] + f'style="{merged}"' + tag[sm.end():]
        return re.sub(r"<img\b", '<img style="max-width:100%;height:auto;border:0;"', tag, count=1, flags=re.I)
    return re.sub(r"<img\b[^>]*>", repl, html, flags=re.I)


def wrap_email_html(inner_html: str) -> str:
    """Wrap content in an email-safe, table-based, 600px responsive container with inline styles."""
    return (
        '<!DOCTYPE html><html lang="pt"><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8"></head>'
        '<body style="margin:0;padding:0;background-color:#f4f4f5;-webkit-text-size-adjust:100%;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f4f5;">'
        '<tr><td align="center" style="padding:24px 12px;">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
        'style="width:600px;max-width:600px;background-color:#ffffff;border-radius:8px;border:1px solid #e4e4e7;">'
        f'<tr><td style="padding:28px 32px;font-family:{EMAIL_FONT};font-size:15px;line-height:1.6;color:#0a0a0a;word-break:break-word;">'
        f'{inner_html}'
        '</td></tr></table>'
        '</td></tr></table></body></html>'
    )


def compose_email_html(content_html: str, signature_html: str = "") -> str:
    """Assemble the final, email-client-safe HTML document (content + signature)."""
    inner = _ensure_img_email_safe(content_html or "")
    if signature_html:
        inner += (
            '<div style="margin-top:24px;padding-top:16px;border-top:1px solid #e4e4e7;">'
            f'{_ensure_img_email_safe(signature_html)}</div>'
        )
    return wrap_email_html(inner)


def inject_open_pixel(html: str, base_url: str, tracking_id: str) -> str:
    # No display:none — hidden images are often skipped by mail clients,
    # which prevents open tracking from firing. Use a tiny 1x1 image instead.
    pixel = f'<img src="{base_url}/api/track/open/{tracking_id}.png?t=1" width="1" height="1" border="0" alt="" style="width:1px;height:1px;border:0;margin:0;padding:0;" />'
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
    in_reply_to: str = None,
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
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to

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
