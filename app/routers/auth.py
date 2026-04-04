from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
import uuid

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_session_token, hash_password, verify_password
from app.models.user import User, UserRole, UserStatus, AuthProvider
from app.services.otp import generate_otp, verify_otp
from app.services.email import send_otp_email

router = APIRouter(prefix="/auth", tags=["auth"])

# OAuth setup
config = Config(environ={
    "GOOGLE_CLIENT_ID": settings.GOOGLE_CLIENT_ID,
    "GOOGLE_CLIENT_SECRET": settings.GOOGLE_CLIENT_SECRET,
})
oauth = OAuth(config)
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
)


@router.get("/google/login")
async def google_login(request: Request, next: str = "/"):
    request.session["oauth_next"] = next
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return RedirectResponse(url="/id/login?error=oauth_failed")

    userinfo = token.get("userinfo") or await oauth.google.userinfo(token=token)

    google_id = userinfo.get("sub")
    email = userinfo.get("email")
    name = userinfo.get("name", email)
    avatar = userinfo.get("picture")

    if not google_id or not email:
        return RedirectResponse(url="/id/login?error=missing_info")

    # Upsert user
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_id = google_id
            user.avatar_url = avatar
        else:
            user = User(
                id=uuid.uuid4(),
                name=name,
                email=email,
                google_id=google_id,
                avatar_url=avatar,
                role=UserRole.customer,
                status=UserStatus.active,
            )
            db.add(user)
    else:
        user.name = name
        user.avatar_url = avatar

    db.commit()
    db.refresh(user)

    if user.status == UserStatus.banned:
        return RedirectResponse(url="/id/login?error=banned")

    # Create session cookie
    token_data = {"user_id": str(user.id), "role": user.role.value}
    session_token = create_session_token(token_data)

    next_url = request.session.pop("oauth_next", None) or f"/id/dashboard"
    response = RedirectResponse(url=next_url)
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=86400 * 7,  # 7 days
    )
    return response


@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/id/")
    response.delete_cookie("session")
    request.session.clear()
    return response


# ─── Email+Password auth ──────────────────────────────────────────────────────

def _make_session_response(user: User, next_url: str) -> RedirectResponse:
    token_data = {"user_id": str(user.id), "role": user.role.value}
    session_token = create_session_token(token_data)
    response = RedirectResponse(url=next_url, status_code=302)
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=86400 * 7,
    )
    return response


@router.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    locale: str = Form(default="id"),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()

    if len(password) < 8:
        return RedirectResponse(
            url=f"/{locale}/register?error=password_short&email={email}&name={name}",
            status_code=302,
        )

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if existing.auth_provider == AuthProvider.google:
            return RedirectResponse(
                url=f"/{locale}/login?error=use_google&email={email}",
                status_code=302,
            )
        return RedirectResponse(
            url=f"/{locale}/register?error=email_taken&email={email}&name={name}",
            status_code=302,
        )

    # Create unverified user
    user = User(
        id=uuid.uuid4(),
        name=name,
        email=email,
        password_hash=hash_password(password),
        email_verified=False,
        auth_provider=AuthProvider.email,
        role=UserRole.customer,
        status=UserStatus.active,
    )
    db.add(user)
    db.commit()

    # Send OTP
    otp = generate_otp("verify_email", email)
    send_otp_email(email, name, otp, purpose="verify", locale=locale)

    return RedirectResponse(
        url=f"/{locale}/verify-email?email={email}",
        status_code=302,
    )


@router.post("/verify-email")
async def verify_email(
    request: Request,
    email: str = Form(...),
    otp: str = Form(...),
    locale: str = Form(default="id"),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    ok, reason = verify_otp("verify_email", email, otp)

    if not ok:
        return RedirectResponse(
            url=f"/{locale}/verify-email?email={email}&error={reason}",
            status_code=302,
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return RedirectResponse(url=f"/{locale}/login?error=not_found", status_code=302)

    user.email_verified = True
    db.commit()

    return _make_session_response(user, f"/{locale}/dashboard")


@router.post("/resend-otp")
async def resend_otp(
    request: Request,
    email: str = Form(...),
    purpose: str = Form(default="verify"),
    locale: str = Form(default="id"),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user:
        otp = generate_otp(
            "verify_email" if purpose == "verify" else "reset_password",
            email,
        )
        send_otp_email(email, user.name, otp, purpose=purpose, locale=locale)
    # Always redirect without exposing whether email exists
    target = "verify-email" if purpose == "verify" else "forgot-password"
    return RedirectResponse(
        url=f"/{locale}/{target}?email={email}&resent=1",
        status_code=302,
    )


@router.post("/login-email")
async def login_email(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    locale: str = Form(default="id"),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        return RedirectResponse(
            url=f"/{locale}/login?error=invalid_credentials&tab=email",
            status_code=302,
        )

    if user.status == UserStatus.banned:
        return RedirectResponse(url=f"/{locale}/login?error=banned", status_code=302)

    if not user.email_verified:
        # Resend OTP and redirect to verify
        otp = generate_otp("verify_email", email)
        send_otp_email(email, user.name, otp, purpose="verify", locale=locale)
        return RedirectResponse(
            url=f"/{locale}/verify-email?email={email}&error=not_verified",
            status_code=302,
        )

    return _make_session_response(user, f"/{locale}/dashboard")


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: str = Form(...),
    locale: str = Form(default="id"),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if user and user.auth_provider == AuthProvider.email:
        otp = generate_otp("reset_password", email)
        send_otp_email(email, user.name, otp, purpose="reset", locale=locale)

    # Don't reveal if email exists
    return RedirectResponse(
        url=f"/{locale}/reset-password?email={email}",
        status_code=302,
    )


@router.post("/reset-password")
async def reset_password(
    request: Request,
    email: str = Form(...),
    otp: str = Form(...),
    password: str = Form(...),
    locale: str = Form(default="id"),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()

    if len(password) < 8:
        return RedirectResponse(
            url=f"/{locale}/reset-password?email={email}&error=password_short",
            status_code=302,
        )

    ok, reason = verify_otp("reset_password", email, otp)
    if not ok:
        return RedirectResponse(
            url=f"/{locale}/reset-password?email={email}&error={reason}",
            status_code=302,
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return RedirectResponse(url=f"/{locale}/login?error=not_found", status_code=302)

    user.password_hash = hash_password(password)
    user.email_verified = True
    db.commit()

    return _make_session_response(user, f"/{locale}/dashboard")
