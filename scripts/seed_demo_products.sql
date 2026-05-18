-- ============================================================
-- Demo Seed: 4 produk lengkap mencakup semua pricing model
--
--   1. NovaSite Pro    → one_time                 (3 package: Personal / Pro / Agency)
--   2. DataVault Cloud → subscription monthly only (3 package: Starter / Business / Enterprise)
--   3. RankX SEO       → subscription yearly only  (3 package: Solo / Growth / Agency)
--   4. FlowCRM Pro     → both (OTF + monthly + yearly, 3 package: Individual / Team / Business)
--
-- Run:
--   docker exec -i twj_db psql -U openpg -d tokowebjaya < scripts/seed_demo_products.sql
-- ============================================================

DO $$
DECLARE
  -- ── Product IDs ──────────────────────────────────────────
  p_novasite   uuid := gen_random_uuid();
  p_datavault  uuid := gen_random_uuid();
  p_rankx      uuid := gen_random_uuid();
  p_flowcrm    uuid := gen_random_uuid();

  -- ── NovaSite packages ────────────────────────────────────
  pkg_nova_personal  uuid := gen_random_uuid();
  pkg_nova_pro       uuid := gen_random_uuid();
  pkg_nova_agency    uuid := gen_random_uuid();

  -- ── DataVault packages ───────────────────────────────────
  pkg_dv_starter     uuid := gen_random_uuid();
  pkg_dv_business    uuid := gen_random_uuid();
  pkg_dv_enterprise  uuid := gen_random_uuid();

  -- ── RankX packages ───────────────────────────────────────
  pkg_rx_solo        uuid := gen_random_uuid();
  pkg_rx_growth      uuid := gen_random_uuid();
  pkg_rx_agency      uuid := gen_random_uuid();

  -- ── FlowCRM packages ─────────────────────────────────────
  pkg_fc_individual  uuid := gen_random_uuid();
  pkg_fc_team        uuid := gen_random_uuid();
  pkg_fc_business    uuid := gen_random_uuid();

  -- ── Limit schema IDs (NovaSite) ──────────────────────────
  ls_nova_pages      uuid := gen_random_uuid();
  ls_nova_domains    uuid := gen_random_uuid();
  ls_nova_storage    uuid := gen_random_uuid();
  ls_nova_support    uuid := gen_random_uuid();

  -- ── Limit schema IDs (DataVault) ─────────────────────────
  ls_dv_storage      uuid := gen_random_uuid();
  ls_dv_devices      uuid := gen_random_uuid();
  ls_dv_history      uuid := gen_random_uuid();
  ls_dv_share        uuid := gen_random_uuid();

  -- ── Limit schema IDs (RankX) ─────────────────────────────
  ls_rx_keywords     uuid := gen_random_uuid();
  ls_rx_projects     uuid := gen_random_uuid();
  ls_rx_users        uuid := gen_random_uuid();
  ls_rx_reports      uuid := gen_random_uuid();

  -- ── Limit schema IDs (FlowCRM) ───────────────────────────
  ls_fc_contacts     uuid := gen_random_uuid();
  ls_fc_pipelines    uuid := gen_random_uuid();
  ls_fc_users        uuid := gen_random_uuid();
  ls_fc_ai           uuid := gen_random_uuid();

BEGIN

-- ============================================================
-- PRODUCT 1 — NovaSite Pro  (pricing_model: one_time)
-- ============================================================
INSERT INTO products (
  id, slug, name_id, name_en,
  short_desc_id, short_desc_en,
  description_id, description_en,
  type, pricing_model, status,
  category, tags, is_featured, sort_order,
  demo_url, contact_whatsapp
) VALUES (
  p_novasite,
  'novasite-pro',
  'NovaSite Pro — Website Builder AI',
  'NovaSite Pro — AI Website Builder',
  'Buat website profesional dalam hitungan menit dengan kekuatan AI. Tanpa coding, tanpa ribet.',
  'Build a professional website in minutes with the power of AI. No coding, no hassle.',
  E'NovaSite Pro adalah website builder berbasis AI generasi terbaru yang memungkinkan siapa pun membuat website kelas dunia tanpa satu baris kode pun.\n\nDengan teknologi AI terdepan, NovaSite Pro menghasilkan desain, konten, dan struktur website secara otomatis hanya dari deskripsi singkat bisnis Anda. Pilih dari 200+ template premium yang dioptimalkan untuk konversi, lalu kustomisasi dengan editor drag-and-drop yang intuitif.\n\n**Mengapa NovaSite Pro?**\n- AI Content Generator: hasilkan teks, headline, dan CTA yang meyakinkan secara otomatis\n- 200+ template premium siap pakai\n- SEO built-in: meta tag, sitemap XML, schema markup otomatis\n- Hosting blazing-fast di CDN global\n- Analitik real-time terintegrasi\n- Formulir, live chat, dan integrasi WhatsApp bawaan\n\nCocok untuk UMKM, freelancer, agensi, dan startup yang ingin hadir online dengan tampilan premium tanpa biaya developer.',
  E'NovaSite Pro is a next-generation AI-powered website builder that lets anyone create a world-class website without a single line of code.\n\nPowered by cutting-edge AI, NovaSite Pro automatically generates design, content, and website structure from just a brief description of your business. Choose from 200+ premium templates optimized for conversion, then customize with an intuitive drag-and-drop editor.\n\n**Why NovaSite Pro?**\n- AI Content Generator: automatically produce compelling copy, headlines, and CTAs\n- 200+ ready-to-use premium templates\n- Built-in SEO: automatic meta tags, XML sitemap, and schema markup\n- Blazing-fast hosting on a global CDN\n- Integrated real-time analytics\n- Built-in forms, live chat, and WhatsApp integration\n\nPerfect for SMBs, freelancers, agencies, and startups who want a premium online presence without developer costs.',
  'software', 'one_time', 'active',
  'Website & Landing Page',
  '["website builder","AI","no-code","landing page","bisnis online","SEO","template"]',
  true, 10,
  'https://demo.novasite.example.com',
  '6281234567890'
);

