#!/bin/bash
# deploy.sh - Futuristic Core Banking Platform Auto-Deployment
# Usage: sudo DOMAIN=yourdomain.com EMAIL=admin@yourdomain.com bash deploy.sh

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)."
    exit 1
fi

DOMAIN=${DOMAIN:-example.com}
EMAIL=${EMAIL:-admin@example.com}
APP_DIR="/opt/core-bank"
SERVICE_NAME="core-bank"

echo "🚀 Starting deployment for domain: $DOMAIN"

# 1. System Updates & Base Packages
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx sqlite3

# 2. Application Setup
mkdir -p $APP_DIR
cd $APP_DIR

# App files are already in $APP_DIR because install.sh handled the git clone.
# Just ensuring we are in the right directory before proceeding.
cd $APP_DIR
# Ensure app.py and other files exist
if [ ! -f "app.py" ]; then
    echo "❌ app.py not found in $APP_DIR. Please place all source files there first."
    exit 1
fi

# Create virtualenv
python3 -m venv venv
source venv/bin/activate
pip install flask flask-login argon2-cffi gunicorn

# Initialize DB (will be created on first run)
python3 -c "from app import init_db; init_db()"

# UPGRADE: The bash script runs as root, so core_bank.db is created by root. 
# The systemd service runs as www-data. Without this chown, www-data cannot write to the database.
chown -R www-data:www-data $APP_DIR

# Generate a secure random secret key for Flask
FLASK_SECRET=$(openssl rand -hex 32)

# Create systemd service
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=Core Banking Flask App
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
Environment="DB_PATH=$APP_DIR/core_bank.db"
Environment="SECRET_KEY=$FLASK_SECRET"
ExecStart=$APP_DIR/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# 3. Nginx Configuration
cat > /etc/nginx/sites-available/$DOMAIN.conf << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf /etc/nginx/sites-available/$DOMAIN.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 4. Let's Encrypt SSL
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m $EMAIL --redirect
# Auto-renewal cron
echo "0 3 * * * root certbot renew --quiet --post-hook 'systemctl reload nginx'" > /etc/cron.d/certbot-renew

# 5. Final Output
echo "✅ Deployment complete! Visit https://$DOMAIN"
echo "Admin login: https://$DOMAIN/admin   (admin / admin123)"
echo "Change admin password immediately via settings or DB."