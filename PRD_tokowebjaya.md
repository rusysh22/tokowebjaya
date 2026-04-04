# PRD - tokowebjaya.com

## 1. Ringkasan Eksekutif
Tokowebjaya.com adalah portal yang menyediakan penjualan produk digital (e-book, kursus, software, template) + solusi (konsultasi IT, integrasi, pembuatan web) dengan central billing untuk invoice, payment, dan subscription.

Target pengguna: B2B dan B2C.

Tujuan utama:
- Menjadi landing page company profile + katalog produk digital.
- Menjadi platform transaksi digital yang otomatis (invoice, payment, subscription, one-time fee).
- Menyediakan admin panel untuk manajemen lengkap (produk, pelanggan, transaksi, laporan).

## 2. Fungsi Utama MVP
### 2.1 Autentikasi dan Akses
- Login/Sign-up Google (OAuth2).
- Role-based: Admin / Customer.

### 2.2 Manajemen Produk dan Solusi
- CRUD produk digital dan layanan solusi.
- Kategori & tag.
- Pricing model: OTF (one-time fee) + Subscription (bulanan/tahunan).

### 2.3 Checkout dan Pembayaran
- Pilihan gateway utama: Duitku.
- Fallback gateway: mayar.id.
- Proses otomatis:
  - Generate pengajuan transaksi.
  - Redirect ke checkout gateway.
  - Webhook callback status (success/failed/pending).

### 2.4 Invoice & Billing
- Generate invoice otomatis pada transaksi berhasil.
- Nomor invoice unik, status: unpaid/paid/overdue.
- PDF invoice + stored record.
- Email notif invoice (pembuatan, pembayaran, overdue).

### 2.5 Dashboard Admin
- Overview KPI: pendapatan, order, subscription aktif, overdue invoice.
- Manajemen transaksi (filter by status).
- Data customer & subscription.
- Laporan sales (harian/mingguan/bulanan) + export CSV/Excel.

### 2.6 Dashboard Customer
- Lihat order history, invoice, status subscription.
- Download invoice PDF.
- Kelola langganan (batal/renew).

## 3. Non-Functional Requirement
- Stack: Python backend (FastAPI/Django/Flask), DB PostgreSQL/MySQL.
- Frontend: statis + `jokoUI.css`.
- Deployment: Docker + CI/CD rails.
- Backup DB, logging, monitoring.
- Keamanan: HTTPS, input validation, XSS/CSRF protection.

## 4. Roadmap Phased Delivery
### Phase 1 (MVP)
1. Setup project, database, environment.
2. Auth Google (user/admin) dan role.
3. Dashboard company profile + katalog produk.
4. CRUD produk.
5. Checkout OTF + subscription.
6. Integrasi gateway Duitku & mayar.id.
7. Auto invoice dan email.
8. UI admin/customer.

### Phase 2
1. Recurring billing otomatis + retry payment.
2. Multi-currency & pajak/VAT.
3. Advanced laporan epidemi.
4. API eksternal untuk integrasi B2B.
5. Marketplace multi-seller jika perlu.

### Phase 3
1. Automasi invoice per periode (langganan + siklus billing).
2. Customer portal dengan self-service.
3. Integrasi accounting (Xero/QuickBooks/AccSheet).

## 5. KPI & Sukses
- 100% transaksi mengenerate invoice otomatis.
- 100% checkout gateway sukses.
- 100% login Google bekerja.
- 90% laporan ditampilkan dengan benar.
- UX 80+ pada usability test.

## 6. Skema Data Utama
- User (id, nama, email, role, google_id, status)
- Product (id, nama, deskripsi, tipe, harga, durasi_subscription, status)
- Order (id, user_id, product_id, tipe, amount, status, payment_gateway, created_at)
- Invoice (id, order_id, nomor_invoice, amount, status, due_date, paid_date)
- Subscription (id, user_id, product_id, status, started_at, next_billing_date)

## 7. Catatan Integrasi
- Duitku: API docs, endpoint payment request, callback signature.
- mayar.id: API docs, callback,
- Email: SMTP/transporter untuk email invoice.
- File storage invoice PDF (local atau blob).

## 8. Pengujian
- Unit testing backend, integrasi gateway.
- E2E testing flow checkout/invoice/subscription.
- Test otomatis dan manual.

## 9. Next Steps
1. Buat wireframe halaman landing, catalog, dashboard.
2. Setup skeleton Python project (FastAPI + SQLAlchemy).
3. Buat model dan endpoint CRUD.
4. Implement payment gateway pemesanan (Duitku + mayar.id).
5. Implement invoice generator (PDF + email).
6. UAT & iterasi.
