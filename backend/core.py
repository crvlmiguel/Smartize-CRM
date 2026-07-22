import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from cryptography.fernet import Fernet

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

_fernet = Fernet(os.environ["ENCRYPTION_KEY"].encode())


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return _fernet.encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except Exception:
        return ""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat()


def _validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    return str(v)


PyObjectId = Annotated[str, BeforeValidator(_validate_object_id)]


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc: Optional[dict]):
        if not doc:
            return None
        return cls(**doc)

    def to_mongo(self, exclude_none: bool = False) -> dict:
        data = self.model_dump(by_alias=True, exclude_none=exclude_none)
        if data.get("_id") is None:
            data.pop("_id", None)
        return data
