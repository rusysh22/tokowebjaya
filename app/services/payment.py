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
    Returns: 'va', 'ewallet', 'qris', 'retail', 'cc', or 'other'
    """
    code = (code or "").upper()
    # Credit card
    if code in ("VC",):
        return "cc"
    # Retail / minimarket
    if code in ("FT", "IR", "ALFMART", "INDOMARET"):
        return "retail"
    # E-wallet (app-based, non-QRIS)
    if code in ("OV", "OL", "DA", "SA", "LA", "SL", "JP"):
        return "ewallet"
    # QRIS
    if code in ("SP", "LQ", "GQ", "NQ", "AG"):
        return "qris"
    # Virtual Account
    if code in ("VA", "BT", "B1", "A1", "I1", "M2", "BC", "BR", "BV", "NC", "DN"):
        return "va"
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

    def _payment_method_url(self) -> str:
        """Return correct getPaymentMethod URL based on environment."""
        if "sandbox" in settings.DUITKU_BASE_URL:
            return "https://sandbox.duitku.com/webapi/api/merchant/paymentmethod/getpaymentmethod"
        return "https://passport.duitku.com/webapi/api/merchant/paymentmethod/getpaymentmethod"

    async def get_payment_methods(self, amount: int) -> list[dict]:
        """
        Fetch active payment methods from Duitku API.
        Uses separate endpoint with its own signature formula:
        sha256(merchantCode + amount + datetime + apiKey)
        """
        dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        raw = f"{settings.DUITKU_MERCHANT_CODE}{amount}{dt}{settings.DUITKU_API_KEY}"
        sig = hashlib.sha256(raw.encode()).hexdigest()
        payload = {
            "merchantcode": settings.DUITKU_MERCHANT_CODE,
            "amount": amount,
            "datetime": dt,
            "signature": sig,
        }
        url = self._payment_method_url()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            logger.info(f"[duitku:get_payment_methods] status={resp.status_code}")
            resp.raise_for_status()
            data = resp.json()

        methods = data.get("paymentFee", [])
        for m in methods:
            m["method_type"] = _method_type(m.get("paymentMethod", ""))
        return methods

    def _inquiry_url(self) -> str:
        """Return correct V2 inquiry URL based on environment."""
        if "sandbox" in settings.DUITKU_BASE_URL:
            return "https://sandbox.duitku.com/webapi/api/merchant/v2/inquiry"
        return "https://passport.duitku.com/webapi/api/merchant/v2/inquiry"

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
        Create a Duitku V2 direct transaction for a specific payment method.
        Uses /v2/inquiry endpoint with MD5 signature: md5(merchantCode+orderId+amount+apiKey)
        Returns vaNumber / qrString / paymentCode directly in response.
        """
        # V2 inquiry signature formula: md5(merchantCode + merchantOrderId + amount + apiKey)
        raw = f"{settings.DUITKU_MERCHANT_CODE}{order_number}{amount}{settings.DUITKU_API_KEY}"
        signature = hashlib.md5(raw.encode()).hexdigest()

        payload = {
            "merchantCode":    settings.DUITKU_MERCHANT_CODE,
            "paymentAmount":   amount,
            "merchantOrderId": order_number,
            "productDetails":  product_name[:255],
            "customerVaName":  customer_name[:20],
            "email":           customer_email,
            "paymentMethod":   payment_method,
            "callbackUrl":     settings.DUITKU_CALLBACK_URL,
            "returnUrl":       return_url,
            "expiryPeriod":    1440,
            "signature":       signature,
        }
        url = self._inquiry_url()
        logger.info(f"[duitku:create_payment_v2] method={payment_method} order={order_number} amount={amount} url={url}")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            logger.info(f"[duitku:create_payment_v2] status={resp.status_code} body={resp.text}")
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