-- Limit schemas NovaSite (incl. enum for support level)
INSERT INTO product_limit_schemas (id, product_id, key, label_id, label_en, unit, value_type, enum_options, is_unlimited_allowed, sort_order)
VALUES
  (ls_nova_pages,   p_novasite, 'max_pages',    'Jumlah Halaman', 'Number of Pages', 'halaman', 'int',  NULL,                              true,  0),
  (ls_nova_domains, p_novasite, 'max_domains',  'Custom Domain',  'Custom Domains',  'domain',  'int',  NULL,                              false, 1),
  (ls_nova_storage, p_novasite, 'storage_gb',   'Penyimpanan',    'Storage',         'GB',      'int',  NULL,                              true,  2),
  (ls_nova_support, p_novasite, 'support_level','Level Dukungan', 'Support Level',   NULL,      'enum', '["email","priority","dedicated"]', false, 3);

-- NovaSite Packages
INSERT INTO product_packages (id, product_id, code, name_id, name_en, tagline_id, tagline_en, status, sort_order, is_default, is_popular, license_type, max_activations)
VALUES
  (pkg_nova_personal, p_novasite, 'personal', 'Personal', 'Personal', 'Untuk portfolio & bisnis solo',      'For portfolios & solo businesses',   'active', 0, true,  false, 'token', 1),
  (pkg_nova_pro,      p_novasite, 'pro',      'Pro',      'Pro',      'Untuk bisnis yang serius berkembang', 'For businesses serious about growth', 'active', 1, false, true,  'token', 1),
  (pkg_nova_agency,   p_novasite, 'agency',   'Agency',   'Agency',   'Untuk agensi & tim kreatif',          'For agencies & creative teams',       'active', 2, false, false, 'token', 1);

-- NovaSite Prices (one_time only)
INSERT INTO package_prices (package_id, billing_type, amount, is_active)
VALUES
  (pkg_nova_personal, 'one_time', 299000,  true),
  (pkg_nova_pro,      'one_time', 899000,  true),
  (pkg_nova_agency,   'one_time', 2499000, true);

-- NovaSite Features
INSERT INTO package_features (package_id, label_id, label_en, included, sort_order)
VALUES
  -- Personal
  (pkg_nova_personal, 'AI Content Generator',                   'AI Content Generator',                  true,  0),
  (pkg_nova_personal, '50+ Template Premium',                    '50+ Premium Templates',                 true,  1),
  (pkg_nova_personal, 'Editor Drag & Drop',                      'Drag & Drop Editor',                    true,  2),
  (pkg_nova_personal, 'SEO Otomatis (Meta & Sitemap)',           'Auto SEO (Meta & Sitemap)',              true,  3),
  (pkg_nova_personal, 'Hosting CDN Global (1 tahun)',            'Global CDN Hosting (1 year)',            true,  4),
  (pkg_nova_personal, 'Subdomain novasite.app',                  'novasite.app Subdomain',                 true,  5),
  (pkg_nova_personal, 'Custom Domain Sendiri',                   'Custom Domain',                         false, 6),
  (pkg_nova_personal, 'Analitik Real-time',                      'Real-time Analytics',                   false, 7),
  (pkg_nova_personal, 'Hapus Branding NovaSite',                 'Remove NovaSite Branding',              false, 8),
  -- Pro
  (pkg_nova_pro, 'AI Content Generator',                         'AI Content Generator',                  true,  0),
  (pkg_nova_pro, '200+ Template Premium',                        '200+ Premium Templates',                true,  1),
  (pkg_nova_pro, 'Editor Drag & Drop',                           'Drag & Drop Editor',                    true,  2),
  (pkg_nova_pro, 'SEO Otomatis + Schema Markup',                 'Auto SEO + Schema Markup',              true,  3),
  (pkg_nova_pro, 'Hosting CDN Global (lifetime)',                'Global CDN Hosting (lifetime)',          true,  4),
  (pkg_nova_pro, '1 Custom Domain Gratis',                       '1 Free Custom Domain',                  true,  5),
  (pkg_nova_pro, 'Analitik Real-time',                           'Real-time Analytics',                   true,  6),
  (pkg_nova_pro, 'Hapus Branding NovaSite',                      'Remove NovaSite Branding',              true,  7),
  (pkg_nova_pro, 'Integrasi WhatsApp & Live Chat',               'WhatsApp & Live Chat Integration',      true,  8),
  (pkg_nova_pro, 'Multi-bahasa (ID + EN)',                       'Multi-language (ID + EN)',              false,  9),
  -- Agency
  (pkg_nova_agency, 'AI Content Generator (Unlimited)',          'AI Content Generator (Unlimited)',      true,  0),
  (pkg_nova_agency, '200+ Template Premium',                     '200+ Premium Templates',                true,  1),
  (pkg_nova_agency, 'Editor Drag & Drop',                        'Drag & Drop Editor',                    true,  2),
  (pkg_nova_agency, 'SEO Otomatis + Schema Markup',              'Auto SEO + Schema Markup',              true,  3),
  (pkg_nova_agency, 'Hosting CDN Global (lifetime)',             'Global CDN Hosting (lifetime)',          true,  4),
  (pkg_nova_agency, 'Hingga 5 Custom Domain',                    'Up to 5 Custom Domains',                true,  5),
  (pkg_nova_agency, 'Analitik Real-time + Export CSV',           'Real-time Analytics + CSV Export',      true,  6),
  (pkg_nova_agency, 'Hapus Branding NovaSite',                   'Remove NovaSite Branding',              true,  7),
  (pkg_nova_agency, 'Integrasi WhatsApp, Live Chat & CRM',       'WhatsApp, Live Chat & CRM Integration', true,  8),
  (pkg_nova_agency, 'Multi-bahasa (ID + EN + JP)',               'Multi-language (ID + EN + JP)',         true,  9),
  (pkg_nova_agency, 'White-label (nama brand sendiri)',          'White-label (your own brand)',           true, 10),
  (pkg_nova_agency, 'Dedicated Support Manager',                 'Dedicated Support Manager',             true, 11);

