"""
Email service via SMTP (Sumopod / any SMTP provider)
"""
import logging
import smtplib
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send(to: str, subject: str, html: str, attachments: list = None) -> bool:
    """Core SMTP send. Returns True on success, False on failure."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("[email] SMTP credentials not set, skipping.")
        return False

    try:
        msg = MIMEMultipart("mixed")
        msg["From"]    = settings.EMAIL_FROM
        msg["To"]      = to
        msg["Subject"] = subject

        msg.attach(MIMEText(html, "html", "utf-8"))

        if attachments:
            for att in attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(att["content"])         # already bytes
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{att["filename"]}"',
                )
                msg.attach(part)

        # Port 465 = SSL, port 587 = STARTTLS
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAIL_FROM, to, msg.as_string())
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAIL_FROM, to, msg.as_string())

        logger.info(f"[email] Sent '{subject}' → {to}")
        return True

    except Exception as e:
        logger.error(f"[email] Failed to send '{subject}' → {to}: {e}")
        return False


# ─── HTML base template ───────────────────────────────────────────────────────

def _base_html(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: Arial, Helvetica, sans-serif; background: #f5f5f5; color: #111; }}
    .wrapper {{ max-width: 560px; margin: 32px auto; background: #fff; border: 1px solid #e0e0e0; }}
    .header {{ background: #0a0a0a; padding: 24px 32px; }}
    .logo-wrap {{ display: flex; align-items: center; gap: 12px; }}
    .logo-box {{ width: 36px; height: 36px; background: #CAFF00; display: inline-flex; align-items: center; justify-content: center; font-weight: 900; font-size: 13px; color: #000; }}
    .logo-text {{ color: #fff; font-weight: 700; font-size: 16px; }}
    .logo-text span {{ color: #CAFF00; }}
    .content {{ padding: 32px; }}
    .badge {{ display: inline-block; background: #CAFF00; color: #000; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; padding: 4px 12px; margin-bottom: 20px; }}
    .badge-red {{ background: #fee2e2; color: #dc2626; }}
    h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 12px; color: #0a0a0a; }}
    p {{ font-size: 14px; line-height: 1.6; color: #444; margin-bottom: 16px; }}
    .info-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
    .info-table td {{ padding: 10px 12px; font-size: 13px; border-bottom: 1px solid #f0f0f0; }}
    .info-table td:first-child {{ color: #888; width: 45%; }}
    .info-table td:last-child {{ font-weight: 600; color: #111; }}
    .total-row td {{ background: #f9f9f9; font-size: 15px; font-weight: 700; border-bottom: none; border-top: 2px solid #0a0a0a; }}
    .btn {{ display: inline-block; background: #0a0a0a; color: #CAFF00 !important; text-decoration: none; font-weight: 700; font-size: 13px; padding: 12px 28px; margin: 8px 0 20px; }}
    .footer {{ background: #f9f9f9; padding: 20px 32px; text-align: center; font-size: 11px; color: #aaa; border-top: 1px solid #e0e0e0; line-height: 1.6; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <div class="logo-wrap">
        <div class="logo-box">TW</div>
        <div class="logo-text">Toko <span>Web</span> Jaya</div>
      </div>
    </div>
    <div class="content">
      {body_html}
    </div>
    <div class="footer">
      Toko Web Jaya &mdash; Tidak Sedia Alat Bangunan. Tapi siap bantu bisnis digital Anda.<br/>
      tokowebjaya.com &bull; Jika ada pertanyaan, balas email ini.
    </div>
  </div>
</body>
</html>"""


# ─── Email functions ──────────────────────────────────────────────────────────

def send_order_confirmation(order, locale: str = "id") -> bool:
    user = order.user
    if not user:
        return False

    product_name = ""
    if order.product:
        product_name = order.product.name_id if locale == "id" else order.product.name_en

    receipt_url = f"{settings.BASE_URL}/{locale}/dashboard/orders/{order.id}/receipt"

    if locale == "id":
        subject     = f"Pembayaran Berhasil — {order.order_number}"
        badge       = "Pembayaran Berhasil"
        heading     = f"Terima kasih, {user.name.split()[0]}!"
        intro       = "Pembayaran Anda telah berhasil dikonfirmasi. Berikut detail pesanan Anda:"
        btn_text    = "Lihat Receipt"
        lbl_order   = "No. Pesanan"
        lbl_product = "Produk"
        lbl_type    = "Tipe"
        lbl_amount  = "Total Pembayaran"
        lbl_status  = "Status"
        status_val  = "&#10003; Lunas"
        outro       = "Invoice akan segera dikirimkan dalam email terpisah."
    else:
        subject     = f"Payment Confirmed — {order.order_number}"
        badge       = "Payment Confirmed"
        heading     = f"Thank you, {user.name.split()[0]}!"
        intro       = "Your payment has been confirmed. Here are your order details:"
        btn_text    = "View Receipt"
        lbl_order   = "Order No."
        lbl_product = "Product"
        lbl_type    = "Type"
        lbl_amount  = "Total Amount"
        lbl_status  = "Status"
        status_val  = "&#10003; Paid"
        outro       = "Your invoice will be sent in a separate email shortly."

    body = f"""
    <div class="badge">{badge}</div>
    <h1>{heading}</h1>
    <p>{intro}</p>
    <table class="info-table">
      <tr><td>{lbl_order}</td><td>{order.order_number}</td></tr>
      <tr><td>{lbl_product}</td><td>{product_name}</td></tr>
      <tr><td>{lbl_type}</td><td>{order.type.value.replace('_',' ').title()}</td></tr>
      <tr><td>{lbl_status}</td><td style="color:#16a34a">{status_val}</td></tr>
      <tr class="total-row"><td>{lbl_amount}</td><td>Rp {float(order.amount):,.0f}</td></tr>
    </table>
    <a href="{receipt_url}" class="btn">{btn_text} &rarr;</a>
    <p style="color:#888;font-size:13px">{outro}</p>
    """
    return _send(user.email, subject, _base_html(subject, body))


