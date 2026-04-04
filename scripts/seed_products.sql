-- ============================================================
-- Seed: RoC Product Suite
-- Run: psql -h localhost -p 5433 -U openpg -d tokowebjaya -f scripts/seed_products.sql
-- ============================================================

INSERT INTO products (
  id, slug,
  name_id, name_en,
  short_desc_id, short_desc_en,
  description_id, description_en,
  type, pricing_model, status,
  price_otf, price_monthly, price_yearly,
  category, tags, features,
  is_featured, sort_order,
  gallery,
  created_at, updated_at
) VALUES

-- ─── 1. RoC Service Desk Ticket ────────────────────────────────────────────
(
  gen_random_uuid(),
  'roc-service-desk-ticket',
  'RoC Service Desk Ticket',
  'RoC Service Desk Ticket',
  'Kelola tiket dukungan pelanggan via WhatsApp & Email dalam satu dashboard.',
  'Manage customer support tickets via WhatsApp & Email in one dashboard.',
  'RoC Service Desk Ticket adalah solusi helpdesk omnichannel yang menyatukan komunikasi WhatsApp dan Email ke dalam satu antarmuka. Tim Anda dapat menerima, mengelola, dan menyelesaikan tiket dengan cepat tanpa berpindah platform. Dilengkapi assignment otomatis, prioritas tiket, SLA tracking, dan laporan performa tim.',
  'RoC Service Desk Ticket is an omnichannel helpdesk solution that unifies WhatsApp and Email communication into a single interface. Your team can receive, manage, and resolve tickets quickly without switching platforms. Includes auto-assignment, ticket prioritization, SLA tracking, and team performance reports.',
  'software',
  'both',
  'active',
  NULL,
  299000,
  2990000,
  'Helpdesk',
  '["whatsapp","email","omnichannel","ticketing","helpdesk","crm"]',
  '[
    {"icon": "💬", "text_id": "Omnichannel WhatsApp & Email", "text_en": "Omnichannel WhatsApp & Email"},
    {"icon": "🎫", "text_id": "Manajemen tiket terpusat", "text_en": "Centralized ticket management"},
    {"icon": "⚡", "text_id": "Auto-assignment & prioritas tiket", "text_en": "Auto-assignment & ticket prioritization"},
    {"icon": "📊", "text_id": "SLA tracking & laporan performa", "text_en": "SLA tracking & performance reports"},
    {"icon": "👥", "text_id": "Multi-agent & multi-tim", "text_en": "Multi-agent & multi-team"},
    {"icon": "🔔", "text_id": "Notifikasi real-time", "text_en": "Real-time notifications"}
  ]',
  true,
  1,
  '[]',
  NOW(), NOW()
),

-- ─── 2. RoC Omnichannel ────────────────────────────────────────────────────
(
  gen_random_uuid(),
  'roc-omnichannel',
  'RoC Omnichannel',
  'RoC Omnichannel',
  'Hubungkan WhatsApp, Email, dan kanal lainnya dalam satu inbox terpadu.',
  'Connect WhatsApp, Email, and other channels into one unified inbox.',
  'RoC Omnichannel memungkinkan bisnis Anda mengelola semua komunikasi pelanggan dari berbagai kanal — WhatsApp, Email, Live Chat — dalam satu inbox terpadu. Tidak ada pesan yang terlewat, tidak ada pelanggan yang menunggu terlalu lama. Cocok untuk tim sales, customer service, dan after-sales support.',
  'RoC Omnichannel lets your business manage all customer communications from multiple channels — WhatsApp, Email, Live Chat — in one unified inbox. No missed messages, no customers waiting too long. Perfect for sales, customer service, and after-sales support teams.',
  'software',
  'subscription',
  'active',
  NULL,
  199000,
  1990000,
  'Komunikasi',
  '["whatsapp","email","live-chat","omnichannel","inbox","komunikasi"]',
  '[
    {"icon": "📱", "text_id": "WhatsApp Business API terintegrasi", "text_en": "Integrated WhatsApp Business API"},
    {"icon": "📧", "text_id": "Email inbox terpadu", "text_en": "Unified email inbox"},
    {"icon": "💬", "text_id": "Live chat widget untuk website", "text_en": "Live chat widget for website"},
    {"icon": "🤖", "text_id": "Chatbot & auto-reply", "text_en": "Chatbot & auto-reply"},
    {"icon": "📂", "text_id": "Riwayat percakapan lengkap", "text_en": "Complete conversation history"},
    {"icon": "📊", "text_id": "Laporan & analitik percakapan", "text_en": "Conversation reports & analytics"}
  ]',
  true,
  2,
  '[]',
  NOW(), NOW()
),