-- NovaSite Limits (int columns)
INSERT INTO package_limits (package_id, schema_id, value_int, is_unlimited)
VALUES
  (pkg_nova_personal, ls_nova_pages,   5,    false),
  (pkg_nova_personal, ls_nova_domains, 0,    false),
  (pkg_nova_personal, ls_nova_storage, 5,    false),
  (pkg_nova_pro,      ls_nova_pages,   NULL, true),
  (pkg_nova_pro,      ls_nova_domains, 1,    false),
  (pkg_nova_pro,      ls_nova_storage, 20,   false),
  (pkg_nova_agency,   ls_nova_pages,   NULL, true),
  (pkg_nova_agency,   ls_nova_domains, 5,    false),
  (pkg_nova_agency,   ls_nova_storage, NULL, true);

-- NovaSite Limits (enum/text column — support_level)
INSERT INTO package_limits (package_id, schema_id, value_text, is_unlimited)
VALUES
  (pkg_nova_personal, ls_nova_support, 'email',     false),
  (pkg_nova_pro,      ls_nova_support, 'priority',  false),
  (pkg_nova_agency,   ls_nova_support, 'dedicated', false);


-- ============================================================
-- PRODUCT 2 — DataVault Cloud  (pricing_model: subscription, monthly only)
-- ============================================================
INSERT INTO products (
  id, slug, name_id, name_en,
  short_desc_id, short_desc_en,
  description_id, description_en,
  type, pricing_model, status,
  category, tags, is_featured, sort_order,
  contact_whatsapp
) VALUES (
  p_datavault,
  'datavault-cloud',
  'DataVault Cloud — Backup & Sinkronisasi',
  'DataVault Cloud — Backup & Sync',
  'Lindungi data bisnis Anda dengan backup otomatis, enkripsi end-to-end, dan sinkronisasi real-time ke cloud.',
  'Protect your business data with automated backups, end-to-end encryption, and real-time cloud sync.',
  E'DataVault Cloud adalah solusi penyimpanan dan pencadangan cloud enterprise-grade yang dirancang untuk bisnis Indonesia.\n\nSetiap file yang Anda simpan di DataVault dienkripsi dengan AES-256 sebelum diunggah, sehingga hanya Anda yang bisa mengaksesnya — bahkan kami tidak bisa membacanya. Backup berjalan otomatis di latar belakang tanpa mengganggu pekerjaan Anda.\n\n**Fitur Unggulan:**\n- Backup otomatis setiap 15 menit\n- Enkripsi end-to-end AES-256 (zero-knowledge)\n- Sinkronisasi real-time di semua perangkat\n- Riwayat versi file hingga 365 hari\n- Pemulihan file dengan satu klik\n- Berbagi folder dengan tim dengan kontrol akses granular\n- Aplikasi desktop (Windows/Mac/Linux) & mobile (iOS/Android)\n- Pusat data di Indonesia (compliant PDPA)\n\nData Anda aman, teragregasi, dan selalu bisa dipulihkan kapan pun.',
  E'DataVault Cloud is an enterprise-grade cloud storage and backup solution designed for Indonesian businesses.\n\nEvery file stored in DataVault is encrypted with AES-256 before upload — only you can access it, even we cannot read your data. Backups run automatically in the background without interrupting your work.\n\n**Key Features:**\n- Automatic backup every 15 minutes\n- AES-256 end-to-end encryption (zero-knowledge)\n- Real-time sync across all devices\n- File version history up to 365 days\n- One-click file recovery\n- Folder sharing with granular access controls\n- Desktop apps (Windows/Mac/Linux) & mobile (iOS/Android)\n- Indonesian data center (PDPA compliant)\n\nYour data is secure, aggregated, and always recoverable.',
  'service', 'subscription', 'active',
  'Cloud & Storage',
  '["cloud storage","backup","enkripsi","sinkronisasi","keamanan data","bisnis"]',
  true, 20,
  '6281234567890'
);

-- Limit schemas DataVault
INSERT INTO product_limit_schemas (id, product_id, key, label_id, label_en, unit, value_type, enum_options, is_unlimited_allowed, sort_order)
VALUES
  (ls_dv_storage,  p_datavault, 'storage_gb',     'Kapasitas Penyimpanan', 'Storage Capacity',  'GB',   'int', NULL, true,  0),
  (ls_dv_devices,  p_datavault, 'max_devices',     'Perangkat Terhubung',   'Connected Devices', NULL,  'int', NULL, true,  1),
  (ls_dv_history,  p_datavault, 'version_history', 'Riwayat Versi',         'Version History',   'hari','int', NULL, false, 2),
  (ls_dv_share,    p_datavault, 'shared_users',    'Anggota Tim',           'Team Members',      'user','int', NULL, true,  3);

