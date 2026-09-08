from datetime import UTC, datetime, timedelta
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import (
    create_access_token,
    generate_otp,
    generate_refresh_token,
    hash_password,
    hash_token,
    refresh_token_expires_at,
    verify_password,
)
from app.models import RefreshToken, User, VerificationCode, VerificationPurpose
from app.schemas.auth import TokenResponse, UserResponse
from app.services.email import send_password_reset_email, send_verification_email

logger = logging.getLogger(__name__)


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_github_id(db: AsyncSession, github_id: str) -> User | None:
    result = await db.execute(select(User).where(User.github_id == github_id))
    return result.scalar_one_or_none()


def user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_verified=user.is_verified,
        github_username=user.github_username,
        avatar_url=user.avatar_url,
    )


async def _create_verification_code(
    db: AsyncSession,
    user: User,
    purpose: VerificationPurpose,
) -> str:
    settings = get_settings()
    code = generate_otp()
    expires = datetime.now(UTC) + timedelta(minutes=settings.otp_expire_minutes)

    db.add(
        VerificationCode(
            user_id=user.id,
            code=code,
            purpose=purpose.value,
            expires_at=expires,
        )
    )
    return code


async def _dispatch_verification_email(
    user: User, code: str, purpose: VerificationPurpose
) -> bool:
    try:
        if purpose == VerificationPurpose.EMAIL_OTP:
            return await send_verification_email(user.email, user.full_name, code)
        return await send_password_reset_email(user.email, user.full_name, code)
    except Exception as exc:
        if get_settings().debug:
            logger.warning("Email send failed (debug): %s", exc)
            return False
        raise AuthError("Unable to send email. Please try again later.", 503) from exc


def _dev_code_if_email_unsent(code: str, email_sent: bool) -> str | None:
    return code if get_settings().debug and not email_sent else None


async def _issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    settings = get_settings()
    access_token = create_access_token(user.id)
    refresh_token = generate_refresh_token()
    expires_at = refresh_token_expires_at()

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=expires_at,
        )
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        refresh_expires_in=settings.jwt_refresh_token_expire_days * 86400,
        user=user_to_response(user),
    )


async def register_user(
    db: AsyncSession, email: str, password: str, full_name: str
) -> tuple[User, str | None]:
    email = email.lower()
    existing = await get_user_by_email(db, email)
    if existing:
        if not existing.is_verified:
            await resend_otp(db, email)
            raise AuthError(
                "An account with this email already exists but is not verified. "
                "A new verification code has been sent.",
                409,
            )
        raise AuthError(
            "An account with this email already exists. Please sign in instead.",
            409,
        )

    user = User(
        email=email,
        full_name=full_name.strip(),
        hashed_password=hash_password(password),
        is_verified=False,
    )
    db.add(user)
    await db.flush()

    code = await _create_verification_code(db, user, VerificationPurpose.EMAIL_OTP)
    email_sent = await _dispatch_verification_email(
        user, code, VerificationPurpose.EMAIL_OTP
    )
    return user, _dev_code_if_email_unsent(code, email_sent)


async def verify_email_otp(db: AsyncSession, email: str, code: str) -> TokenResponse:
    user = await get_user_by_email(db, email.lower())
    if not user:
        raise AuthError("Invalid verification code", 400)

    now = datetime.now(UTC)
    result = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.user_id == user.id,
            VerificationCode.purpose == VerificationPurpose.EMAIL_OTP.value,
            VerificationCode.code == code,
            VerificationCode.used_at.is_(None),
            VerificationCode.expires_at > now,
        )
        .order_by(VerificationCode.created_at.desc())
    )
    verification = result.scalar_one_or_none()
    if not verification:
        raise AuthError("Invalid or expired verification code", 400)

    verification.used_at = now
    user.is_verified = True
    return await _issue_tokens(db, user)


async def resend_otp(db: AsyncSession, email: str) -> str | None:
    user = await get_user_by_email(db, email.lower())
    if not user:
        return None
    if user.is_verified:
        raise AuthError("Email is already verified", 400)

    code = await _create_verification_code(db, user, VerificationPurpose.EMAIL_OTP)
    email_sent = await _dispatch_verification_email(
        user, code, VerificationPurpose.EMAIL_OTP
    )
    return _dev_code_if_email_unsent(code, email_sent)


async def login_user(db: AsyncSession, email: str, password: str) -> TokenResponse:
    user = await get_user_by_email(db, email.lower())
    if not user or not verify_password(password, user.hashed_password):
        raise AuthError("Invalid email or password", 401)
    if not user.is_verified:
        await resend_otp(db, email.lower())
        raise AuthError("Please verify your email before signing in", 403)

    return await _issue_tokens(db, user)


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
    token_hash = hash_token(refresh_token)
    now = datetime.now(UTC)

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
    )
    stored = result.scalar_one_or_none()
    if not stored:
        raise AuthError("Invalid or expired refresh token", 401)

    user = await get_user_by_id(db, stored.user_id)
    if not user:
        raise AuthError("User not found", 401)

    stored.revoked_at = now
    return await _issue_tokens(db, user)


async def logout_user(db: AsyncSession, refresh_token: str) -> None:
    token_hash = hash_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored = result.scalar_one_or_none()
    if stored:
        stored.revoked_at = datetime.now(UTC)


async def forgot_password(db: AsyncSession, email: str) -> str | None:
    user = await get_user_by_email(db, email.lower())
    if not user:
        return None

    code = await _create_verification_code(
        db, user, VerificationPurpose.PASSWORD_RESET
    )
    email_sent = await _dispatch_verification_email(
        user, code, VerificationPurpose.PASSWORD_RESET
    )
    return _dev_code_if_email_unsent(code, email_sent)


async def reset_password(
    db: AsyncSession, email: str, code: str, new_password: str
) -> None:
    user = await get_user_by_email(db, email.lower())
    if not user:
        raise AuthError("Invalid reset code", 400)

    now = datetime.now(UTC)
    result = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.user_id == user.id,
            VerificationCode.purpose == VerificationPurpose.PASSWORD_RESET.value,
            VerificationCode.code == code,
            VerificationCode.used_at.is_(None),
            VerificationCode.expires_at > now,
        )
        .order_by(VerificationCode.created_at.desc())
    )
    verification = result.scalar_one_or_none()
    if not verification:
        raise AuthError("Invalid or expired reset code", 400)

    verification.used_at = now
    user.hashed_password = hash_password(new_password)
    user.is_verified = True


async def get_or_create_github_user(
    db: AsyncSession,
    github_id: str,
    email: str,
    full_name: str,
    github_username: str,
    avatar_url: str | None,
    github_access_token: str | None = None,
) -> TokenResponse:
    user = await get_user_by_github_id(db, github_id)
    if not user:
        user = await get_user_by_email(db, email.lower())
        if user:
            user.github_id = github_id
            user.github_username = github_username
            user.avatar_url = avatar_url
            user.is_verified = True
        else:
            user = User(
                email=email.lower(),
                full_name=full_name or github_username,
                github_id=github_id,
                github_username=github_username,
                avatar_url=avatar_url,
                is_verified=True,
            )
            db.add(user)
            await db.flush()
    else:
        user.github_username = github_username
        user.avatar_url = avatar_url

    if github_access_token:
        user.github_access_token = github_access_token

    return await _issue_tokens(db, user)
