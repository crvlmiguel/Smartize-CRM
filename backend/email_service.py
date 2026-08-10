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
    """Convert HTML to clean plain text, treating block/table elements as line breaks
    so structured signatures (name / role / phone / email / website) never end up glued together."""
    if not html:
        return ""
    text = html
    # Drop non-visible sections entirely.
    text = re.sub(r"(?is)<(script|style|head)\b[^>]*>.*?</\1>", "", text)
    # Explicit line breaks.
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    # Block/table element boundaries -> line break (each item on its own line).
    text = re.sub(
        r"(?i)</(p|div|tr|td|th|table|h[1-6]|li|ul|ol|blockquote|header|footer|section|article)>",
        "\n", text,
    )
    # Strip remaining (inline) tags.
    text = re.sub(r"<[^>]+>", "", text)
    # Decode the common HTML entities.
    for a, b in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'"), ("&#160;", " ")]:
        text = text.replace(a, b)
    text = text.replace("\xa0", " ")
    # Tidy: trim each line, drop empty lines, collapse spaces within a line.
    lines = []
    for raw in text.split("\n"):
        ln = re.sub(r"[ \t]{2,}", " ", raw).strip()
        if ln:
            lines.append(ln)
    return "\n".join(lines).strip()


def html_has_visible_content(html: str) -> bool:
    """True if the HTML carries real content (text or an image), not just empty editor markup like <br>/<p></p>/&nbsp;."""
    if not html:
        return False
    if re.search(r"<img\b", html, flags=re.I):
        return True
    return bool(html_to_text(html).replace("\xa0", " ").strip())


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
    """Wrap content as a natural, plain-looking email — no container box, background or borders."""
    return (
        '<!DOCTYPE html><html lang="pt"><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8"></head>'
        '<body style="margin:0;padding:0;">'
        f'<div style="font-family:{EMAIL_FONT};font-size:15px;line-height:1.6;color:#000000;word-break:break-word;">'
        f'{inner_html}'
        '</div>'
        '</body></html>'
    )


def text_to_html(text: str) -> str:
    """Convert a plain-text body into simple, natural HTML (escaped, newlines -> <br>)."""
    if not text:
        return ""
    import html as _html
    return _html.escape(text).replace("\n", "<br>\n")


def compose_email_html(content_html: str, signature_html: str = "") -> str:
    """Assemble the final email HTML (content + signature) with a natural, non-boxed look."""
    inner = _ensure_img_email_safe(content_html or "")
    if signature_html:
        inner += '<br><br>' + _ensure_img_email_safe(signature_html)
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
