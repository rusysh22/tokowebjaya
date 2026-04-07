"""
Static payment instructions per method code.
Grouped by channel (ATM, Mobile Banking, Internet Banking, etc.)
"""

GUIDES: dict[str, list[dict]] = {
    # ── BCA Virtual Account ──────────────────────────────────────────────────
    "BC": [
        {
            "name": "ATM BCA",
            "steps": [
                "Masukkan kartu ATM dan PIN Anda",
                "Pilih menu **Transaksi Lainnya**",
                "Pilih **Transfer** → **Ke Rekening Virtual Account**",
                "Masukkan **Nomor Virtual Account** di atas",
                "Periksa detail transaksi, lalu pilih **Ya**",
            ],
        },
        {
            "name": "myBCA / BCA Mobile",
            "steps": [
                "Login ke aplikasi **myBCA**",
                "Pilih **m-Transfer** → **BCA Virtual Account**",
                "Masukkan **Nomor Virtual Account** di atas",
                "Masukkan jumlah tagihan, lalu konfirmasi",
                "Masukkan **PIN m-BCA** untuk menyelesaikan",
            ],
        },
        {
            "name": "Internet Banking BCA",
            "steps": [
                "Login di **klikbca.com**",
                "Pilih **Fund Transfer** → **Transfer to BCA Virtual Account**",
                "Masukkan **Nomor Virtual Account** di atas",
                "Periksa detail, masukkan **respon KeyBCA**, lalu kirim",
            ],
        },
    ],

    # ── BRI Virtual Account ──────────────────────────────────────────────────
    "BR": [
        {
            "name": "ATM BRI",
            "steps": [
                "Masukkan kartu ATM dan PIN Anda",
                "Pilih **Transaksi Lain** → **Pembayaran** → **Lainnya**",
                "Pilih **BRIVA**, masukkan **Nomor Virtual Account** di atas",
                "Periksa detail dan konfirmasi pembayaran",
            ],
        },
        {
            "name": "BRImo",
            "steps": [
                "Login ke aplikasi **BRImo**",
                "Pilih **BRIVA** dari menu utama",
                "Masukkan **Nomor Virtual Account** di atas",
                "Masukkan PIN untuk konfirmasi",
            ],
        },
        {
            "name": "Internet Banking BRI",
            "steps": [
                "Login di **ib.bri.co.id**",
                "Pilih **Pembayaran** → **BRIVA**",
                "Masukkan **Nomor Virtual Account** di atas",
                "Konfirmasi dengan **mToken**",
            ],
        },
    ],

    # ── BNI Virtual Account ──────────────────────────────────────────────────
    "I1": [
        {
            "name": "ATM BNI",
            "steps": [
                "Masukkan kartu ATM dan PIN Anda",
                "Pilih **Menu Lain** → **Transfer** → **Rekening Tabungan**",
                "Pilih **Ke Rekening BNI** → masukkan **Nomor Virtual Account**",
                "Masukkan jumlah tagihan persis, konfirmasi",
            ],
        },
        {
            "name": "BNI Mobile Banking",
            "steps": [
                "Login ke aplikasi **BNI Mobile**",
                "Pilih **Transfer** → **Virtual Account Billing**",
                "Masukkan **Nomor Virtual Account** di atas",
                "Konfirmasi dengan **password transaksi**",
            ],
        },
    ],

    # ── Mandiri Virtual Account ──────────────────────────────────────────────
    "M2": [
        {
            "name": "ATM Mandiri",
            "steps": [
                "Masukkan kartu ATM dan PIN Anda",
                "Pilih **Bayar/Beli** → **Lainnya** → **Multi Payment**",
                "Masukkan kode perusahaan **70018**, lalu **Nomor Virtual Account**",
                "Konfirmasi jumlah dan selesaikan transaksi",
            ],
        },
        {
            "name": "Livin' by Mandiri",
            "steps": [
                "Login ke aplikasi **Livin' by Mandiri**",
                "Pilih **Bayar** → **Multipayment**",
                "Masukkan **Nomor Virtual Account** di atas",
                "Konfirmasi dengan **PIN Livin'**",
            ],
        },
    ],

    # ── BSI Virtual Account ──────────────────────────────────────────────────
    "BV": [
        {
            "name": "ATM BSI",
            "steps": [
                "Masukkan kartu ATM dan PIN Anda",
                "Pilih **Transaksi Lainnya** → **Pembayaran**",
                "Pilih **Virtual Account**, masukkan **Nomor Virtual Account**",
                "Konfirmasi detail pembayaran",
            ],
        },
        {
            "name": "BSI Mobile",
            "steps": [
                "Login ke aplikasi **BSI Mobile**",
                "Pilih **Bayar** → **Virtual Account**",
                "Masukkan **Nomor Virtual Account** di atas dan konfirmasi",
            ],
        },
    ],

    # ── CIMB Niaga Virtual Account ───────────────────────────────────────────
    "B1": [
        {
            "name": "ATM CIMB Niaga",
            "steps": [
                "Masukkan kartu ATM dan PIN Anda",
                "Pilih **Transaksi Lainnya** → **Pembayaran** → **Virtual Account**",
                "Masukkan **Nomor Virtual Account** di atas",
                "Konfirmasi detail dan selesaikan",
            ],
        },
        {
            "name": "OCTO Mobile",
            "steps": [
                "Login ke aplikasi **OCTO Mobile**",
                "Pilih **Transfer** → **Virtual Account**",
                "Masukkan **Nomor Virtual Account** dan konfirmasi PIN",
            ],
        },
    ],

    # ── QRIS (ShopeePay, LinkAja, Nobu, dll) ────────────────────────────────
    "SP": [
        {
            "name": "Semua Aplikasi QRIS",
            "steps": [
                "Buka aplikasi e-wallet atau mobile banking Anda",
                "Pilih menu **Scan QR** atau **Bayar dengan QR**",
                "Arahkan kamera ke **QR Code** di atas",
                "Periksa jumlah tagihan, lalu konfirmasi pembayaran",
            ],
        },
    ],
    "LQ": [
        {
            "name": "Semua Aplikasi QRIS",
            "steps": [
                "Buka aplikasi e-wallet atau mobile banking Anda",
                "Pilih menu **Scan QR** atau **Bayar dengan QR**",
                "Arahkan kamera ke **QR Code** di atas",
                "Periksa jumlah tagihan, lalu konfirmasi pembayaran",
            ],
        },
    ],
    "NQ": [
        {
            "name": "Semua Aplikasi QRIS",
            "steps": [
                "Buka aplikasi e-wallet atau mobile banking Anda",
                "Pilih **Scan QR**, arahkan ke **QR Code** di atas",
                "Konfirmasi jumlah dan selesaikan pembayaran",
            ],
        },
    ],

    # ── OVO ──────────────────────────────────────────────────────────────────
    "OV": [
        {
            "name": "Aplikasi OVO",
            "steps": [
                "Buka aplikasi **OVO**",
                "Pilih **Scan** di halaman utama",
                "Arahkan kamera ke **QR Code** di atas",
                "Konfirmasi jumlah tagihan dan selesaikan",
            ],
        },
    ],

    # ── DANA ─────────────────────────────────────────────────────────────────
    "DA": [
        {
            "name": "Aplikasi DANA",
            "steps": [
                "Buka aplikasi **DANA**",
                "Pilih **Scan QR** di halaman utama",
                "Arahkan kamera ke **QR Code** atau link pembayaran",
                "Konfirmasi dan masukkan PIN DANA",
            ],
        },
    ],

    # ── ShopeePay App ─────────────────────────────────────────────────────────
    "SA": [
        {
            "name": "ShopeePay",
            "steps": [
                "Buka aplikasi **Shopee** → pilih **ShopeePay**",
                "Pilih **Scan** dan arahkan ke QR di atas",
                "Konfirmasi jumlah dan masukkan PIN",
            ],
        },
    ],

    # ── Indomaret ────────────────────────────────────────────────────────────
    "IR": [
        {
            "name": "Kasir Indomaret",
            "steps": [
                "Pergi ke **Indomaret** terdekat",
                "Beritahu kasir: *\"Saya ingin bayar Virtual Account\"*",
                "Berikan **Nomor Kode** di atas kepada kasir",
                "Bayar sejumlah **total tagihan** (persis)",
                "Simpan struk sebagai bukti pembayaran",
            ],
        },
    ],

    # ── Alfamart / Retail ─────────────────────────────────────────────────────
    "FT": [
        {
            "name": "Kasir Alfamart",
            "steps": [
                "Pergi ke **Alfamart** terdekat",
                "Beritahu kasir: *\"Saya ingin bayar Duitku\"*",
                "Berikan **Nomor Kode** di atas kepada kasir",
                "Bayar sejumlah **total tagihan** (persis)",
                "Simpan struk sebagai bukti pembayaran",
            ],
        },
    ],
}

# Fallback guide untuk metode yang belum terdaftar
FALLBACK_GUIDE: list[dict] = [
    {
        "name": "Instruksi Umum",
        "steps": [
            "Buka aplikasi atau platform pembayaran yang dipilih",
            "Masukkan nomor / kode pembayaran di atas",
            "Konfirmasi jumlah tagihan",
            "Selesaikan transaksi sesuai instruksi di aplikasi",
        ],
    }
]


def get_guide(payment_method_code: str) -> list[dict]:
    """Return payment guide for given method code. Falls back to generic guide."""
    return GUIDES.get((payment_method_code or "").upper(), FALLBACK_GUIDE)
