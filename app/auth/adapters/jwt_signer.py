import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.auth.ports import TokenSigner
from app.shared.errors import AuthenticationError


class JwtSigner(TokenSigner):
    """JWT signer with asymmetric keys (RS256)."""

    def __init__(
        self,
        private_key: str,
        public_key: str,
        issuer: str,
        audience: str,
        access_ttl_seconds: int,
    ) -> None:
        """Initialize the signer with keys and settings.

        Args:
            private_key: PEM-encoded private key for signing.
            public_key: PEM-encoded public key for verification.
            issuer: Expected 'iss' claim.
            audience: Expected 'aud' claim.
            access_ttl_seconds: Default TTL for tokens.
        """
        self._private_key = private_key
        self._public_key = public_key
        self._issuer = issuer
        self._audience = audience
        self._access_ttl_seconds = access_ttl_seconds
        self._algorithm = "RS256"
        self._leeway = 30

    def sign(self, claims: Mapping[str, Any]) -> str:
        """Sign a set of claims into a token."""
        now = datetime.now(UTC)

        payload = dict(claims)

        # Standard claims
        if "iss" not in payload:
            payload["iss"] = self._issuer
        if "aud" not in payload:
            payload["aud"] = self._audience
        if "iat" not in payload:
            payload["iat"] = now
        if "exp" not in payload:
            payload["exp"] = now + timedelta(seconds=self._access_ttl_seconds)
        if "jti" not in payload:
            payload["jti"] = str(uuid.uuid4())

        return jwt.encode(
            payload,
            self._private_key,
            algorithm=self._algorithm,
        )

    def verify(self, token: str) -> Mapping[str, Any]:
        """Verify a token and return the contained claims."""
        try:
            return jwt.decode(
                token,
                self._public_key,
                algorithms=[self._algorithm],
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
            )
        except jwt.ExpiredSignatureError as e:
            raise AuthenticationError(detail="Token has expired") from e
        except jwt.InvalidIssuerError as e:
            raise AuthenticationError(detail="Invalid token issuer") from e
        except jwt.InvalidAudienceError as e:
            raise AuthenticationError(detail="Invalid token audience") from e
        except jwt.PyJWTError as e:
            raise AuthenticationError(detail=f"Invalid token: {e!s}") from e
