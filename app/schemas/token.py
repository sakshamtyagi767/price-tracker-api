from pydantic import BaseModel
from typing import Optional


class Token(BaseModel):
    """The JSON returned on successful login."""

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """The data decoded from inside the JWT."""

    sub: Optional[str] = None
