from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyOtpRequest,
)
from app.services.auth import (
    AuthError,
    forgot_password,
    get_or_create_github_user,
    login_user,
    logout_user,
    refresh_access_token,
    register_user,
    resend_otp,
    reset_password,
    user_to_response,
    verify_email_otp,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _handle_auth_error(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/register", response_model=MessageResponse)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    try:
        _, dev_code = await register_user(
            db, body.email, body.password, body.full_name
        )
    except AuthError as exc:
        raise _handle_auth_error(exc) from exc

    return MessageResponse(
        message="Account created. Please verify your email.",
        requires_verification=True,
        dev_code=dev_code,
    )


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(
    body: VerifyOtpRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    try:
        return await verify_email_otp(db, body.email, body.code)
    except AuthError as exc:
        raise _handle_auth_error(exc) from exc


@router.post("/resend-otp", response_model=MessageResponse)
async def resend_verification_otp(
    body: ResendOtpRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    try:
        dev_code = await resend_otp(db, body.email)
    except AuthError as exc:
        raise _handle_auth_error(exc) from exc

    return MessageResponse(
        message="If an account exists, a new verification code has been sent.",
        dev_code=dev_code,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    try:
        return await login_user(db, body.email, body.password)
    except AuthError as exc:
        raise _handle_auth_error(exc) from exc


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    try:
        return await refresh_access_token(db, body.refresh_token)
    except AuthError as exc:
        raise _handle_auth_error(exc) from exc


@router.post("/logout", response_model=MessageResponse)
async def logout(
    body: LogoutRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await logout_user(db, body.refresh_token)
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return user_to_response(current_user)


@router.post("/forgot-password", response_model=MessageResponse)
async def request_password_reset(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    dev_code = await forgot_password(db, body.email)
    return MessageResponse(
        message="If an account exists, a reset code has been sent.",
        dev_code=dev_code,
    )


@router.post("/reset-password", response_model=MessageResponse)
async def complete_password_reset(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    try:
        await reset_password(db, body.email, body.code, body.new_password)
    except AuthError as exc:
        raise _handle_auth_error(exc) from exc

    return MessageResponse(message="Password reset successfully. You can now sign in.")


@router.get("/github")
async def github_login() -> RedirectResponse:
    settings = get_settings()
    if not settings.github_client_id:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")

    params = urlencode(
        {
            "client_id": settings.github_client_id,
            "redirect_uri": settings.github_redirect_uri,
            "scope": "read:user user:email repo workflow",
        }
    )
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


@router.get("/github/callback")
async def github_callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": settings.github_redirect_uri,
            },
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="GitHub authorization failed")

        user_resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        gh_user = user_resp.json()

        email = gh_user.get("email")
        if not email:
            emails_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            emails = emails_resp.json()
            primary = next(
                (e["email"] for e in emails if e.get("primary")), None
            )
            email = primary or (emails[0]["email"] if emails else None)

        if not email:
            raise HTTPException(
                status_code=400,
                detail="Could not retrieve email from GitHub account",
            )

    tokens = await get_or_create_github_user(
        db,
        github_id=str(gh_user["id"]),
        email=email,
        full_name=gh_user.get("name") or gh_user.get("login", ""),
        github_username=gh_user.get("login", ""),
        avatar_url=gh_user.get("avatar_url"),
        github_access_token=access_token,
    )

    params = urlencode(
        {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_in": str(tokens.expires_in),
            "refresh_expires_in": str(tokens.refresh_expires_in),
        }
    )
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?{params}")
