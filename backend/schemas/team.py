from pydantic import BaseModel


class TeamUserOut(BaseModel):
    user_id: str
    email: str
    role: str
    is_active: bool
    created_at: str | None = None
    last_login_at: str | None = None


class CreateUserIn(BaseModel):
    email: str
    password: str
    role: str
