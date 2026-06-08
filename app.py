#!/usr/bin/env python3
"""
Futuristic Core Banking & CMS Platform
Run with: python app.py
"""

import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, g)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from argon2 import PasswordHasher
import secrets

# ---------- App Setup ----------
app = Flask(__name__)
# UPGRADE: Generating a random key on every startup destroys active user sessions 
# whenever the systemd service restarts. Allow it to pull from the environment.
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Database path
DATABASE = os.environ.get('DB_PATH', 'core_bank.db')

# Argon2 hasher (modern)
ph = PasswordHasher()

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

# ---------- Database Helpers ----------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Create tables and seed default settings."""
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.executescript(f.read())
        db.commit()

# ---------- Auth & User Loader ----------
class User:
    def __init__(self, row):
        self.id = row['id']
        self.username = row['username']
        self.password_hash = row['password_hash']
        self.role = row['role']
        self.full_name = row['full_name']
        self.email = row['email']

    def is_authenticated(self):
        return True
    def is_active(self):
        return True
    def is_anonymous(self):
        return False
    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row:
        return User(row)
    return None

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated

# ---------- CMS Context Processor (makes settings available to all templates) ----------
@app.context_processor
def inject_cms():
    db = get_db()
    settings = {}
    for row in db.execute("SELECT setting_key, setting_value FROM site_settings").fetchall():
        settings[row['setting_key']] = row['setting_value']
    return dict(cms=settings)

# ---------- Pages ----------
@app.route('/')
def index():
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Only users (not admins) see the dashboard; admins go to admin panel
    if current_user.role == 'admin':
        return redirect(url_for('admin_panel'))
    return render_template('dashboard.html')

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    return render_template('admin.html')

# ---------- Auth API ----------
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400
    username = data.get('username', '').strip()
    password = data.get('password', '')

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        return jsonify({"error": "Invalid credentials"}), 401

    # Verify password with Argon2
    try:
        ph.verify(row['password_hash'], password)
        # Optionally rehash if needed
        if ph.check_needs_rehash(row['password_hash']):
            new_hash = ph.hash(password)
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, row['id']))
            db.commit()
    except Exception:
        return jsonify({"error": "Invalid credentials"}), 401

    user = User(row)
    login_user(user)
    return jsonify({"success": True, "role": user.role})

@app.route('/api/logout')
@login_required
def api_logout():
    logout_user()
    return jsonify({"success": True})

# ---------- Admin User Provisioning ----------
@app.route('/api/admin/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    db = get_db()
    users = db.execute("""
        SELECT u.id, u.username, u.role, u.full_name, u.email, a.balance, a.account_number
        FROM users u
        LEFT JOIN accounts a ON a.user_id = u.id
        ORDER BY u.id
    """).fetchall()
    return jsonify([dict(row) for row in users])

@app.route('/api/admin/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    db = get_db()
    # Check uniqueness
    if db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
        return jsonify({"error": "Username already exists"}), 400

    hashed = ph.hash(password)
    try:
        db.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'user')",
                   (username, hashed))
        user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        # Create an account with a generated account number
        acc_num = f"NX-{secrets.token_hex(4).upper()}"
        db.execute("INSERT INTO accounts (user_id, balance, account_number) VALUES (?, 0.0, ?)",
                   (user_id, acc_num))
        db.commit()
        return jsonify({"success": True, "user_id": user_id, "account_number": acc_num})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------- Ledger & Account Control ----------