-- DataVault Packages
INSERT INTO product_packages (id, product_id, code, name_id, name_en, tagline_id, tagline_en, status, sort_order, is_default, is_popular, license_type)
VALUES
  (pkg_dv_starter,    p_datavault, 'starter',    'Starter',    'Starter',    'Untuk freelancer & penggunaan pribadi', 'For freelancers & personal use',        'active', 0, true,  false, 'none'),
  (pkg_dv_business,   p_datavault, 'business',   'Business',   'Business',   'Untuk tim kecil hingga menengah',       'For small to medium teams',             'active', 1, false, true,  'none'),
  (pkg_dv_enterprise, p_datavault, 'enterprise', 'Enterprise', 'Enterprise', 'Untuk organisasi besar dengan SLA',     'For large organizations with SLA',      'active', 2, false, false, 'none');

-- DataVault Prices (monthly only)
INSERT INTO package_prices (package_id, billing_type, amount, is_active)
VALUES
  (pkg_dv_starter,    'monthly', 49000,  true),
  (pkg_dv_business,   'monthly', 199000, true),
  (pkg_dv_enterprise, 'monthly', 599000, true);

-- DataVault Features
INSERT INTO package_features (package_id, label_id, label_en, included, sort_order)
VALUES
  -- Starter
  (pkg_dv_starter, 'Backup Otomatis (setiap jam)',            'Automatic Backup (hourly)',              true,  0),
  (pkg_dv_starter, 'Enkripsi AES-256 End-to-End',             'AES-256 End-to-End Encryption',         true,  1),
  (pkg_dv_starter, 'Aplikasi Desktop & Mobile',               'Desktop & Mobile App',                  true,  2),
  (pkg_dv_starter, 'Riwayat Versi 30 Hari',                   '30-Day Version History',                true,  3),
  (pkg_dv_starter, 'Pemulihan File Satu Klik',                 'One-Click File Recovery',               true,  4),
  (pkg_dv_starter, 'Berbagi Folder dengan Tim',                'Team Folder Sharing',                  false,  5),
  (pkg_dv_starter, 'Admin Dashboard',                          'Admin Dashboard',                      false,  6),
  (pkg_dv_starter, 'SLA 99.9% Uptime',                        'SLA 99.9% Uptime',                     false,  7),
  -- Business
  (pkg_dv_business, 'Backup Otomatis (setiap 15 menit)',      'Automatic Backup (every 15 min)',        true,  0),
  (pkg_dv_business, 'Enkripsi AES-256 End-to-End',            'AES-256 End-to-End Encryption',         true,  1),
  (pkg_dv_business, 'Aplikasi Desktop & Mobile',              'Desktop & Mobile App',                  true,  2),
  (pkg_dv_business, 'Riwayat Versi 180 Hari',                 '180-Day Version History',               true,  3),
  (pkg_dv_business, 'Pemulihan File Satu Klik',               'One-Click File Recovery',               true,  4),
  (pkg_dv_business, 'Berbagi Folder + Kontrol Akses',         'Folder Sharing + Access Controls',      true,  5),
  (pkg_dv_business, 'Admin Dashboard Terpusat',               'Centralized Admin Dashboard',           true,  6),
  (pkg_dv_business, 'SLA 99.9% Uptime',                       'SLA 99.9% Uptime',                     true,  7),
  (pkg_dv_business, 'Prioritas Support (Email & Chat)',        'Priority Support (Email & Chat)',       true,  8),
  (pkg_dv_business, 'Dedicated Account Manager',               'Dedicated Account Manager',            false,  9),
  -- Enterprise
  (pkg_dv_enterprise, 'Backup Otomatis Real-time',            'Real-time Automatic Backup',            true,  0),
  (pkg_dv_enterprise, 'Enkripsi AES-256 End-to-End',          'AES-256 End-to-End Encryption',         true,  1),
  (pkg_dv_enterprise, 'Aplikasi Desktop & Mobile',            'Desktop & Mobile App',                  true,  2),
  (pkg_dv_enterprise, 'Riwayat Versi 365 Hari',               '365-Day Version History',               true,  3),
  (pkg_dv_enterprise, 'Pemulihan File & Folder Massal',        'Bulk File & Folder Recovery',           true,  4),
  (pkg_dv_enterprise, 'Manajemen Tim + Hak Akses Granular',   'Team Management + Granular Permissions', true,  5),
  (pkg_dv_enterprise, 'Admin Dashboard + Audit Log',           'Admin Dashboard + Audit Log',           true,  6),
  (pkg_dv_enterprise, 'SLA 99.99% Uptime Tertulis',           'Written SLA 99.99% Uptime',             true,  7),
  (pkg_dv_enterprise, 'Dedicated Account Manager',             'Dedicated Account Manager',             true,  8),
  (pkg_dv_enterprise, 'Integrasi SSO & Active Directory',      'SSO & Active Directory Integration',    true,  9),
  (pkg_dv_enterprise, 'Data Residency Indonesia',              'Indonesian Data Residency',             true, 10);

-- DataVault Limits
INSERT INTO package_limits (package_id, schema_id, value_int, is_unlimited)
VALUES
  (pkg_dv_starter,    ls_dv_storage,  100,  false),
  (pkg_dv_starter,    ls_dv_devices,  3,    false),
  (pkg_dv_starter,    ls_dv_history,  30,   false),
  (pkg_dv_starter,    ls_dv_share,    1,    false),
  (pkg_dv_business,   ls_dv_storage,  1000, false),
  (pkg_dv_business,   ls_dv_devices,  25,   false),
  (pkg_dv_business,   ls_dv_history,  180,  false),
  (pkg_dv_business,   ls_dv_share,    20,   false),
  (pkg_dv_enterprise, ls_dv_storage,  NULL, true),
  (pkg_dv_enterprise, ls_dv_devices,  NULL, true),
  (pkg_dv_enterprise, ls_dv_history,  365,  false),
  (pkg_dv_enterprise, ls_dv_share,    NULL, true);