def send_invoice_email(invoice, order, locale: str = "id") -> bool:
    user = order.user
    if not user:
        return False

    product_name = ""
    if order.product:
        product_name = order.product.name_id if locale == "id" else order.product.name_en

    download_url = f"{settings.BASE_URL}/{locale}/dashboard/invoices/{invoice.id}/download"

    if locale == "id":
        subject     = f"Invoice {invoice.invoice_number} — Toko Web Jaya"
        badge       = "Invoice"
        heading     = f"Invoice #{invoice.invoice_number}"
        intro       = f"Invoice untuk pesanan <strong>{order.order_number}</strong> sudah tersedia."
        btn_text    = "Unduh Invoice PDF"
        lbl_inv     = "No. Invoice"
        lbl_order   = "No. Pesanan"
        lbl_product = "Produk"
        lbl_date    = "Tanggal"
        lbl_amount  = "Total"
        lbl_status  = "Status"
        status_val  = "&#10003; Lunas"
    else:
        subject     = f"Invoice {invoice.invoice_number} — Toko Web Jaya"
        badge       = "Invoice"
        heading     = f"Invoice #{invoice.invoice_number}"
        intro       = f"Invoice for order <strong>{order.order_number}</strong> is now available."
        btn_text    = "Download Invoice PDF"
        lbl_inv     = "Invoice No."
        lbl_order   = "Order No."
        lbl_product = "Product"
        lbl_date    = "Date"
        lbl_amount  = "Total"
        lbl_status  = "Status"
        status_val  = "&#10003; Paid"

    body = f"""
    <div class="badge">{badge}</div>
    <h1>{heading}</h1>
    <p>{intro}</p>
    <table class="info-table">
      <tr><td>{lbl_inv}</td><td>{invoice.invoice_number}</td></tr>
      <tr><td>{lbl_order}</td><td>{order.order_number}</td></tr>
      <tr><td>{lbl_product}</td><td>{product_name}</td></tr>
      <tr><td>{lbl_date}</td><td>{invoice.created_at.strftime('%d %B %Y')}</td></tr>
      <tr><td>{lbl_status}</td><td style="color:#16a34a">{status_val}</td></tr>
      <tr class="total-row"><td>{lbl_amount}</td><td>Rp {float(invoice.amount):,.0f}</td></tr>
    </table>
    <a href="{download_url}" class="btn">{btn_text} &rarr;</a>
    """

    # Attach PDF if available
    attachments = []
    if invoice.pdf_path:
        pdf_full = Path(settings.UPLOAD_DIR) / invoice.pdf_path
        if pdf_full.exists():
            with open(pdf_full, "rb") as f:
                attachments.append({
                    "filename": f"{invoice.invoice_number}.pdf",
                    "content":  f.read(),   # raw bytes
                })

    return _send(user.email, subject, _base_html(subject, body), attachments or None)


def send_subscription_expiring(subscription, product, user, days: int, locale: str = "id") -> bool:
    product_name = product.name_id if locale == "id" else product.name_en
    subs_url     = f"{settings.BASE_URL}/{locale}/dashboard/subscriptions"

    if locale == "id":
        subject  = f"Langganan Anda akan berakhir dalam {days} hari"
        badge    = "Pengingat Langganan"
        heading  = f"Hei {user.name.split()[0]}, langganan Anda hampir habis!"
        intro    = f"Langganan <strong>{product_name}</strong> Anda akan berakhir dalam <strong>{days} hari</strong>."
        note     = "Pastikan pembayaran berikutnya berjalan lancar agar akses tidak terputus."
        btn_text = "Kelola Langganan"
        lbl_prod  = "Produk"
        lbl_cycle = "Siklus"
        lbl_next  = "Tagihan berikutnya"
    else:
        subject  = f"Your subscription expires in {days} days"
        badge    = "Subscription Reminder"
        heading  = f"Hey {user.name.split()[0]}, your subscription is expiring soon!"
        intro    = f"Your <strong>{product_name}</strong> subscription expires in <strong>{days} days</strong>."
        note     = "Please ensure your next payment goes through to avoid service interruption."
        btn_text = "Manage Subscription"
        lbl_prod  = "Product"
        lbl_cycle = "Cycle"
        lbl_next  = "Next billing date"

    body = f"""
    <div class="badge">{badge}</div>
    <h1>{heading}</h1>
    <p>{intro}</p>
    <p>{note}</p>
    <table class="info-table">
      <tr><td>{lbl_prod}</td><td>{product_name}</td></tr>
      <tr><td>{lbl_cycle}</td><td>{subscription.billing_cycle.value.title()}</td></tr>
      <tr><td>{lbl_next}</td><td>{subscription.next_billing_date.strftime('%d %B %Y')}</td></tr>
    </table>
    <a href="{subs_url}" class="btn">{btn_text} &rarr;</a>
    """
    return _send(user.email, subject, _base_html(subject, body))


