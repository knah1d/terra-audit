from pydantic import BaseModel


class LoginRequest(BaseModel):
    # Plain str, not EmailStr: avoids an extra `email-validator` dependency,
    # and src.auth.get_user_by_email doesn't format-validate either — it
    # just strips/lowercases before lookup, so this matches that contract.
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    user_id: str
    org_id: str
    email: str
    role: str