-- ─── 3. RoC Shorten Link ──────────────────────────────────────────────────
(
  gen_random_uuid(),
  'roc-shorten-link',
  'RoC Shorten Link',
  'RoC Shorten Link',
  'Persingkat, lacak, dan analisis setiap tautan yang Anda bagikan.',
  'Shorten, track, and analyze every link you share.',
  'RoC Shorten Link adalah layanan pemendek URL profesional dengan fitur analitik lengkap. Lacak jumlah klik, lokasi pengunjung, perangkat yang digunakan, dan waktu akses secara real-time. Dukung custom domain, branded link, dan QR code otomatis untuk setiap tautan.',
  'RoC Shorten Link is a professional URL shortener with complete analytics. Track click counts, visitor locations, devices used, and access times in real-time. Supports custom domains, branded links, and automatic QR codes for every link.',
  'software',
  'both',
  'active',
  149000,
  49000,
  490000,
  'Utilitas',
  '["url-shortener","link","analytics","qr-code","branding","tracking"]',
  '[
    {"icon": "🔗", "text_id": "Pemendek URL dengan custom alias", "text_en": "URL shortener with custom alias"},
    {"icon": "📊", "text_id": "Analitik klik real-time", "text_en": "Real-time click analytics"},
    {"icon": "🌍", "text_id": "Tracking lokasi & perangkat", "text_en": "Location & device tracking"},
    {"icon": "🎨", "text_id": "Branded link & custom domain", "text_en": "Branded links & custom domain"},
    {"icon": "📷", "text_id": "QR Code otomatis tiap link", "text_en": "Automatic QR Code for each link"},
    {"icon": "⏰", "text_id": "Link expiry & password protection", "text_en": "Link expiry & password protection"}
  ]',
  false,
  3,
  '[]',
  NOW(), NOW()
),

-- ─── 4. RoC Form Creator ──────────────────────────────────────────────────
(
  gen_random_uuid(),
  'roc-form-creator',
  'RoC Form Creator',
  'RoC Form Creator',
  'Buat formulir online profesional tanpa coding, kumpulkan data dengan mudah.',
  'Build professional online forms without coding, collect data effortlessly.',
  'RoC Form Creator memungkinkan Anda membuat formulir online yang indah dan fungsional hanya dengan drag & drop — tanpa perlu coding. Dari form pendaftaran, survei, kuis, hingga order form, semua bisa dibuat dalam hitungan menit. Data responden tersimpan otomatis dan bisa diexport ke Excel atau terkoneksi ke sistem lain via webhook.',
  'RoC Form Creator lets you build beautiful and functional online forms with just drag & drop — no coding required. From registration forms, surveys, quizzes, to order forms, everything can be built in minutes. Respondent data is automatically saved and can be exported to Excel or connected to other systems via webhook.',
  'software',
  'both',
  'active',
  99000,
  39000,
  390000,
  'Produktivitas',
  '["form","survey","drag-drop","no-code","data-collection","webhook"]',
  '[
    {"icon": "🖱️", "text_id": "Drag & drop form builder", "text_en": "Drag & drop form builder"},
    {"icon": "📋", "text_id": "20+ tipe field tersedia", "text_en": "20+ field types available"},
    {"icon": "📱", "text_id": "Responsive di semua perangkat", "text_en": "Responsive on all devices"},
    {"icon": "📥", "text_id": "Export data ke Excel / CSV", "text_en": "Export data to Excel / CSV"},
    {"icon": "🔗", "text_id": "Integrasi webhook & API", "text_en": "Webhook & API integration"},
    {"icon": "🎨", "text_id": "Custom tema & branding", "text_en": "Custom theme & branding"}
  ]',
  false,
  4,
  '[]',
  NOW(), NOW()
);
