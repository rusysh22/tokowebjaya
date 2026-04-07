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


def send_contact_notification(name: str, email: str, subject: str, message: str, admin_email: str) -> bool:
    """Send contact form submission notification to admin."""
    email_subject = f"[Kontak] {subject or 'Pesan baru'} — dari {name}"

    body = f"""
    <div class="badge">Pesan Kontak Baru</div>
    <h1>Pesan baru dari {name}</h1>
    <p>Ada pesan baru masuk melalui form kontak website.</p>
    <table class="info-table">
      <tr><td>Nama</td><td>{name}</td></tr>
      <tr><td>Email</td><td><a href="mailto:{email}" style="color:#0a0a0a">{email}</a></td></tr>
      <tr><td>Subjek</td><td>{subject or '-'}</td></tr>
    </table>
    <div style="background:#f9f9f9;border-left:3px solid #CAFF00;padding:16px 20px;margin:20px 0;font-size:14px;line-height:1.7;color:#333;white-space:pre-wrap">{message}</div>
    <a href="mailto:{email}?subject=Re: {subject or 'Pesan Anda'}" class="btn">Balas Email &rarr;</a>
    <p style="font-size:12px;color:#bbb;margin-top:16px">Pesan ini dikirim otomatis dari form kontak Toko Web Jaya.</p>
    """
    return _send(admin_email, email_subject, _base_html(email_subject, body))


