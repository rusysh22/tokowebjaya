"""
Currency & VAT utilities.

Supported currencies: IDR, USD
VAT: 11% PPN for IDR, configurable per currency via settings.
"""

from app.core.config import settings


def get_vat_rate(currency: str) -> float:
    """Return VAT rate for a given currency."""
    if currency == "IDR":
        return settings.VAT_RATE_IDR
    elif currency == "USD":
        return settings.VAT_RATE_USD
    return 0.0


def convert_price(amount_idr: float, currency: str) -> float:
    """Convert IDR amount to target currency."""
    if currency == "IDR":
        return amount_idr
    elif currency == "USD":
        return round(amount_idr / settings.USD_TO_IDR_RATE, 2)
    return amount_idr


def convert_to_idr(amount: float, currency: str) -> float:
    """Convert any currency amount to IDR for payment processing."""
    if currency == "IDR":
        return amount
    elif currency == "USD":
        return round(amount * settings.USD_TO_IDR_RATE, 0)
    return amount


def add_vat(amount: float, currency: str) -> dict:
    """
    Calculate price with VAT.
    Returns: {subtotal, vat_amount, total, vat_rate, currency}
    """
    vat_rate = get_vat_rate(currency)
    vat_amount = round(amount * vat_rate, 2 if currency == "USD" else 0)
    total = round(amount + vat_amount, 2 if currency == "USD" else 0)
    return {
        "subtotal": amount,
        "vat_amount": vat_amount,
        "total": total,
        "vat_rate": vat_rate,
        "currency": currency,
    }


def format_price(amount: float, currency: str) -> str:
    """Format price for display."""
    if currency == "IDR":
        return f"Rp {amount:,.0f}"
    elif currency == "USD":
        return f"${amount:,.2f}"
    return f"{amount:,.2f} {currency}"


def get_display_prices(price_idr: float, currency: str, include_vat: bool = False) -> dict:
    """
    Get all price display data for a given IDR price and target currency.
    """
    converted = convert_price(price_idr, currency)
    if include_vat:
        breakdown = add_vat(converted, currency)
    else:
        breakdown = {"subtotal": converted, "vat_amount": 0, "total": converted, "vat_rate": 0, "currency": currency}

    return {
        "amount": converted,
        "amount_idr": price_idr,
        "currency": currency,
        "formatted": format_price(converted, currency),
        "formatted_total": format_price(breakdown["total"], currency),
        "vat_rate": breakdown["vat_rate"],
        "vat_amount": breakdown["vat_amount"],
        "subtotal": breakdown["subtotal"],
        "total": breakdown["total"],
    }