-- ============================================================
-- PRODUCT 3 — RankX SEO  (pricing_model: subscription, yearly only)
-- ============================================================
INSERT INTO products (
  id, slug, name_id, name_en,
  short_desc_id, short_desc_en,
  description_id, description_en,
  type, pricing_model, status,
  category, tags, is_featured, sort_order,
  demo_url, contact_whatsapp
) VALUES (
  p_rankx,
  'rankx-seo',
  'RankX SEO — Platform Analitik SEO Profesional',
  'RankX SEO — Professional SEO Analytics Platform',
  'Pantau peringkat keyword, audit website, dan kalahkan kompetitor dengan data SEO real-time.',
  'Track keyword rankings, audit your website, and outrank competitors with real-time SEO data.',
  E'RankX SEO adalah platform analitik SEO all-in-one yang memberikan visibilitas penuh atas performa pencarian organik bisnis Anda.\n\nDari pemantauan peringkat keyword harian hingga audit teknis mendalam, RankX mengumpulkan semua data yang Anda butuhkan dalam satu dashboard yang elegan. Tidak perlu lagi berpindah-pindah antara berbagai tool.\n\n**Apa yang Anda Dapatkan:**\n- Rank Tracker: pantau ribuan keyword di Google, Bing, dan Yahoo secara harian\n- Site Audit: scan 200+ faktor SEO teknis dan dapatkan rekomendasi actionable\n- Competitor Analysis: lacak backlink dan strategi konten pesaing\n- Backlink Monitor: notifikasi real-time saat backlink baru ditemukan atau hilang\n- Content Optimizer: skor konten berbasis NLP untuk meningkatkan relevansi\n- Laporan otomatis PDF/CSV untuk klien (cocok untuk agensi)\n- API akses untuk integrasi dengan tool lain\n\nDipakai oleh 5.000+ marketer dan agensi digital di Asia Tenggara.',
  E'RankX SEO is an all-in-one SEO analytics platform giving you full visibility into your business organic search performance.\n\nFrom daily keyword rank tracking to deep technical audits, RankX aggregates all the data you need in one elegant dashboard. No more switching between multiple tools.\n\n**What You Get:**\n- Rank Tracker: monitor thousands of keywords on Google, Bing, and Yahoo daily\n- Site Audit: scan 200+ technical SEO factors and get actionable recommendations\n- Competitor Analysis: track competitor backlinks and content strategies\n- Backlink Monitor: real-time notifications for new or lost backlinks\n- Content Optimizer: NLP-based content scoring to improve relevance\n- Automated PDF/CSV reports for clients (ideal for agencies)\n- API access for integration with other tools\n\nUsed by 5,000+ marketers and digital agencies across Southeast Asia.',
  'software', 'subscription', 'active',
  'Marketing & SEO',
  '["SEO","keyword tracking","audit","backlink","competitor analysis","marketing","agensi"]',
  false, 30,
  'https://demo.rankx.example.com',
  '6281234567890'
);

-- Limit schemas RankX
INSERT INTO product_limit_schemas (id, product_id, key, label_id, label_en, unit, value_type, enum_options, is_unlimited_allowed, sort_order)
VALUES
  (ls_rx_keywords, p_rankx, 'max_keywords',  'Keyword Terlacak',  'Tracked Keywords',    'keyword', 'int', NULL, true,  0),
  (ls_rx_projects, p_rankx, 'max_projects',  'Proyek / Website',  'Projects / Websites', NULL,      'int', NULL, true,  1),
  (ls_rx_users,    p_rankx, 'max_users',     'Pengguna Akun',     'Account Users',       'user',    'int', NULL, false, 2),
  (ls_rx_reports,  p_rankx, 'reports_month', 'Laporan per Bulan', 'Reports per Month',   NULL,      'int', NULL, true,  3);

-- RankX Packages
INSERT INTO product_packages (id, product_id, code, name_id, name_en, tagline_id, tagline_en, status, sort_order, is_default, is_popular, license_type)
VALUES
  (pkg_rx_solo,   p_rankx, 'solo',   'Solo',   'Solo',   'Untuk blogger & pemilik bisnis solo',            'For bloggers & solo business owners',        'active', 0, true,  false, 'none'),
  (pkg_rx_growth, p_rankx, 'growth', 'Growth', 'Growth', 'Untuk tim marketing yang ambisius',              'For ambitious marketing teams',              'active', 1, false, true,  'none'),
  (pkg_rx_agency, p_rankx, 'agency', 'Agency', 'Agency', 'Untuk agensi SEO yang mengelola banyak klien',  'For SEO agencies managing many clients',      'active', 2, false, false, 'none');

-- RankX Prices (yearly only)
INSERT INTO package_prices (package_id, billing_type, amount, is_active)
VALUES
  (pkg_rx_solo,   'yearly', 999000,  true),
  (pkg_rx_growth, 'yearly', 2999000, true),
  (pkg_rx_agency, 'yearly', 7999000, true);

