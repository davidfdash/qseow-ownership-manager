#!/bin/bash
set -e

# Log everything
exec > >(tee /var/log/user-data.log) 2>&1

echo "Starting QSEoW Ownership Manager deployment..."

# Update system
yum update -y

# Install Docker
yum install -y docker git
systemctl start docker
systemctl enable docker

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Clone the repository
cd /opt
git clone https://github.com/davidfdash/qseow-ownership-manager.git
cd qseow-ownership-manager

# Create certs directory
# IMPORTANT: You must manually copy your Qlik client certificate files
# to the certs/ directory before running docker-compose:
#   scp client.pem ec2-user@<ip>:/opt/qseow-ownership-manager/certs/client.pem
#   scp client_key.pem ec2-user@<ip>:/opt/qseow-ownership-manager/certs/client_key.pem
mkdir -p certs
echo "WARNING: Certificate files must be manually placed in /opt/qseow-ownership-manager/certs/"

# Create .env file with QSEoW configuration
cat > .env << 'EOF'
# PostgreSQL Configuration (using local Docker PostgreSQL)
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=qseow_ownership
POSTGRES_USER=postgres
POSTGRES_PASSWORD=qseow_secure_password_2026

# Encryption key for storing certificate paths securely
ENCRYPTION_KEY=

# QSEoW Server Configuration
QSEOW_SERVER_URL=https://ec2-54-210-217-253.compute-1.amazonaws.com:4242
QSEOW_CERT_PATH=/app/certs/client.pem
QSEOW_KEY_PATH=/app/certs/client_key.pem
QSEOW_USER_DIRECTORY=INTERNAL
QSEOW_USER_ID=sa_api
EOF

# Generate and set encryption key
pip3 install cryptography 2>/dev/null
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${ENCRYPTION_KEY}|" .env

echo "Generated encryption key and updated .env"

# Build and start the application
docker-compose up -d --build

echo "Deployment complete!"
echo "Application will be available on port 3000"
echo "QSEoW server: ec2-54-210-217-253.compute-1.amazonaws.com"