@app.route('/api/admin/users/<int:user_id>/balance', methods=['PUT'])
@login_required
@admin_required
def update_balance(user_id):
    data = request.get_json()
    new_balance = data.get('balance')
    if new_balance is None or new_balance < 0:
        return jsonify({"error": "Invalid balance"}), 400

    db = get_db()
    # Get account
    account = db.execute("SELECT id FROM accounts WHERE user_id = ?", (user_id,)).fetchone()
    if not account:
        return jsonify({"error": "Account not found"}), 404

    old_balance = account['balance'] if 'balance' in account.keys() else 0.0
    try:
        db.execute("UPDATE accounts SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        # Record adjustment transaction
        db.execute("INSERT INTO transactions (account_id, type, amount, description, admin_note) VALUES (?, 'adjustment', ?, 'Admin manual balance adjustment', 'Manual override')",
                   (account['id'], new_balance - old_balance))
        db.commit()
        return jsonify({"success": True, "new_balance": new_balance})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/users/<int:user_id>/transactions', methods=['GET'])
@login_required
@admin_required
def user_transactions(user_id):
    db = get_db()
    account = db.execute("SELECT id FROM accounts WHERE user_id = ?", (user_id,)).fetchone()
    if not account:
        return jsonify({"error": "Account not found"}), 404

    txns = db.execute("""
        SELECT t.id, t.type, t.amount, t.description, t.timestamp, t.counterparty_account_id, t.admin_note
        FROM transactions t
        WHERE t.account_id = ?
        ORDER BY t.timestamp DESC
    """, (account['id'],)).fetchall()
    return jsonify([dict(row) for row in txns])

@app.route('/api/admin/users/<int:user_id>/transactions', methods=['POST'])
@login_required
@admin_required
def inject_transaction(user_id):
    data = request.get_json()
    # Validate fields
    required = ['type', 'amount', 'description']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400
    txn_type = data['type']
    if txn_type not in ('deposit', 'withdrawal', 'transfer'):
        return jsonify({"error": "Invalid type"}), 400
    try:
        amount = float(data['amount'])
    except (ValueError, TypeError):
        return jsonify({"error": "Amount must be numeric"}), 400

    db = get_db()
    account = db.execute("SELECT id, balance FROM accounts WHERE user_id = ?", (user_id,)).fetchone()
    if not account:
        return jsonify({"error": "Account not found"}), 404

    # For transfer, counterparty required
    counterparty_id = data.get('counterparty_account_id')
    if txn_type == 'transfer' and not counterparty_id:
        return jsonify({"error": "Transfer requires counterparty_account_id"}), 400

    try:
        # Insert transaction (admin can do anything)
        db.execute("""
            INSERT INTO transactions (account_id, type, amount, description, counterparty_account_id, admin_note)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (account['id'], txn_type, amount, data['description'], counterparty_id, data.get('admin_note', '')))
        # Optionally update balance (admin decides if balance reflects the transaction)
        # For simulation, we update balance only if forced? We'll update based on type.
        if txn_type == 'deposit':
            db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, account['id']))
        elif txn_type == 'withdrawal':
            db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, account['id']))
        elif txn_type == 'transfer':
            # Deduct from sender, add to receiver
            db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, account['id']))
            if counterparty_id:
                db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, counterparty_id))
        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/users/<int:user_id>/transactions/<int:txn_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_transaction(user_id, txn_id):
    db = get_db()
    account = db.execute("SELECT id FROM accounts WHERE user_id = ?", (user_id,)).fetchone()
    if not account:
        return jsonify({"error": "Account not found"}), 404
    # Delete transaction (admin may also reverse balance effect, simplified here)
    db.execute("DELETE FROM transactions WHERE id = ? AND account_id = ?", (txn_id, account['id']))
    db.commit()
    return jsonify({"success": True})

# ---------- CMS Settings API ----------
@app.route('/api/admin/settings', methods=['GET'])
@login_required
@admin_required
def get_settings():
    db = get_db()
    rows = db.execute("SELECT setting_key, setting_value FROM site_settings").fetchall()
    return jsonify({row['setting_key']: row['setting_value'] for row in rows})

@app.route('/api/admin/settings', methods=['POST'])
@login_required
@admin_required
def update_settings():
    data = request.get_json()
    db = get_db()
    for key, value in data.items():
        # Validate key exists? We'll upsert.
        db.execute("""
            INSERT INTO site_settings (setting_key, setting_value)
            VALUES (?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
        """, (key, str(value)))
    db.commit()
    # Force reload of CMS for all users (simple, in-memory dict gets refreshed on next request)
    return jsonify({"success": True})

# ---------- User Frontend API (read-only, secure) ----------
@app.route('/api/user/profile')
@login_required
def user_profile():
    db = get_db()
    row = db.execute("SELECT id, username, full_name, email, created_at FROM users WHERE id = ?",
                     (current_user.id,)).fetchone()
    if not row:
        return jsonify({"error": "User not found"}), 404
    return jsonify(dict(row))

@app.route('/api/user/balance')
@login_required
def user_balance():
    db = get_db()
    acc = db.execute("SELECT balance, account_number FROM accounts WHERE user_id = ?",
                     (current_user.id,)).fetchone()
    if not acc:
        return jsonify({"error": "Account not found"}), 404
    return jsonify({"balance": acc['balance'], "account_number": acc['account_number']})

@app.route('/api/user/transactions')
@login_required
def user_transaction_history():
    db = get_db()
    acc = db.execute("SELECT id FROM accounts WHERE user_id = ?", (current_user.id,)).fetchone()
    if not acc:
        return jsonify([])
    txns = db.execute("""
        SELECT type, amount, description, timestamp
        FROM transactions
        WHERE account_id = ?
        ORDER BY timestamp DESC
        LIMIT 100
    """, (acc['id'],)).fetchall()
    return jsonify([dict(row) for row in txns])

# ---------- Main ----------
if __name__ == '__main__':
    # Initialize database if not exists
    if not os.path.exists(DATABASE):
        init_db()
        # Create default admin user (admin / admin123) only on first run
        with app.app_context():
            db = get_db()
            admin_hash = ph.hash("admin123")
            db.execute("INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, 'admin', 'System Admin')",
                       ("admin", admin_hash))
            db.execute("INSERT INTO accounts (user_id, balance, account_number) VALUES (?, 1000000.0, 'NX-ADMIN-00')",
                       (db.execute("SELECT last_insert_rowid()").fetchone()[0],))
            db.commit()
            print("Default admin created: admin / admin123")
    app.run(debug=False, host='0.0.0.0', port=5000)