-- RankX Features
INSERT INTO package_features (package_id, label_id, label_en, included, sort_order)
VALUES
  -- Solo
  (pkg_rx_solo, 'Rank Tracker Harian',                  'Daily Rank Tracker',                  true,  0),
  (pkg_rx_solo, 'Site Audit (200+ faktor)',              'Site Audit (200+ factors)',            true,  1),
  (pkg_rx_solo, 'Backlink Monitor',                      'Backlink Monitor',                    true,  2),
  (pkg_rx_solo, 'Content Optimizer',                     'Content Optimizer',                   true,  3),
  (pkg_rx_solo, 'Dashboard Analytics',                   'Analytics Dashboard',                 true,  4),
  (pkg_rx_solo, 'Competitor Analysis',                   'Competitor Analysis',                 false, 5),
  (pkg_rx_solo, 'Laporan PDF Otomatis',                  'Automated PDF Reports',               false, 6),
  (pkg_rx_solo, 'API Access',                            'API Access',                          false, 7),
  (pkg_rx_solo, 'White-label Reports',                   'White-label Reports',                 false, 8),
  -- Growth
  (pkg_rx_growth, 'Rank Tracker Harian',                 'Daily Rank Tracker',                  true,  0),
  (pkg_rx_growth, 'Site Audit (200+ faktor)',             'Site Audit (200+ factors)',            true,  1),
  (pkg_rx_growth, 'Backlink Monitor Real-time',           'Real-time Backlink Monitor',           true,  2),
  (pkg_rx_growth, 'Content Optimizer + NLP',              'Content Optimizer + NLP',             true,  3),
  (pkg_rx_growth, 'Dashboard Analytics Lanjutan',         'Advanced Analytics Dashboard',        true,  4),
  (pkg_rx_growth, 'Competitor Analysis (5 kompetitor)',   'Competitor Analysis (5 competitors)', true,  5),
  (pkg_rx_growth, 'Laporan PDF Branded Otomatis',         'Automated Branded PDF Reports',       true,  6),
  (pkg_rx_growth, 'Notifikasi Email & Slack',             'Email & Slack Notifications',         true,  7),
  (pkg_rx_growth, 'API Access',                           'API Access',                          false, 8),
  (pkg_rx_growth, 'White-label Reports',                  'White-label Reports',                 false, 9),
  -- Agency
  (pkg_rx_agency, 'Rank Tracker Harian (multi-lokasi)',           'Daily Rank Tracker (multi-location)',           true,  0),
  (pkg_rx_agency, 'Site Audit + Jadwal Otomatis',                 'Site Audit + Auto Schedule',                    true,  1),
  (pkg_rx_agency, 'Backlink Monitor Real-time',                    'Real-time Backlink Monitor',                    true,  2),
  (pkg_rx_agency, 'Content Optimizer + NLP + AI Writing Assist',  'Content Optimizer + NLP + AI Writing Assist',  true,  3),
  (pkg_rx_agency, 'Dashboard Analytics + Custom Widget',           'Analytics Dashboard + Custom Widgets',         true,  4),
  (pkg_rx_agency, 'Competitor Analysis (unlimited)',               'Competitor Analysis (unlimited)',               true,  5),
  (pkg_rx_agency, 'Laporan PDF White-label Otomatis',              'Automated White-label PDF Reports',             true,  6),
  (pkg_rx_agency, 'Notifikasi Email, Slack & WhatsApp',            'Email, Slack & WhatsApp Notifications',        true,  7),
  (pkg_rx_agency, 'Full API Access + Webhook',                     'Full API Access + Webhooks',                   true,  8),
  (pkg_rx_agency, 'Client Portal (akses terbatas untuk klien)',    'Client Portal (limited client access)',         true,  9),
  (pkg_rx_agency, 'Priority Support + Dedicated CSM',              'Priority Support + Dedicated CSM',             true, 10);

-- RankX Limits
INSERT INTO package_limits (package_id, schema_id, value_int, is_unlimited)
VALUES
  (pkg_rx_solo,   ls_rx_keywords,  500,  false),
  (pkg_rx_solo,   ls_rx_projects,  3,    false),
  (pkg_rx_solo,   ls_rx_users,     1,    false),
  (pkg_rx_solo,   ls_rx_reports,   5,    false),
  (pkg_rx_growth, ls_rx_keywords,  5000, false),
  (pkg_rx_growth, ls_rx_projects,  15,   false),
  (pkg_rx_growth, ls_rx_users,     5,    false),
  (pkg_rx_growth, ls_rx_reports,   NULL, true),
  (pkg_rx_agency, ls_rx_keywords,  NULL, true),
  (pkg_rx_agency, ls_rx_projects,  NULL, true),
  (pkg_rx_agency, ls_rx_users,     20,   false),
  (pkg_rx_agency, ls_rx_reports,   NULL, true);


