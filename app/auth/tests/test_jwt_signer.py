# ruff: noqa: S101
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from freezegun import freeze_time

from app.auth.adapters.jwt_signer import JwtSigner
from app.auth.ports import TokenSigner
from app.shared.errors import AuthenticationError


@pytest.fixture
def rsa_keys() -> tuple[str, str]:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


@pytest.fixture
def signer(rsa_keys: tuple[str, str]) -> JwtSigner:
    private_pem, public_pem = rsa_keys
    return JwtSigner(
        private_key=private_pem,
        public_key=public_pem,
        issuer="test-issuer",
        audience="test-audience",
        access_ttl_seconds=900,
    )


@pytest.mark.unit
def test_jwt_signer_implements_protocol(signer: JwtSigner) -> None:
    assert isinstance(signer, TokenSigner)


@pytest.mark.unit
def test_sign_verify_roundtrip(signer: JwtSigner) -> None:
    claims = {"sub": "user-123", "tid": "tenant-456", "scope": "read:all"}
    token = signer.sign(claims)

    verified_claims = signer.verify(token)

    assert verified_claims["sub"] == "user-123"
    assert verified_claims["tid"] == "tenant-456"
    assert verified_claims["scope"] == "read:all"
    assert verified_claims["iss"] == "test-issuer"
    assert verified_claims["aud"] == "test-audience"
    assert "iat" in verified_claims
    assert "exp" in verified_claims
    assert "jti" in verified_claims


@pytest.mark.unit
def test_verify_invalid_token(signer: JwtSigner) -> None:
    with pytest.raises(AuthenticationError):
        signer.verify("invalid-token")


@pytest.mark.unit
def test_verify_tampered_token(signer: JwtSigner) -> None:
    claims = {"sub": "user-123"}
    token = signer.sign(claims)

    # Tamper with the token by changing a character in the signature
    parts = token.split(".")
    signature = list(parts[2])
    # Change the first character of the signature
    signature[0] = "A" if signature[0] != "A" else "B"
    tampered_token = f"{parts[0]}.{parts[1]}.{''.join(signature)}"

    with pytest.raises(AuthenticationError):
        signer.verify(tampered_token)


@pytest.mark.unit
def test_verify_expired_token(signer: JwtSigner) -> None:
    with freeze_time("2023-01-01 12:00:00"):
        claims = {"sub": "user-123"}
        token = signer.sign(claims)

    # 15 minutes + 31 seconds later (TTL is 900s, leeway is 30s)
    with freeze_time("2023-01-01 12:15:31"):
        with pytest.raises(AuthenticationError) as exc:
            signer.verify(token)
        assert "expired" in str(exc.value.detail).lower()


@pytest.mark.unit
def test_verify_clock_skew_tolerance(signer: JwtSigner) -> None:
    # Expired by 20s, but within 30s tolerance
    with freeze_time("2023-01-01 12:00:00"):
        claims = {"sub": "user-123"}
        token = signer.sign(claims)

    with freeze_time("2023-01-01 12:15:20"):  # 20s past expiration (920s total)
        verified_claims = signer.verify(token)
        assert verified_claims["sub"] == "user-123"


@pytest.mark.unit
def test_verify_wrong_audience(signer: JwtSigner) -> None:
    # Create a token with wrong audience manually via signer.sign override
    token = signer.sign({"sub": "user-123", "aud": "wrong-audience"})

    with pytest.raises(AuthenticationError) as exc:
        signer.verify(token)
    assert "audience" in str(exc.value.detail).lower()


@pytest.mark.unit
def test_verify_wrong_issuer(signer: JwtSigner) -> None:
    # Create a token with wrong issuer manually via signer.sign override
    token = signer.sign({"sub": "user-123", "iss": "wrong-issuer"})

    with pytest.raises(AuthenticationError) as exc:
        signer.verify(token)
    assert "issuer" in str(exc.value.detail).lower()


@pytest.mark.unit
def test_sign_respects_provided_claims(signer: JwtSigner) -> None:
    with freeze_time("2023-01-01 12:00:00"):
        custom_iat = int(datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC).timestamp())
        custom_exp = int(datetime(2023, 1, 1, 13, 0, 0, tzinfo=UTC).timestamp())
        claims = {
            "sub": "user-123",
            "iss": "test-issuer",
            "aud": "test-audience",
            "iat": custom_iat,
            "exp": custom_exp,
            "jti": "custom-jti",
        }
        token = signer.sign(claims)

        verified_claims = signer.verify(token)

        assert verified_claims["iss"] == "test-issuer"
        assert verified_claims["aud"] == "test-audience"
        assert verified_claims["iat"] == custom_iat
        assert verified_claims["exp"] == custom_exp
        assert verified_claims["jti"] == "custom-jti"
