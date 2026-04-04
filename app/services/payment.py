import hashlib
import httpx
import uuid
import logging
import time
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)


class DuitkuService:
    """Duitku Pop API integration (api-sandbox.duitku.com)."""

    @staticmethod
    def _header_signature(merchant_code: str, timestamp: str, api_key: str) -> str:
        raw = f"{merchant_code}{timestamp}{api_key}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _callback_signature(merchant_code: str, amount: int, merchant_order_id: str, api_key: str) -> str:
        # Callback signature still uses MD5
        raw = f"{merchant_code}{amount}{merchant_order_id}{api_key}"
        return hashlib.md5(raw.encode()).hexdigest()

    async def create_payment(
        self,
        order_number: str,
        amount: int,
        product_name: str,
        customer_name: str,
        customer_email: str,
        return_url: str,
    ) -> dict:
        timestamp = str(int(time.time() * 1000))  # milliseconds
        signature = self._header_signature(
            settings.DUITKU_MERCHANT_CODE,
            timestamp,
            settings.DUITKU_API_KEY,
        )
        headers = {
            "Content-Type": "application/json",
            "x-duitku-merchantcode": settings.DUITKU_MERCHANT_CODE,
            "x-duitku-timestamp": timestamp,
            "x-duitku-signature": signature,
        }
        payload = {
            "merchantCode": settings.DUITKU_MERCHANT_CODE,
            "paymentAmount": amount,
            "merchantOrderId": order_number,
            "productDetails": product_name[:255],
            "customerVaName": customer_name[:20],
            "email": customer_email,
            "callbackUrl": settings.DUITKU_CALLBACK_URL,
            "returnUrl": return_url,
            "expiryPeriod": 1440,
        }
        logger.warning(f"[duitku] sending payload: {payload}")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.DUITKU_BASE_URL}/api/merchant/createInvoice",
                json=payload,
                headers=headers,
            )
            logger.warning(f"[duitku] status={resp.status_code} body={resp.text}")
            resp.raise_for_status()
            return resp.json()

    def verify_callback(self, merchant_code: str, amount: int, order_id: str, signature: str) -> bool:
        expected = self._callback_signature(
            merchant_code, amount, order_id, settings.DUITKU_API_KEY
        )
        return expected == signature


class MayarService:
    """Mayar.id payment gateway integration (fallback)."""

    async def create_payment(
        self,
        order_number: str,
        amount: int,
        product_name: str,
        customer_name: str,
        customer_email: str,
        return_url: str,
    ) -> dict:
        payload = {
            "amount": amount,
            "description": product_name,
            "customer": {"name": customer_name, "email": customer_email},
            "externalId": order_number,
            "redirectUrl": return_url,
            "callbackUrl": settings.MAYAR_CALLBACK_URL,
        }
        async with httpx.AsyncClient(
            timeout=30,
            headers={"Authorization": f"Bearer {settings.MAYAR_API_KEY}"},
        ) as client:
            resp = await client.post(
                f"{settings.MAYAR_BASE_URL}/payment-link/create",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()


duitku = DuitkuService()
mayar = MayarService()


def generate_order_number() -> str:
    now = datetime.utcnow()
    uid = uuid.uuid4().hex[:6].upper()
    return f"TWJ-{now.strftime('%Y%m%d')}-{uid}"
