from fastapi import Request
from app.core.config import settings

TRANSLATIONS = {
    "id": {
        "nav_home": "Beranda",
        "nav_catalog": "Katalog",
        "nav_solutions": "Solusi",
        "nav_about": "Tentang Kami",
        "nav_contact": "Kontak",
        "nav_login": "Masuk",
        "nav_dashboard": "Dashboard",
        "nav_logout": "Keluar",
        "hero_title": "Produk Digital untuk Bisnis yang Lebih Cerdas",
        "hero_subtitle": "E-book, kursus, software, template, dan layanan IT profesional. Semua dalam satu platform.",
        "hero_cta_primary": "Lihat Katalog",
        "hero_cta_secondary": "Pelajari Lebih Lanjut",
        "humor_title": "Maaf, Kami Tidak Jual Semen",
        "humor_body": "Kami tahu nama kami terdengar seperti toko bangunan — tapi percayalah, kami tidak menyediakan semen, pasir, batu bata, genteng, atau cat tembok. Yang kami jual adalah produk digital: e-book, kursus online, software, dan template keren. Kalau Anda butuh material bangunan, silakan cari di tempat lain. Tapi kalau bisnis Anda butuh solusi digital, Anda sudah di tempat yang tepat.",
        "humor_cta": "Oke, Tunjukkan Produknya",
        "catalog_title": "Katalog Produk",
        "catalog_subtitle": "Produk digital pilihan untuk kebutuhan bisnis Anda",
        "footer_tagline": "Solusi digital profesional untuk bisnis modern.",
        "footer_rights": "Hak cipta dilindungi",
        "price_otf": "Bayar Sekali",
        "price_subscription": "Langganan",
        "per_month": "/ bulan",
        "per_year": "/ tahun",
        "buy_now": "Beli Sekarang",
        "subscribe": "Berlangganan",
        "login_title": "Masuk ke Akun Anda",
        "login_google": "Masuk dengan Google",
        "dashboard_welcome": "Selamat Datang",
        "dashboard_orders": "Pesanan Saya",
        "dashboard_invoices": "Invoice",
        "dashboard_subscriptions": "Langganan",
    },
    "en": {
        "nav_home": "Home",
        "nav_catalog": "Catalog",
        "nav_solutions": "Solutions",
        "nav_about": "About",
        "nav_contact": "Contact",
        "nav_login": "Login",
        "nav_dashboard": "Dashboard",
        "nav_logout": "Logout",
        "hero_title": "Digital Products for Smarter Business",
        "hero_subtitle": "E-books, courses, software, templates, and professional IT services. All in one platform.",
        "hero_cta_primary": "Browse Catalog",
        "hero_cta_secondary": "Learn More",
        "humor_title": "Sorry, We Don't Sell Cement",
        "humor_body": "We know our name sounds like a hardware store — but trust us, we don't carry cement, sand, bricks, roof tiles, or wall paint. What we sell is digital: e-books, online courses, software, and templates. If you need building materials, you're in the wrong place. But if your business needs digital solutions, you've come to the right spot.",
        "humor_cta": "Got It, Show Me the Products",
        "catalog_title": "Product Catalog",
        "catalog_subtitle": "Curated digital products for your business needs",
        "footer_tagline": "Professional digital solutions for modern businesses.",
        "footer_rights": "All rights reserved",
        "price_otf": "One-Time",
        "price_subscription": "Subscription",
        "per_month": "/ month",
        "per_year": "/ year",
        "buy_now": "Buy Now",
        "subscribe": "Subscribe",
        "login_title": "Sign In to Your Account",
        "login_google": "Continue with Google",
        "dashboard_welcome": "Welcome",
        "dashboard_orders": "My Orders",
        "dashboard_invoices": "Invoices",
        "dashboard_subscriptions": "Subscriptions",
    },
}


def get_locale(request: Request) -> str:
    path = request.url.path
    for locale in settings.SUPPORTED_LOCALES:
        if path.startswith(f"/{locale}/") or path == f"/{locale}":
            return locale
    accept_lang = request.headers.get("accept-language", "")
    if "id" in accept_lang:
        return "id"
    return settings.DEFAULT_LOCALE


def t(locale: str, key: str) -> str:
    return TRANSLATIONS.get(locale, {}).get(key, key)
