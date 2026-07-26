"""
Server-side verification of Google ID tokens.

The frontend sends the raw `id_token` obtained from Google Sign-In; we must
never trust client-supplied identity fields (email, sub, name) without
verifying the token's signature, audience and issuer against Google.
"""
from typing import Any, Dict

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from app.core.config import settings

_GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class GoogleAuthError(Exception):
    """Raised when a Google ID token fails verification."""


def verify_google_id_token(token: str) -> Dict[str, Any]:
    """
    Verify a Google ID token and return its trusted claims.

    Checks performed:
    - Signature against Google's public keys
    - Expiry (`exp`)
    - Audience matches our GOOGLE_CLIENT_ID
    - Issuer is Google
    - The Google account email is verified
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise GoogleAuthError("Google OAuth is not configured on the server")

    try:
        claims = google_id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        raise GoogleAuthError("Invalid Google ID token") from exc

    if claims.get("iss") not in _GOOGLE_ISSUERS:
        raise GoogleAuthError("Invalid Google ID token issuer")

    if not claims.get("sub") or not claims.get("email"):
        raise GoogleAuthError("Google ID token is missing required claims")

    if not claims.get("email_verified"):
        raise GoogleAuthError("Google account email is not verified")

    return claims
