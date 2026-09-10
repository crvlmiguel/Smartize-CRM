from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr


# ---------------- Auth ----------------
class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = "Utilizador"


# ---------------- Contacts ----------------
class ContactCreate(BaseModel):
    first_name: str = ""
    last_name: str = ""
    saudacao: str = ""
    company: str = ""
    position: str = ""
    email: str
    phone: str = ""
    city: str = ""
    country: str = ""
    website: str = ""
    group_id: Optional[str] = None
    status: str = "ativo"  # ativo, respondido, bounce, descadastrado
    notes: str = ""
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class ContactUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    saudacao: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    group_id: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None


class BulkDeleteRequest(BaseModel):
    ids: List[str] = Field(default_factory=list)


# ---------------- Groups ----------------
class GroupCreate(BaseModel):
    name: str
    description: str = ""


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


# ---------------- Templates ----------------
class TemplateCreate(BaseModel):
    name: str
    subject: str = ""
    content_html: str = ""
    content_text: str = ""
    type: str = "plain"  # plain | html


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    content_html: Optional[str] = None
    content_text: Optional[str] = None
    type: Optional[str] = None


class TemplateTestSend(BaseModel):
    to_email: str
    subject: str = ""
    content_html: str = ""
    content_text: str = ""
    type: str = "plain"
    smtp_account_id: Optional[str] = None


# ---------------- SMTP ----------------
class SmtpCreate(BaseModel):
    name: str
    account_type: str = "smtp"  # smtp | google
    from_name: str
    from_email: str
    host: str
    port: int = 587
    use_ssl: bool = False
    use_tls: bool = True
    username: str
    password: str = ""
    reply_to: Optional[str] = None
    signature_html: str = ""
    signature_text: str = ""
    daily_limit: int = 200
    status: str = "ativo"
    is_default: bool = False
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    imap_password: Optional[str] = None


class SmtpUpdate(BaseModel):
    name: Optional[str] = None
    account_type: Optional[str] = None
    from_name: Optional[str] = None
    from_email: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    use_ssl: Optional[bool] = None
    use_tls: Optional[bool] = None
    username: Optional[str] = None
    password: Optional[str] = None
    reply_to: Optional[str] = None
    signature_html: Optional[str] = None
    signature_text: Optional[str] = None
    daily_limit: Optional[int] = None
    status: Optional[str] = None
    is_default: Optional[bool] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    imap_password: Optional[str] = None


class SmtpTestRequest(BaseModel):
    host: str
    port: int = 587
    use_ssl: bool = False
    use_tls: bool = True
    username: str
    password: str = ""
    from_email: Optional[str] = None
    smtp_account_id: Optional[str] = None  # to reuse stored password


# ---------------- Campaigns ----------------
class CampaignSettings(BaseModel):
    min_interval_seconds: int = 30
    max_interval_seconds: int = 90
    emails_per_hour: int = 30
    emails_per_day: int = 200
    business_days_only: bool = True
    business_hour_start: int = 9
    business_hour_end: int = 18
    timezone: str = "Europe/Lisbon"


class SequenceStep(BaseModel):
    template_id: str
    subject: Optional[str] = None
    send_type: str = "new"  # new | reply
    delay_days: int = 0
    delay_hours: int = 0


class CampaignCreate(BaseModel):
    name: str
    smtp_account_id: Optional[str] = None
    group_id: str
    template_id: Optional[str] = None
    type: str = "normal"  # normal | newsletter
    schedule_at: Optional[str] = None  # ISO string; None = send now
    settings: CampaignSettings = Field(default_factory=CampaignSettings)
    is_sequence: bool = False
    steps: List[SequenceStep] = Field(default_factory=list)


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    smtp_account_id: Optional[str] = None
    group_id: Optional[str] = None
    template_id: Optional[str] = None
    type: Optional[str] = None
    schedule_at: Optional[str] = None
    settings: Optional[CampaignSettings] = None


# ---------------- Settings ----------------
class SettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    logo_url: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    footer: Optional[str] = None


# ---------------- SMTP test send ----------------
class SmtpTestSendRequest(BaseModel):
    smtp_account_id: str
    to_email: str
    signature_html: Optional[str] = None
