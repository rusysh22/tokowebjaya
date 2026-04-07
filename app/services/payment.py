"""
Payment service — gateway integrations for Duitku (primary) and Mayar (secondary).

Exports:
  duitku   — DuitkuService singleton
  mayar    — MayarService singleton
  generate_order_number()  — Unique order number with timestamp + random suffix
"""
import hashlib
import logging
import time
import uuid
from datetime import datetime

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _method_type(code: str) -> str:
    """
    Classify a Duitku payment method code into display type.
    Returns: 'va', 'qris', 'retail', or 'other'
    """
    code = (code or "").upper()
    if code in ("VC", "BT", "M2", "A1", "B1", "I1", "VA"):
        return "va"
    if code in ("QRIS", "SP", "LA", "DA", "OV", "SB", "LT", "FT", "AG"):
        return "qris"
    if code in ("ALFMART", "INDOMARET", "AG", "FT", "LT"):
        return "retail"
    # Fallback heuristic
    if code.startswith("Q"):
        return "qris"
    if code.startswith("A") or code.startswith("I"):
        return "retail"
    return "va"


class DuitkuService:
    """Duitku V2 API integration."""

    @staticmethod
    def _header_signature(merchant_code: str, timestamp: str, api_key: str) -> str:
        raw = f"{merchant_code}{timestamp}{api_key}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _callback_signature(merchant_code: str, amount: int, merchant_order_id: str, api_key: str) -> str:
        raw = f"{merchant_code}{amount}{merchant_order_id}{api_key}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _build_headers(self) -> tuple[dict, str]:
        """Build signed request headers. Returns (headers, timestamp)."""
        timestamp = str(int(time.time() * 1000))
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
        return headers, timestamp

    async def get_payment_methods(self, amount: int) -> list[dict]:
        """
        Fetch active payment methods from Duitku V2 API.
        Returns list of method dicts with extra 'method_type' field.
        """
        headers, _ = self._build_headers()
        payload = {
            "merchantcode": settings.DUITKU_MERCHANT_CODE,
            "amount": amount,
            "datetime": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{settings.DUITKU_BASE_URL}/api/merchant/paymentmethod/getPaymentMethod",
                json=payload,
                headers=headers,
            )
            logger.info(f"[duitku:get_payment_methods] status={resp.status_code}")
            resp.raise_for_status()
            data = resp.json()

        methods = data.get("paymentFee", [])
        for m in methods:
            m["method_type"] = _method_type(m.get("paymentMethod", ""))
        return methods

    async def create_payment_v2(
        self,
        order_number: str,
        amount: int,
        payment_method: str,
        product_name: str,
        customer_name: str,
        customer_email: str,
        return_url: str,
    ) -> dict:
        """
        Create a Duitku V2 transaction for a specific payment method.
        Returns the full API response dict.
        """
        headers, _ = self._build_headers()
        payload = {
            "merchantCode":   settings.DUITKU_MERCHANT_CODE,
            "paymentAmount":  amount,
            "merchantOrderId": order_number,
            "productDetails": product_name[:255],
            "customerVaName": customer_name[:20],
            "email":          customer_email,
            "paymentMethod":  payment_method,
            "callbackUrl":    settings.DUITKU_CALLBACK_URL,
            "returnUrl":      return_url,
            "expiryPeriod":   1440,
        }
        logger.info(f"[duitku:create_payment_v2] method={payment_method} order={order_number} amount={amount}")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.DUITKU_BASE_URL}/api/merchant/createInvoice",
                json=payload,
                headers=headers,
            )
            logger.warning(f"[duitku:create_payment_v2] status={resp.status_code} body={resp.text}")
            resp.raise_for_status()
            return resp.json()

    # Keep legacy create_payment for backward compat (used by /process route)
    async def create_payment(
        self,
        order_number: str,
        amount: int,
        product_name: str,
        customer_name: str,
        customer_email: str,
        return_url: str,
    ) -> dict:
        headers, _ = self._build_headers()
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