def send_otp_email(to_email: str, name: str, otp: str, purpose: str = "verify", locale: str = "id") -> bool:
    """
    Send OTP email.
    purpose: 'verify' (email verification on register) | 'reset' (password reset)
    """
    if purpose == "verify":
        if locale == "id":
            subject  = "Kode Verifikasi Email — Toko Web Jaya"
            badge    = "Verifikasi Email"
            heading  = f"Halo, {name.split()[0]}!"
            intro    = "Gunakan kode OTP berikut untuk memverifikasi alamat email Anda:"
            note     = "Kode berlaku selama <strong>10 menit</strong>. Jangan bagikan kode ini kepada siapapun."
            ignore   = "Jika Anda tidak mendaftar di Toko Web Jaya, abaikan email ini."
        else:
            subject  = "Email Verification Code — Toko Web Jaya"
            badge    = "Email Verification"
            heading  = f"Hello, {name.split()[0]}!"
            intro    = "Use the OTP code below to verify your email address:"
            note     = "Code is valid for <strong>10 minutes</strong>. Never share this code with anyone."
            ignore   = "If you didn't register at Toko Web Jaya, please ignore this email."
    else:  # reset
        if locale == "id":
            subject  = "Kode Reset Password — Toko Web Jaya"
            badge    = "Reset Password"
            heading  = f"Halo, {name.split()[0]}!"
            intro    = "Gunakan kode OTP berikut untuk mereset password Anda:"
            note     = "Kode berlaku selama <strong>10 menit</strong>. Jangan bagikan kode ini kepada siapapun."
            ignore   = "Jika Anda tidak meminta reset password, abaikan email ini dan password Anda tidak akan berubah."
        else:
            subject  = "Password Reset Code — Toko Web Jaya"
            badge    = "Password Reset"
            heading  = f"Hello, {name.split()[0]}!"
            intro    = "Use the OTP code below to reset your password:"
            note     = "Code is valid for <strong>10 minutes</strong>. Never share this code with anyone."
            ignore   = "If you didn't request a password reset, ignore this email — your password won't change."

    body = f"""
    <div class="badge">{badge}</div>
    <h1>{heading}</h1>
    <p>{intro}</p>
    <div style="text-align:center;margin:28px 0">
      <div style="display:inline-block;background:#0a0a0a;color:#CAFF00;font-size:40px;font-weight:900;letter-spacing:14px;padding:18px 32px;border-radius:4px">{otp}</div>
    </div>
    <p style="font-size:13px;color:#888">{note}</p>
    <p style="font-size:12px;color:#bbb;margin-top:24px">{ignore}</p>
    """
    return _send(to_email, subject, _base_html(subject, body))


def send_subscription_cancelled(subscription, product, user, locale: str = "id") -> bool:
    product_name = product.name_id if locale == "id" else product.name_en
    catalog_url  = f"{settings.BASE_URL}/{locale}/catalog"

    if locale == "id":
        subject  = f"Langganan {product_name} telah dibatalkan"
        badge    = "Langganan Dibatalkan"
        heading  = "Langganan Anda telah dibatalkan"
        intro    = f"Langganan <strong>{product_name}</strong> Anda telah berhasil dibatalkan."
        note     = "Anda masih bisa berlangganan kembali kapan saja melalui katalog kami."
        btn_text = "Lihat Katalog"
    else:
        subject  = f"{product_name} subscription cancelled"
        badge    = "Subscription Cancelled"
        heading  = "Your subscription has been cancelled"
        intro    = f"Your <strong>{product_name}</strong> subscription has been successfully cancelled."
        note     = "You can re-subscribe at any time through our catalog."
        btn_text = "Browse Catalog"

    body = f"""
    <div class="badge badge-red">{badge}</div>
    <h1>{heading}</h1>
    <p>{intro}</p>
    <p>{note}</p>
    <a href="{catalog_url}" class="btn">{btn_text} &rarr;</a>
    """
    return _send(user.email, subject, _base_html(subject, body))
