from datetime import datetime

from pydantic import BaseModel


class TeamUserOut(BaseModel):
    user_id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime | None = None
    last_login_at: datetime | None = None


class CreateUserIn(BaseModel):
    email: str
    password: str
    role: str
