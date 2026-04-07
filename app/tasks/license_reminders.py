"""
Celery tasks for license/subscription reminders and expiry handling.

Tasks:
  send_license_reminders  — daily: send 7d and 3d expiry warnings
  expire_licenses         — daily: mark expired licenses, fire webhooks
"""
import logging
from datetime import datetime, timedelta

from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.license_reminders.send_license_reminders", bind=True, max_retries=2)
def send_license_reminders(self):
    """
    Daily task — find licenses expiring in ~7 days or ~3 days and send reminder emails.
    Marks reminded_7d / reminded_3d to avoid duplicate sends.
    """
    from app.core.database import SessionLocal
    from app.models.license import ProductLicense
    from app.services.email import send_license_reminder

    db = SessionLocal()
    try:
        now = datetime.utcnow()

        # 7-day window: expires between 6.5 and 7.5 days from now
        window_7_start = now + timedelta(days=6, hours=12)
        window_7_end   = now + timedelta(days=7, hours=12)

        # 3-day window: expires between 2.5 and 3.5 days from now
        window_3_start = now + timedelta(days=2, hours=12)
        window_3_end   = now + timedelta(days=3, hours=12)

        # 7-day reminders
        licenses_7d = db.query(ProductLicense).filter(
            ProductLicense.expires_at.between(window_7_start, window_7_end),
            ProductLicense.is_active == True,
            ProductLicense.reminded_7d == False,
        ).all()

        sent_7d = 0
        for lic in licenses_7d:
            try:
                locale = "id"  # default; could be stored in metadata
                send_license_reminder(lic, days_left=7, locale=locale)
                lic.reminded_7d = True
                sent_7d += 1
            except Exception as e:
                logger.warning(f"[reminder] 7d failed license={lic.id} error={e}")
        db.commit()

        # 3-day reminders
        licenses_3d = db.query(ProductLicense).filter(
            ProductLicense.expires_at.between(window_3_start, window_3_end),
            ProductLicense.is_active == True,
            ProductLicense.reminded_3d == False,
        ).all()

        sent_3d = 0
        for lic in licenses_3d:
            try:
                locale = "id"
                send_license_reminder(lic, days_left=3, locale=locale)
                lic.reminded_3d = True
                sent_3d += 1
            except Exception as e:
                logger.warning(f"[reminder] 3d failed license={lic.id} error={e}")
        db.commit()

        logger.info(f"[license_reminders] sent 7d={sent_7d} 3d={sent_3d}")
        return {"sent_7d": sent_7d, "sent_3d": sent_3d}

    except Exception as exc:
        logger.error(f"[license_reminders] error={exc}")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


@celery.task(name="app.tasks.license_reminders.expire_licenses", bind=True, max_retries=2)
def expire_licenses(self):
    """
    Daily task — process licenses that have passed grace_until:
    - Deactivate the license
    - Fire webhook to external app
    - Send final expiry email if not already sent
    """
    import asyncio
    from app.core.database import SessionLocal
    from app.models.license import ProductLicense
    from app.services.email import send_license_reminder
    from app.services.license import send_webhook

    db = SessionLocal()
    try:
        now = datetime.utcnow()

        # Licenses past grace period, still marked active
        expired_licenses = db.query(ProductLicense).filter(
            ProductLicense.grace_until < now,
            ProductLicense.is_active == True,
        ).all()

        deactivated = 0
        for lic in expired_licenses:
            try:
                lic.is_active = False
                if not lic.reminded_expired:
                    try:
                        send_license_reminder(lic, days_left=0, locale="id")
                    except Exception:
                        pass
                    lic.reminded_expired = True

                # Fire webhook
                if lic.product and lic.product.webhook_url:
                    try:
                        asyncio.run(send_webhook(
                            lic.product.webhook_url,
                            "license.expired",
                            {
                                "license_key":  lic.license_key,
                                "license_type": lic.license_type,
                                "expired_at":   now.isoformat(),
                                "order_id":     str(lic.order_id),
                                "user_email":   lic.user.email if lic.user else None,
                            }
                        ))
                    except Exception as e:
                        logger.warning(f"[expire] webhook failed license={lic.id} error={e}")

                deactivated += 1
            except Exception as e:
                logger.warning(f"[expire] failed license={lic.id} error={e}")

        db.commit()
        logger.info(f"[expire_licenses] deactivated={deactivated}")
        return {"deactivated": deactivated}

    except Exception as exc:
        logger.error(f"[expire_licenses] error={exc}")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