def send_contact_autoreply(name: str, to_email: str, locale: str = "id") -> bool:
    """Send auto-reply confirmation to the person who submitted the contact form."""
    if locale == "id":
        subject  = "Pesan Anda telah kami terima — Toko Web Jaya"
        badge    = "Pesan Diterima"
        heading  = f"Halo, {name.split()[0]}!"
        intro    = "Terima kasih telah menghubungi kami. Pesan Anda telah kami terima dan tim kami akan membalas dalam <strong>1×24 jam</strong> hari kerja."
        note     = "Jika ada hal mendesak, Anda juga bisa menghubungi kami langsung melalui halaman kontak."
    else:
        subject  = "We've received your message — Toko Web Jaya"
        badge    = "Message Received"
        heading  = f"Hello, {name.split()[0]}!"
        intro    = "Thank you for reaching out. We've received your message and our team will reply within <strong>1 business day</strong>."
        note     = "For urgent matters, you can also reach us directly through our contact page."

    body = f"""
    <div class="badge">{badge}</div>
    <h1>{heading}</h1>
    <p>{intro}</p>
    <p style="color:#888;font-size:13px">{note}</p>
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


# ── Appointment emails ────────────────────────────────────────────────────────

def send_appointment_booked(appt, product, user, locale: str = "id") -> bool:
    """Notify user (booking confirmed) + admin (new booking)."""
    product_name = product.name_id if locale == "id" else product.name_en
    date_str     = appt.appt_date.strftime("%d %B %Y")
    time_str     = appt.appt_time.strftime("%H:%M") + " WIB"
    type_label   = {"demo": "Demo Produk", "call": "Video/Phone Call", "meeting": "Meeting Offline"}.get(appt.appt_type.value, appt.appt_type.value)

    # Email to user
    if locale == "id":
        subject  = f"Booking Diterima — {product_name}"
        heading  = "Booking Anda Diterima!"
        intro    = f"Terima kasih! Booking <strong>{type_label}</strong> untuk produk <strong>{product_name}</strong> telah kami terima dan sedang menunggu konfirmasi dari penjual."
        detail   = f"<strong>Tanggal:</strong> {date_str}<br><strong>Waktu:</strong> {time_str}"
        note     = "Anda akan mendapat notifikasi email saat penjual mengkonfirmasi janji temu."
        badge    = "Booking Diterima"
    else:
        subject  = f"Booking Received — {product_name}"
        heading  = "Your Booking is Received!"
        intro    = f"Thank you! Your <strong>{type_label}</strong> booking for <strong>{product_name}</strong> has been received and is pending seller confirmation."
        detail   = f"<strong>Date:</strong> {date_str}<br><strong>Time:</strong> {time_str}"
        note     = "You will receive an email notification once the seller confirms your appointment."
        badge    = "Booking Received"

    body = f"""
    <div class="badge">{badge}</div>
    <h1>{heading}</h1>
    <p>{intro}</p>
    <div style="background:#111;border:1px solid #222;padding:16px;margin:16px 0;font-size:14px;line-height:1.8">{detail}</div>
    <p style="color:#888;font-size:13px">{note}</p>
    """
    ok_user = _send(user.email, subject, _base_html(subject, body))

    # Email to admin
    admin_subject = f"[New Appointment] {product_name} — {user.name}"
    admin_body = f"""
    <div class="badge">New Appointment</div>
    <h1>Booking Baru Masuk</h1>
    <p>Ada booking baru yang perlu dikonfirmasi.</p>
    <div style="background:#111;border:1px solid #222;padding:16px;margin:16px 0;font-size:14px;line-height:1.8">
      <strong>Produk:</strong> {product_name}<br>
      <strong>Tipe:</strong> {type_label}<br>
      <strong>Tanggal:</strong> {date_str}<br>
      <strong>Waktu:</strong> {time_str}<br>
      <strong>Nama:</strong> {user.name}<br>
      <strong>Email:</strong> {user.email}<br>
      {f'<strong>Catatan:</strong> {appt.notes}' if appt.notes else ''}
    </div>
    <a href="{settings.BASE_URL}/id/admin/appointments" class="btn">Lihat di Admin Panel &rarr;</a>
    """
    _send(settings.SMTP_FROM, admin_subject, _base_html(admin_subject, admin_body))
    return ok_user


def send_appointment_confirmed(appt) -> bool:
    user         = appt.user
    product      = appt.product
    product_name = product.name_id
    date_str     = appt.appt_date.strftime("%d %B %Y")
    time_str     = appt.appt_time.strftime("%H:%M") + " WIB"

    subject = f"Janji Temu Dikonfirmasi — {product_name}"
    body = f"""
    <div class="badge badge-green">Dikonfirmasi</div>
    <h1>Janji Temu Anda Dikonfirmasi!</h1>
    <p>Penjual telah mengkonfirmasi janji temu Anda untuk produk <strong>{product_name}</strong>.</p>
    <div style="background:#111;border:1px solid #222;padding:16px;margin:16px 0;font-size:14px;line-height:1.8">
      <strong>Tanggal:</strong> {date_str}<br>
      <strong>Waktu:</strong> {time_str}<br>
      {f'<strong>Catatan penjual:</strong> {appt.admin_note}' if appt.admin_note else ''}
    </div>
    <p style="color:#888;font-size:13px">Silakan hadir tepat waktu. Jika ada perubahan, hubungi kami segera.</p>
    """
    return _send(user.email, subject, _base_html(subject, body))


def send_appointment_rejected(appt) -> bool:
    user         = appt.user
    product      = appt.product
    product_name = product.name_id

    subject = f"Janji Temu Tidak Dapat Dikonfirmasi — {product_name}"
    body = f"""
    <div class="badge badge-red">Tidak Dikonfirmasi</div>
    <h1>Mohon Maaf</h1>
    <p>Sayangnya janji temu Anda untuk produk <strong>{product_name}</strong> tidak dapat dikonfirmasi saat ini.</p>
    {f'<p><strong>Alasan:</strong> {appt.admin_note}</p>' if appt.admin_note else ''}
    <p>Silakan coba pilih waktu lain atau hubungi kami langsung.</p>
    <a href="{settings.BASE_URL}/id/catalog" class="btn">Lihat Produk Lain &rarr;</a>
    """
    return _send(user.email, subject, _base_html(subject, body))


# ─── License Delivery Email ───────────────────────────────────────────────────

def send_license_delivery(order, license, locale: str = "id") -> bool:
    """
    Send product license/access credentials to user after successful order.
    Covers: token, password, credential, download types.
    """
    user = order.user
    if not user:
        return False

    product      = order.product
    product_name = product.name_id if locale == "id" else product.name_en
    ltype        = license.license_type
    dashboard_url = f"{settings.BASE_URL}/{locale}/dashboard/licenses"

    # Build credential rows based on license type
    credential_rows = ""
    delivery_note   = ""

    if ltype == "token":
        credential_rows = f"""
        <tr><td>License Key</td><td style="font-family:monospace;font-size:15px;letter-spacing:2px;color:#0a0a0a;font-weight:900">{license.license_key}</td></tr>
        """
        if license.access_url:
            credential_rows += f'<tr><td>URL Akses</td><td><a href="{license.access_url}" style="color:#0a0a0a">{license.access_url}</a></td></tr>'
        if license.expires_at:
            credential_rows += f'<tr><td>Berlaku hingga</td><td>{license.expires_at.strftime("%d %B %Y")}</td></tr>'
        else:
            credential_rows += '<tr><td>Masa berlaku</td><td>Seumur hidup (Lifetime)</td></tr>'
        delivery_note = "Masukkan License Key di atas pada aplikasi untuk mengaktifkan akses Anda." if locale == "id" else "Enter the License Key above in the application to activate your access."

    elif ltype == "password":
        credential_rows = f"""
        <tr><td>Password</td><td style="font-family:monospace;font-size:15px;letter-spacing:2px;color:#0a0a0a;font-weight:900">{license.license_password}</td></tr>
        """
        if license.access_url:
            credential_rows += f'<tr><td>Download</td><td><a href="{license.access_url}" style="color:#0a0a0a">{license.access_url}</a></td></tr>'
        delivery_note = "Gunakan password di atas untuk membuka file terenkripsi yang telah Anda beli." if locale == "id" else "Use the password above to open the encrypted file you purchased."

    elif ltype == "credential":
        credential_rows = f"""
        <tr><td>Username</td><td style="font-family:monospace;font-size:14px;color:#0a0a0a;font-weight:700">{license.license_username}</td></tr>
        <tr><td>Password</td><td style="font-family:monospace;font-size:14px;color:#0a0a0a;font-weight:700">{license.license_password}</td></tr>
        """
        if license.access_url:
            credential_rows += f'<tr><td>URL Login</td><td><a href="{license.access_url}" style="color:#0a0a0a">{license.access_url}</a></td></tr>'
        if license.expires_at:
            credential_rows += f'<tr><td>Berlaku hingga</td><td>{license.expires_at.strftime("%d %B %Y")}</td></tr>'
        delivery_note = "Gunakan kredensial di atas untuk login ke layanan yang Anda beli. Segera ganti password setelah login pertama." if locale == "id" else "Use the credentials above to log in to your purchased service. Please change your password after first login."

    elif ltype == "download":
        from app.services.license import generate_signed_download_url
        download_url = generate_signed_download_url(license)
        credential_rows = f"""
        <tr><td>Link Download</td><td><a href="{download_url}" style="color:#0a0a0a;font-weight:700">Klik untuk Download</a></td></tr>
        <tr><td>Maks. Download</td><td>{license.max_downloads}x</td></tr>
        <tr><td>Link berlaku</td><td>Tidak expired (maks {license.max_downloads}x)</td></tr>
        """
        delivery_note = "Link download di atas hanya bisa digunakan sebanyak 5 kali. Simpan file setelah diunduh." if locale == "id" else "The download link above can only be used 5 times. Save the file after downloading."

    # Guidebook section
    guidebook_html = ""
    guidebook_text = product.guidebook_text_id if locale == "id" else product.guidebook_text_en
    if guidebook_text:
        guidebook_html = f"""
        <div style="background:#f9f9f9;border-left:3px solid #CAFF00;padding:16px 20px;margin:20px 0;">
          <p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:8px;">Panduan Penggunaan</p>
          <p style="font-size:13px;color:#444;line-height:1.7;margin:0">{guidebook_text}</p>
        </div>
        """
    if product.guidebook_url:
        guidebook_html += f'<p style="margin-top:12px"><a href="{product.guidebook_url}" class="btn" style="display:inline-block;background:#0a0a0a;color:#CAFF00;text-decoration:none;font-weight:700;font-size:13px;padding:10px 24px">📖 Buka Panduan Lengkap</a></p>'

    if locale == "id":
        subject = f"Akses Produk Anda — {product_name}"
        body = f"""
        <div class="badge">Akses Produk</div>
        <h1>Produk siap digunakan! 🎉</h1>
        <p>Hei <strong>{user.name or user.email}</strong>, terima kasih atas pembelian <strong>{product_name}</strong>. Berikut adalah detail akses Anda:</p>
        <table class="info-table">
          <tr><td>Produk</td><td>{product_name}</td></tr>
          <tr><td>Order</td><td>{order.order_number}</td></tr>
          {credential_rows}
        </table>
        <p style="background:#fffbeb;border:1px solid #fcd34d;padding:12px 16px;font-size:13px;color:#92400e;">
          ⚠️ <strong>Penting:</strong> Simpan informasi ini di tempat yang aman. {delivery_note}
        </p>
        {guidebook_html}
        <a href="{dashboard_url}" class="btn">Lihat di Dashboard &rarr;</a>
        <p style="font-size:12px;color:#aaa;margin-top:16px">Butuh bantuan? Balas email ini atau hubungi support kami.</p>
        """
    else:
        subject = f"Your Product Access — {product_name}"
        body = f"""
        <div class="badge">Product Access</div>
        <h1>Your product is ready! 🎉</h1>
        <p>Hi <strong>{user.name or user.email}</strong>, thank you for purchasing <strong>{product_name}</strong>. Here are your access details:</p>
        <table class="info-table">
          <tr><td>Product</td><td>{product_name}</td></tr>
          <tr><td>Order</td><td>{order.order_number}</td></tr>
          {credential_rows}
        </table>
        <p style="background:#fffbeb;border:1px solid #fcd34d;padding:12px 16px;font-size:13px;color:#92400e;">
          ⚠️ <strong>Important:</strong> Save this information in a safe place. {delivery_note}
        </p>
        {guidebook_html}
        <a href="{dashboard_url}" class="btn">View in Dashboard &rarr;</a>
        <p style="font-size:12px;color:#aaa;margin-top:16px">Need help? Reply to this email or contact our support.</p>
        """

    return _send(user.email, subject, _base_html(subject, body))


def send_license_reminder(license, days_left: int, locale: str = "id") -> bool:
    """Send subscription expiry reminder — 7 days or 3 days before expiry."""
    user    = license.user
    product = license.product
    if not user or not product:
        return False

    product_name  = product.name_id if locale == "id" else product.name_en
    renewal_url   = f"{settings.BASE_URL}/{locale}/checkout/{product.id}?type=subscription"
    dashboard_url = f"{settings.BASE_URL}/{locale}/dashboard/licenses"
    expire_date   = license.expires_at.strftime("%d %B %Y") if license.expires_at else "-"

    if locale == "id":
        subject = f"Langganan {product_name} akan berakhir dalam {days_left} hari"
        urgency = "segera" if days_left <= 3 else "segera"
        body = f"""
        <div class="badge" style="background:#fef3c7;color:#92400e">Pengingat Langganan</div>
        <h1>Langganan Anda akan berakhir!</h1>
        <p>Hei <strong>{user.name or user.email}</strong>, langganan <strong>{product_name}</strong> Anda akan berakhir dalam <strong>{days_left} hari</strong> ({expire_date}).</p>
        <p>Perbarui langganan Anda {urgency} agar akses tidak terputus.</p>
        <a href="{renewal_url}" class="btn">Perbarui Langganan &rarr;</a>
        <p style="font-size:12px;color:#aaa;margin-top:16px"><a href="{dashboard_url}">Lihat detail lisensi Anda</a></p>
        """
    else:
        subject = f"{product_name} subscription expires in {days_left} days"
        body = f"""
        <div class="badge" style="background:#fef3c7;color:#92400e">Subscription Reminder</div>
        <h1>Your subscription is expiring!</h1>
        <p>Hi <strong>{user.name or user.email}</strong>, your <strong>{product_name}</strong> subscription expires in <strong>{days_left} days</strong> ({expire_date}).</p>
        <p>Renew your subscription now to avoid any interruption to your access.</p>
        <a href="{renewal_url}" class="btn">Renew Subscription &rarr;</a>
        <p style="font-size:12px;color:#aaa;margin-top:16px"><a href="{dashboard_url}">View your license details</a></p>
        """

    return _send(user.email, subject, _base_html(subject, body))
