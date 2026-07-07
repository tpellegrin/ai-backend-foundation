from app.auth.adapters.argon2_hasher import Argon2PasswordHasher
from app.auth.adapters.jwt_signer import JwtSigner
from app.auth.ports import PasswordHasher, TokenSigner
from app.core.config.settings import AppSettings


def setup_password_hasher(settings: AppSettings) -> PasswordHasher:
    """Wire the password hasher using Argon2 settings."""
    return Argon2PasswordHasher(
        time_cost=settings.argon2.time_cost,
        memory_cost=settings.argon2.memory_cost,
        parallelism=settings.argon2.parallelism,
        hash_len=settings.argon2.hash_len,
        salt_len=settings.argon2.salt_len,
    )


def setup_token_signer(settings: AppSettings) -> TokenSigner:
    """Wire the token signer using JWT settings."""
    return JwtSigner(
        private_key=settings.jwt.private_key.get_secret_value(),
        public_key=settings.jwt.public_key.get_secret_value(),
        issuer=settings.jwt.issuer,
        audience=settings.jwt.audience,
        access_ttl_seconds=settings.jwt.access_ttl_seconds,
    )
