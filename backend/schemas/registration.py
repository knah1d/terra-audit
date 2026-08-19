from pydantic import BaseModel


class RegisterRequest(BaseModel):
    # Plain str fields, matching LoginRequest's convention (no EmailStr —
    # avoids the extra email-validator dependency; src.auth doesn't
    # format-validate emails either).
    org_name: str
    email: str
    password: str


class RegisterOtpSentResponse(BaseModel):
    email: str
    expires_in_seconds: int


class VerifyOtpRequest(BaseModel):
    email: str
    otp: str
