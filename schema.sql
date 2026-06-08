-- schema.sql
-- Core Banking & CMS Database Schema (SQLite / PostgreSQL compatible)

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin', 'user')),
    full_name TEXT DEFAULT '',
    email TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    balance REAL NOT NULL DEFAULT 0.0 CHECK(balance >= 0),
    account_number TEXT UNIQUE NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('deposit', 'withdrawal', 'transfer', 'adjustment')),
    amount REAL NOT NULL,
    description TEXT DEFAULT '',
    counterparty_account_id INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    admin_note TEXT DEFAULT '',
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (counterparty_account_id) REFERENCES accounts(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS site_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT UNIQUE NOT NULL,
    setting_value TEXT NOT NULL
);

-- Default CMS values (will be inserted by app on first run if missing)
INSERT OR IGNORE INTO site_settings (setting_key, setting_value) VALUES
    ('header_title', 'Nexus Financial'),
    ('header_subtitle', 'Tomorrow''s Banking, Today'),
    ('footer_text', '© 2026 Nexus Financial. All rights reserved.'),
    ('logo_url', 'https://via.placeholder.com/150x50?text=Nexus'),
    ('hero_image_url', 'https://via.placeholder.com/1920x600?text=Futuristic+Banking'),
    ('primary_color', '#00F0FF'),
    ('secondary_color', '#FF00C8'),
    ('background_color', '#0A0E27'),
    ('glass_bg', 'rgba(10,14,39,0.75)'),
    ('text_color', '#FFFFFF'),
    ('muted_text', '#A0AEC0'),
    ('chart_color_1', '#00F0FF'),
    ('chart_color_2', '#FF00C8'),
    ('font_family', '"Inter", "Segoe UI", sans-serif');