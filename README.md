# 🏦 Futuristic Core Banking & CMS Platform

A complete, production-ready prototype for a futuristic core banking and financial simulation platform.  
**Fully dynamic frontend** – every text, colour, logo, and image is controlled by an admin CMS.  
Deploy to an Ubuntu server with a single command.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Flask](https://img.shields.io/badge/flask-2.0%2B-lightgrey)

---

## ✨ Features

### 🔐 Secure & Controlled Access
- **No public sign-up** – users are created exclusively by an admin.
- **Argon2 password hashing** and secure session management.
- **Role-based routing** – admins and users see completely different interfaces.

### 🎛️ Admin Control Center (`/admin`)
- **User provisioning** – create users, generate initial passwords, assign accounts.
- **Ledger manipulation** – view all accounts, manually set balances, inject, edit, or delete transactions with full audit trail.
- **Full-site CMS** – change every text string, header, footer, logo URL, colour palette (HEX codes), and hero images dynamically, stored in the database. All frontend components react instantly.

### 👤 User Dashboard (`/dashboard`)
- **Futuristic sci-fi UI** – glassmorphism, neon accents, dark mode default.
- **Live balance display** and account number.
- **Interactive financial chart** (Chart.js) plotting transaction history.
- **Uneditable transaction log** with deposit/withdrawal badges.
- **Profile view** showing name, email, and membership date.

### 🚀 Production‑Ready Deployment
- One‑click install for **Ubuntu 20.04/24.04**.
- **Nginx reverse proxy** with automatic **Let’s Encrypt SSL** (certbot).
- **Systemd service** for automatic startup and crash recovery.
- **SQLite** for prototyping (swap to PostgreSQL by changing one connection string).

---

## 📦 Quick Install (Ubuntu 20.04/24.04)

Run the following commands one after the other on a fresh Ubuntu server **as root or with sudo**:

# 1. Download the installation script 

```bash
curl -O [https://raw.githubusercontent.com/TheTechSavant/futuristic-core-bank/main/install.sh](https://raw.githubusercontent.com/TheTechSavant/futuristic-core-bank/main/install.sh)
```

# 2. Run the script (you will be prompted for your domain and email)

```bash

sudo bash install.sh
```