-- ============================================================
-- PRODUCT 4 — FlowCRM Pro  (pricing_model: both — OTF + monthly + yearly)
-- ============================================================
INSERT INTO products (
  id, slug, name_id, name_en,
  short_desc_id, short_desc_en,
  description_id, description_en,
  type, pricing_model, status,
  category, tags, is_featured, sort_order,
  demo_url, contact_whatsapp
) VALUES (
  p_flowcrm,
  'flowcrm-pro',
  'FlowCRM Pro — CRM Bertenaga AI untuk Tim Sales',
  'FlowCRM Pro — AI-Powered CRM for Sales Teams',
  'Kelola pipeline, otomasi follow-up, dan tutup lebih banyak deal dengan CRM yang belajar dari pola penjualan Anda.',
  'Manage pipelines, automate follow-ups, and close more deals with a CRM that learns from your sales patterns.',
  E'FlowCRM Pro adalah customer relationship management (CRM) generasi terbaru yang menggabungkan kecerdasan buatan dengan kesederhanaan desain untuk membantu tim sales Anda bekerja lebih cerdas, bukan lebih keras.\n\nBerbeda dengan CRM konvensional yang membutuhkan setup berminggu-minggu, FlowCRM siap digunakan dalam 30 menit. AI built-in FlowCRM menganalisis pola historis penjualan Anda dan secara proaktif merekomendasikan: kapan follow-up, kontak mana yang paling siap menutup deal, dan apa yang harus dikatakan.\n\n**Fitur Utama:**\n- Visual Pipeline Kanban: drag-and-drop deal antar stage dengan mudah\n- AI Lead Scoring: skor otomatis untuk setiap lead berdasarkan perilaku & engagement\n- Automasi Follow-up: kirim email/WhatsApp otomatis pada waktu yang tepat\n- Unified Inbox: semua komunikasi (email, WhatsApp, telepon) dalam satu tempat\n- Laporan & Forecast: prediksi revenue bulanan dengan akurasi tinggi\n- Template Email & Proposal: hemat waktu dengan template yang bisa dikustomisasi\n- Integrasi: Google Workspace, Outlook, Shopee, Tokopedia, Slack, Zapier\n- Mobile App: iOS & Android\n\nDipakai lebih dari 3.000 tim sales di Indonesia.',
  E'FlowCRM Pro is a next-generation CRM that combines artificial intelligence with design simplicity to help your sales team work smarter, not harder.\n\nUnlike conventional CRMs that require weeks of setup, FlowCRM is ready to use in 30 minutes. FlowCRM''s built-in AI analyzes your historical sales patterns and proactively recommends: when to follow up, which contacts are most likely to close, and what to say.\n\n**Key Features:**\n- Visual Kanban Pipeline: drag-and-drop deals between stages effortlessly\n- AI Lead Scoring: automatic scoring for every lead based on behavior & engagement\n- Follow-up Automation: send emails/WhatsApp automatically at the right time\n- Unified Inbox: all communications (email, WhatsApp, calls) in one place\n- Reports & Forecast: predict monthly revenue with high accuracy\n- Email & Proposal Templates: save time with customizable templates\n- Integrations: Google Workspace, Outlook, Shopee, Tokopedia, Slack, Zapier\n- Mobile App: iOS & Android\n\nUsed by more than 3,000 sales teams in Indonesia.',
  'software', 'both', 'active',
  'CRM & Sales',
  '["CRM","sales","pipeline","AI","otomasi","follow-up","lead scoring","bisnis"]',
  true, 5,
  'https://demo.flowcrm.example.com',
  '6281234567890'
);

-- Limit schemas FlowCRM
INSERT INTO product_limit_schemas (id, product_id, key, label_id, label_en, unit, value_type, enum_options, is_unlimited_allowed, sort_order)
VALUES
  (ls_fc_contacts,  p_flowcrm, 'max_contacts',  'Jumlah Kontak',    'Number of Contacts', 'kontak', 'int', NULL, true,  0),
  (ls_fc_pipelines, p_flowcrm, 'max_pipelines', 'Pipeline Sales',   'Sales Pipelines',    NULL,     'int', NULL, true,  1),
  (ls_fc_users,     p_flowcrm, 'max_users',     'Pengguna / Seat',  'Users / Seats',      'user',   'int', NULL, false, 2),
  (ls_fc_ai,        p_flowcrm, 'ai_credits',    'AI Credits/Bulan', 'AI Credits/Month',   NULL,     'int', NULL, true,  3);

-- FlowCRM Packages
INSERT INTO product_packages (id, product_id, code, name_id, name_en, tagline_id, tagline_en, status, sort_order, is_default, is_popular, license_type)
VALUES
  (pkg_fc_individual, p_flowcrm, 'individual', 'Individual', 'Individual', 'Untuk sales solo & freelancer',            'For solo sales & freelancers',              'active', 0, true,  false, 'none'),
  (pkg_fc_team,       p_flowcrm, 'team',       'Team',       'Team',       'Untuk tim sales kecil yang ingin tumbuh',  'For small sales teams ready to grow',       'active', 1, false, true,  'none'),
  (pkg_fc_business,   p_flowcrm, 'business',   'Business',   'Business',   'Untuk perusahaan dengan tim sales besar',  'For companies with large sales teams',      'active', 2, false, false, 'none');

-- FlowCRM Prices (one_time + monthly + yearly)
-- Individual: beli sekali atau berlangganan (yearly ≈ hemat 2 bulan vs monthly)
-- Team & Business: yearly ≈ hemat ~2 bulan
INSERT INTO package_prices (package_id, billing_type, amount, is_active)
VALUES
  (pkg_fc_individual, 'one_time', 799000,  true),
  (pkg_fc_individual, 'monthly',  99000,   true),
  (pkg_fc_individual, 'yearly',   899000,  true),
  (pkg_fc_team,       'one_time', 2499000, true),
  (pkg_fc_team,       'monthly',  299000,  true),
  (pkg_fc_team,       'yearly',   2799000, true),
  (pkg_fc_business,   'one_time', 5999000, true),
  (pkg_fc_business,   'monthly',  699000,  true),
  (pkg_fc_business,   'yearly',   6599000, true);

