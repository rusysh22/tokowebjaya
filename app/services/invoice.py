import uuid
import os
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.invoice import Invoice, InvoiceStatus
from app.models.order import Order, OrderStatus


def _generate_invoice_number() -> str:
    now = datetime.utcnow()
    uid = uuid.uuid4().hex[:6].upper()
    return f"INV-{now.strftime('%Y%m')}-{uid}"


def create_invoice(order_id: str):
    """Background task: create invoice for a paid order."""
    db: Session = SessionLocal()
    try:
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.status == OrderStatus.paid,
        ).first()

        if not order:
            return

        # Check existing invoice
        existing = db.query(Invoice).filter(Invoice.order_id == order_id).first()
        if existing:
            if existing.status == InvoiceStatus.unpaid:
                existing.status = InvoiceStatus.paid
                existing.paid_date = datetime.utcnow()
                db.commit()
            return

        invoice = Invoice(
            id=uuid.uuid4(),
            invoice_number=_generate_invoice_number(),
            order_id=order.id,
            amount=order.amount,
            status=InvoiceStatus.paid,
            due_date=datetime.utcnow() + timedelta(days=7),
            paid_date=datetime.utcnow(),
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        # Generate PDF
        try:
            pdf_path = _generate_pdf(invoice, order, db)
            invoice.pdf_path = pdf_path
            db.commit()
        except Exception:
            pass  # PDF failure should not break invoice creation

        # Send email notification via Resend
        try:
            from app.services.email import send_invoice_email
            ok = send_invoice_email(invoice, order)
            if ok:
                invoice.email_sent_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass

    finally:
        db.close()


def _generate_pdf(invoice: Invoice, order: Order, db: Session) -> str:
    from weasyprint import HTML

    product_name = ""
    if order.product:
        product_name = order.product.name_id

    customer_name = order.user.name if order.user else ""
    customer_email = order.user.email if order.user else ""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8"/>
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: Arial, Helvetica, sans-serif; color: #111; background: #fff; padding: 48px; font-size: 13px; }}
        .header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 40px; padding-bottom: 24px; border-bottom: 2px solid #0A0A0A; }}
        .brand {{ font-size: 20px; font-weight: 700; }}
        .brand span {{ color: #0A0A0A; }}
        .badge {{ background: #CAFF00; color: #0A0A0A; padding: 4px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; }}
        h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 8px; }}
        .meta {{ color: #555; margin-bottom: 32px; }}
        .meta p {{ margin-bottom: 4px; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 32px; margin-bottom: 32px; }}
        .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #888; margin-bottom: 6px; font-weight: 600; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; }}
        th {{ text-align: left; padding: 10px 12px; background: #0A0A0A; color: #fff; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }}
        td {{ padding: 12px; border-bottom: 1px solid #eee; }}
        .total-row td {{ font-weight: 700; font-size: 15px; border-bottom: none; border-top: 2px solid #0A0A0A; }}
        .status-paid {{ display: inline-block; background: #CAFF00; color: #0A0A0A; padding: 4px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #aaa; font-size: 11px; text-align: center; }}
      </style>
    </head>
    <body>
      <div class="header">
        <div>
          <div class="brand">Toko <span>Web</span> Jaya</div>
          <div style="color:#888; font-size:11px; margin-top:4px;">Solusi Digital Profesional</div>
        </div>
        <div class="badge">Invoice</div>
      </div>

      <h1>Invoice #{invoice.invoice_number}</h1>
      <div class="meta">
        <p>Tanggal: {invoice.created_at.strftime('%d %B %Y')}</p>
        <p>Order: {order.order_number}</p>
        <p>Status: <span class="status-paid">LUNAS</span></p>
      </div>

      <div class="grid">
        <div>
          <div class="label">Tagihan Kepada</div>
          <div style="font-weight:600">{customer_name}</div>
          <div style="color:#555">{customer_email}</div>
        </div>
        <div>
          <div class="label">Dari</div>
          <div style="font-weight:600">Toko Web Jaya</div>
          <div style="color:#555">contact@tokowebjaya.com</div>
        </div>
      </div>

      <table>
        <thead>
          <tr>
            <th>Deskripsi</th>
            <th>Tipe</th>
            <th style="text-align:right">Jumlah</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{product_name}</td>
            <td style="text-transform:capitalize">{order.type.value.replace('_', ' ')}</td>
            <td style="text-align:right">Rp {'{:,.0f}'.format(float(order.amount))}</td>
          </tr>
          <tr class="total-row">
            <td colspan="2">Total</td>
            <td style="text-align:right">Rp {'{:,.0f}'.format(float(invoice.amount))}</td>
          </tr>
        </tbody>
      </table>

      <div class="footer">
        Toko Web Jaya — Tidak Sedia Alat Bangunan. Tapi siap bantu bisnis digital Anda.<br/>
        tokowebjaya.com • contact@tokowebjaya.com
      </div>
    </body>
    </html>
    """

    pdf_dir = Path(settings.UPLOAD_DIR) / "invoices"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{invoice.invoice_number}.pdf"
    pdf_path = pdf_dir / filename

    HTML(string=html_content).write_pdf(str(pdf_path))
    return f"invoices/{filename}"


def _send_invoice_email(invoice: Invoice, order: Order, db: Session):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        return

    customer_email = order.user.email if order.user else None
    if not customer_email:
        return

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = customer_email
    msg["Subject"] = f"Invoice {invoice.invoice_number} — Toko Web Jaya"

    product_name = order.product.name_id if order.product else "Produk Digital"
    body = f"""Terima kasih atas pembelian Anda!

Invoice: {invoice.invoice_number}
Order: {order.order_number}
Produk: {product_name}
Total: Rp {float(invoice.amount):,.0f}
Status: LUNAS

Invoice PDF terlampir pada email ini.

Salam,
Tim Toko Web Jaya
"""
    msg.attach(MIMEText(body, "plain"))

    # Attach PDF if exists
    if invoice.pdf_path:
        pdf_full_path = Path(settings.UPLOAD_DIR) / invoice.pdf_path.replace("invoices/", "")
        if pdf_full_path.exists():
            with open(pdf_full_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={invoice.invoice_number}.pdf",
            )
            msg.attach(part)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
