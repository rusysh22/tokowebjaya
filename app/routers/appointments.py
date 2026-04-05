"""
Appointment router — booking demo/call/meeting for any product.
Routes:
  GET  /{locale}/appointments                     — user's appointment list
  GET  /{locale}/appointments/{id}                — appointment detail
  POST /{locale}/appointments/{product_id}/book   — create booking (AJAX JSON)
  POST /{locale}/appointments/{id}/cancel         — cancel booking
  GET  /api/appointments/slots                    — available time slots (AJAX)
"""
import logging
from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_login
from app.core.database import get_db
from app.models.appointment import (
    Appointment, AppointmentStatus, AppointmentType, ProductAvailability
)
from app.models.product import Product, ProductStatus

logger = logging.getLogger(__name__)
router = APIRouter(tags=["appointments"])

WIB = ZoneInfo("Asia/Jakarta")
DAYS_AHEAD = 30   # how many days ahead user can book


# ── Helpers ──────────────────────────────────────────────────────────────────

def _booked_times(db: Session, product_id, appt_date: date) -> set:
    """Return set of already-booked WIB times for a product on a given date."""
    rows = db.query(Appointment.appt_time).filter(
        Appointment.product_id == product_id,
        Appointment.appt_date  == appt_date,
        Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.confirmed]),
    ).all()
    return {r.appt_time for r in rows}


def _slots_for_date(db: Session, product_id, target_date: date) -> list[str]:
    """
    Return list of available time slots (HH:MM, WIB) for product on target_date.
    """
    dow = target_date.weekday()   # 0=Mon … 6=Sun
    avail = db.query(ProductAvailability).filter(
        ProductAvailability.product_id == product_id,
        ProductAvailability.day_of_week == dow,
        ProductAvailability.is_active.is_(True),
    ).all()

    if not avail:
        return []

    booked = _booked_times(db, product_id, target_date)
    now_wib = datetime.now(WIB)

    slots = []
    for a in avail:
        duration = timedelta(minutes=a.slot_duration_minutes or 60)
        current  = datetime.combine(target_date, a.start_time)
        end      = datetime.combine(target_date, a.end_time)
        while current + duration <= end:
            t = current.time()
            # Skip if booked or if in the past (same day)
            slot_dt = datetime.combine(target_date, t, tzinfo=WIB)
            if t not in booked and slot_dt > now_wib + timedelta(hours=1):
                slots.append(t.strftime("%H:%M"))
            current += duration

    return sorted(set(slots))


# ── AJAX: available slots ─────────────────────────────────────────────────────

@router.get("/api/appointments/slots")
async def get_slots(
    product_id: str,
    date_str: str,     # YYYY-MM-DD
    db: Session = Depends(get_db),
):
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        return JSONResponse({"slots": [], "error": "Invalid date"}, status_code=400)

    if target_date < date.today():
        return JSONResponse({"slots": []})
    if target_date > date.today() + timedelta(days=DAYS_AHEAD):
        return JSONResponse({"slots": [], "error": "Too far ahead"})

    product = db.query(Product).filter(
        Product.id == product_id,
        Product.status == ProductStatus.active,
    ).first()
    if not product:
        return JSONResponse({"slots": [], "error": "Product not found"}, status_code=404)

    slots = _slots_for_date(db, product_id, target_date)

    # Also return which days in the next 30d have availability (for disabling calendar dates)
    available_days = []
    today = date.today()
    avail_rows = db.query(ProductAvailability.day_of_week).filter(
        ProductAvailability.product_id == product_id,
        ProductAvailability.is_active.is_(True),
    ).distinct().all()
    active_dows = {r.day_of_week for r in avail_rows}
    for i in range(DAYS_AHEAD + 1):
        d = today + timedelta(days=i)
        if d.weekday() in active_dows:
            available_days.append(d.isoformat())

    return JSONResponse({"slots": slots, "available_days": available_days})


# ── Book appointment ──────────────────────────────────────────────────────────

@router.post("/{locale}/appointments/{product_id}/book")
async def book_appointment(
    request: Request, locale: str, product_id: str,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    if not current_user:
        return JSONResponse({"detail": "Login required"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON"}, status_code=400)

    appt_date_str = body.get("date", "")
    appt_time_str = body.get("time", "")
    appt_type_str = body.get("type", "demo")
    notes         = str(body.get("notes", "")).strip()[:500]
    user_tz       = str(body.get("timezone", "Asia/Jakarta"))[:50]

    # Validate
    try:
        appt_date = date.fromisoformat(appt_date_str)
        appt_time = time.fromisoformat(appt_time_str)
    except ValueError:
        return JSONResponse({"detail": "Invalid date or time"}, status_code=400)

    if appt_date < date.today():
        return JSONResponse({"detail": "Cannot book in the past"}, status_code=400)

    if appt_type_str not in AppointmentType.__members__:
        appt_type_str = "demo"

    product = db.query(Product).filter(
        Product.id == product_id,
        Product.status == ProductStatus.active,
    ).first()
    if not product:
        return JSONResponse({"detail": "Product not found"}, status_code=404)

    # Verify slot is still available
    available_slots = _slots_for_date(db, product_id, appt_date)
    if appt_time.strftime("%H:%M") not in available_slots:
        return JSONResponse({"detail": "Slot tidak tersedia atau sudah dibooking"}, status_code=409)

    appt = Appointment(
        id         = __import__("uuid").uuid4(),
        product_id = product.id,
        user_id    = current_user.id,
        appt_type  = appt_type_str,
        appt_date  = appt_date,
        appt_time  = appt_time,
        timezone   = user_tz,
        notes      = notes or None,
        status     = AppointmentStatus.pending,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    logger.info("Appointment booked: %s by user %s", appt.id, current_user.id)

    # Fire email notifications (background — don't block response)
    try:
        from app.services.email import send_appointment_booked
        send_appointment_booked(appt, product, current_user, locale)
    except Exception as e:
        logger.warning("Appointment email failed: %s", e)

    return JSONResponse({
        "ok":     True,
        "id":     str(appt.id),
        "status": appt.status.value,
        "message": "Booking berhasil! Menunggu konfirmasi dari penjual." if locale == "id"
                   else "Booking successful! Waiting for seller confirmation.",
    })


# ── Cancel appointment ────────────────────────────────────────────────────────

@router.post("/{locale}/appointments/{appt_id}/cancel")
async def cancel_appointment(
    request: Request, locale: str, appt_id: str,
    db: Session = Depends(get_db),
):
    current_user = require_login(request, db)

    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if str(appt.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your appointment")
    if appt.status not in (AppointmentStatus.pending, AppointmentStatus.confirmed):
        raise HTTPException(status_code=400, detail="Cannot cancel this appointment")

    appt.status = AppointmentStatus.cancelled
    db.commit()

    return JSONResponse({"ok": True})


# ── User appointment list page ────────────────────────────────────────────────

@router.get("/{locale}/appointments")
async def appointments_list(
    request: Request, locale: str,
    db: Session = Depends(get_db),
):
    current_user = require_login(request, db)
    from app.main import templates

    appts = db.query(Appointment).filter(
        Appointment.user_id == current_user.id,
    ).order_by(Appointment.appt_date.desc(), Appointment.appt_time.desc()).all()

    return templates.TemplateResponse(
        request, "appointments/list.html", {
            "locale":       locale,
            "current_user": current_user,
            "active_page":  "appointments",
            "appointments": appts,
        }
    )