-- FlowCRM Features
INSERT INTO package_features (package_id, label_id, label_en, included, sort_order)
VALUES
  -- Individual
  (pkg_fc_individual, 'Visual Pipeline Kanban',               'Visual Kanban Pipeline',               true,  0),
  (pkg_fc_individual, 'Manajemen Kontak & Company',           'Contact & Company Management',         true,  1),
  (pkg_fc_individual, 'Email Tracking & Template',            'Email Tracking & Templates',           true,  2),
  (pkg_fc_individual, 'Kalender & Reminder Otomatis',         'Calendar & Automatic Reminders',       true,  3),
  (pkg_fc_individual, 'Mobile App (iOS & Android)',           'Mobile App (iOS & Android)',           true,  4),
  (pkg_fc_individual, 'AI Lead Scoring',                      'AI Lead Scoring',                      true,  5),
  (pkg_fc_individual, 'Laporan Dasar',                        'Basic Reports',                        true,  6),
  (pkg_fc_individual, 'Automasi Follow-up',                   'Follow-up Automation',                 false, 7),
  (pkg_fc_individual, 'Unified Inbox (Email + WA)',           'Unified Inbox (Email + WA)',           false, 8),
  (pkg_fc_individual, 'Revenue Forecast AI',                  'AI Revenue Forecast',                  false, 9),
  (pkg_fc_individual, 'Integrasi Slack & Zapier',             'Slack & Zapier Integration',           false, 10),
  -- Team
  (pkg_fc_team, 'Visual Pipeline Kanban (unlimited)',         'Visual Kanban Pipeline (unlimited)',   true,  0),
  (pkg_fc_team, 'Manajemen Kontak & Company',                 'Contact & Company Management',         true,  1),
  (pkg_fc_team, 'Email Tracking & Template',                  'Email Tracking & Templates',           true,  2),
  (pkg_fc_team, 'Kalender & Reminder Otomatis',               'Calendar & Automatic Reminders',       true,  3),
  (pkg_fc_team, 'Mobile App (iOS & Android)',                 'Mobile App (iOS & Android)',           true,  4),
  (pkg_fc_team, 'AI Lead Scoring + Prioritas Otomatis',       'AI Lead Scoring + Auto Prioritization',true,  5),
  (pkg_fc_team, 'Laporan & Dashboard Tim',                    'Team Reports & Dashboard',             true,  6),
  (pkg_fc_team, 'Automasi Follow-up (Email & WhatsApp)',      'Follow-up Automation (Email & WA)',    true,  7),
  (pkg_fc_team, 'Unified Inbox (Email + WA + Telepon)',       'Unified Inbox (Email + WA + Phone)',   true,  8),
  (pkg_fc_team, 'Revenue Forecast AI',                        'AI Revenue Forecast',                  true,  9),
  (pkg_fc_team, 'Integrasi Slack & Zapier',                   'Slack & Zapier Integration',           true,  10),
  (pkg_fc_team, 'Role & Permission Per User',                 'Per-User Role & Permissions',          true,  11),
  (pkg_fc_team, 'Integrasi Shopee & Tokopedia',               'Shopee & Tokopedia Integration',       false, 12),
  (pkg_fc_team, 'Custom Field & Form',                        'Custom Fields & Forms',                false, 13),
  -- Business
  (pkg_fc_business, 'Visual Pipeline Kanban (unlimited)',             'Visual Kanban Pipeline (unlimited)',            true,  0),
  (pkg_fc_business, 'Manajemen Kontak & Company',                     'Contact & Company Management',                  true,  1),
  (pkg_fc_business, 'Email Tracking & Template',                      'Email Tracking & Templates',                    true,  2),
  (pkg_fc_business, 'Kalender & Reminder Otomatis',                   'Calendar & Automatic Reminders',                true,  3),
  (pkg_fc_business, 'Mobile App (iOS & Android)',                     'Mobile App (iOS & Android)',                    true,  4),
  (pkg_fc_business, 'AI Lead Scoring + Prioritas + Next Action',      'AI Lead Scoring + Priority + Next Action',      true,  5),
  (pkg_fc_business, 'Laporan, Dashboard & Executive Summary',         'Reports, Dashboard & Executive Summary',         true,  6),
  (pkg_fc_business, 'Automasi Lanjutan (multi-step workflow)',         'Advanced Automation (multi-step workflow)',      true,  7),
  (pkg_fc_business, 'Unified Inbox + Perekaman Panggilan',            'Unified Inbox + Call Recording',                true,  8),
  (pkg_fc_business, 'Revenue Forecast AI + Anomaly Detection',        'AI Revenue Forecast + Anomaly Detection',       true,  9),
  (pkg_fc_business, 'Integrasi Full (Slack, Zapier, API)',            'Full Integrations (Slack, Zapier, API)',         true,  10),
  (pkg_fc_business, 'Role & Permission + Team Hierarchy',             'Role & Permission + Team Hierarchy',             true,  11),
  (pkg_fc_business, 'Integrasi Shopee, Tokopedia & Marketplace lain', 'Shopee, Tokopedia & Other Marketplace Integration', true, 12),
  (pkg_fc_business, 'Custom Field, Form & Workflow Builder',          'Custom Fields, Forms & Workflow Builder',        true,  13),
  (pkg_fc_business, 'SSO & Active Directory',                         'SSO & Active Directory',                        true,  14),
  (pkg_fc_business, 'Dedicated Onboarding & Support',                 'Dedicated Onboarding & Support',                true,  15);

-- FlowCRM Limits
INSERT INTO package_limits (package_id, schema_id, value_int, is_unlimited)
VALUES
  (pkg_fc_individual, ls_fc_contacts,  2500,  false),
  (pkg_fc_individual, ls_fc_pipelines, 2,     false),
  (pkg_fc_individual, ls_fc_users,     1,     false),
  (pkg_fc_individual, ls_fc_ai,        100,   false),
  (pkg_fc_team,       ls_fc_contacts,  25000, false),
  (pkg_fc_team,       ls_fc_pipelines, 10,    false),
  (pkg_fc_team,       ls_fc_users,     10,    false),
  (pkg_fc_team,       ls_fc_ai,        1000,  false),
  (pkg_fc_business,   ls_fc_contacts,  NULL,  true),
  (pkg_fc_business,   ls_fc_pipelines, NULL,  true),
  (pkg_fc_business,   ls_fc_users,     50,    false),
  (pkg_fc_business,   ls_fc_ai,        NULL,  true);

END $$;
