# QSEoW Ownership Manager - Setup Guide

This guide walks you through setting up the QSEoW Ownership Manager from scratch.

## Prerequisites

- Python 3.9 or higher
- PostgreSQL 12 or higher
- Qlik Sense Enterprise on Windows server with API access
- Admin access to export certificates from QMC

## Step 1: Export Certificates from Qlik Sense

### Using the QMC

1. Log in to the **Qlik Management Console (QMC)**
   - URL: `https://your-qlik-server/qmc`

2. Navigate to **Certificates** (under Configure System)

3. Click **Export certificates**

4. Fill in the export dialog:
   - **Machine name**: Enter a name (e.g., `ownership-manager`)
   - **Include secret key**: ✓ Checked
   - **Export file format**: **Platform independent PEM-format**
   - **Certificate password**: Leave empty (recommended for this use case)

5. Click **Export**

6. Download the ZIP file containing:
   - `client.pem` - The client certificate
   - `client_key.pem` - The private key
   - `root.pem` - The root CA certificate

### Alternative: Using PowerShell

```powershell
# On the Qlik Sense server
$certPath = "C:\ProgramData\Qlik\Sense\Repository\Exported Certificates"
$machineName = "ownership-manager"

# Export using the Qlik CLI
& "C:\Program Files\Qlik\Sense\Repository\Repository.exe" `
    -exportCertificates `
    -exportPassword "" `
    -pwd "$env:COMPUTERNAME" `
    -certificateSetName "$machineName"
```

## Step 2: Install PostgreSQL

### Windows

1. Download from [postgresql.org](https://www.postgresql.org/download/windows/)
2. Run the installer
3. Remember the password you set for `postgres` user
4. Default port is 5432

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Create Database

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database
CREATE DATABASE qseow_ownership;
\q
```

## Step 3: Set Up the Project

### Clone or Download

```bash
git clone https://github.com/yourusername/qseow-ownership-manager.git
cd qseow-ownership-manager
```

### Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 4: Configure Certificates

### Place Certificates

Create a `certs` directory and copy your exported certificates:

```bash
mkdir certs
# Copy your certificates here
# certs/client.pem
# certs/client_key.pem
# certs/root.pem
```

### Set Permissions (Linux)

```bash
chmod 600 certs/*.pem
```

## Step 5: Configure Environment

### Generate Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save this key - you'll need it for the `.env` file.

### Create .env File

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=qseow_ownership
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password

# Encryption key (from the command above)
ENCRYPTION_KEY=your-generated-fernet-key
```

## Step 6: Initialize Reflex

```bash
reflex init
```

This creates necessary configuration files for the web framework.

## Step 7: Run the Application

### Development Mode

```bash
reflex run
```

The application will be available at:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`

### Production Mode

```bash
reflex run --env prod
```

## Step 8: Add Your First Server

1. Open `http://localhost:3000` in your browser

2. Click the **+** button next to "Select server..."

3. Fill in the server details:
   - **Server Name**: A friendly name (e.g., "Production Qlik")
   - **Server URL**: `https://your-qlik-server:4242`
   - **Client Certificate Path**: Full path to `client.pem`
   - **Client Key Path**: Full path to `client_key.pem`
   - **Root CA Certificate Path**: Full path to `root.pem` (optional but recommended)
   - **User Directory**: `INTERNAL` (or your Windows domain)
   - **User ID**: `sa_api` (or your service account)

4. Click **Test Connection**
   - If successful, you'll see "Connection successful!"
   - If failed, check the error message and verify your settings

5. Click **Create Server**

## Step 9: Sync Data

1. Select your server from the dropdown

2. Click **Sync from Qlik**

3. Wait for the sync to complete

4. Your apps and reload tasks will appear in the table

## Step 10: Transfer Ownership

1. Use filters to find objects (by type, owner, stream, or search)

2. Select objects using checkboxes

3. Click **Transfer Ownership**

4. Select the new owner from the dropdown

5. Optionally add a reason for the transfer

6. Click **Transfer**

7. Check the audit log to verify the transfers

## Troubleshooting

### "Connection Failed" Error

**Possible causes:**

1. **Wrong URL format**: Ensure URL includes protocol and port
   - Correct: `https://qlikserver.domain.com:4242`
   - Wrong: `qlikserver.domain.com`

2. **Certificate issues**:
   - Verify certificate files exist and are readable
   - Check certificates are in PEM format (not DER or PFX)
   - Ensure private key is included and not password-protected

3. **Network issues**:
   - Verify you can reach the server on port 4242
   - Check firewall rules

4. **User permissions**:
   - The user (e.g., `sa_api`) must have RootAdmin or appropriate roles

### "SSL Certificate Verify Failed"

The application disables SSL verification by default for self-signed certificates. If you want strict verification:

1. Ensure the root CA certificate path is provided
2. The root CA must be the one that signed the server's certificate

### "No Objects Found"

1. Verify the service account has read access to apps:
   - In QMC → Security Rules, check "Read" permissions

2. Check if apps exist:
   - Log in to the Hub and verify apps are visible

3. Review the server logs:
   - Check Qlik Sense Repository logs for access denied errors

### Database Connection Error

1. Verify PostgreSQL is running:
   ```bash
   # Linux
   sudo systemctl status postgresql

   # Windows
   # Check Services for "postgresql-x64-XX"
   ```

2. Test connection manually:
   ```bash
   psql -h localhost -U postgres -d qseow_ownership
   ```

3. Check `.env` file has correct credentials

## Security Best Practices

### Certificate Storage

- Never commit certificates to version control
- Store certificates in a secure location with restricted permissions
- Consider using a secrets manager in production

### Database Security

- Use a strong password for PostgreSQL
- Restrict database access to application servers only
- Enable SSL for database connections in production

### Network Security

- Run the application on a private network
- Use a reverse proxy (nginx) with SSL for external access
- Restrict access to the application to authorized users

### Audit Log

- Regularly review the audit log for unexpected changes
- Set up alerts for bulk ownership transfers
- Archive old audit logs per your retention policy

## Appendix: QRS API User Setup

### Creating a Service Account

1. In QMC, go to **Users**
2. Click **Create new**
3. Fill in:
   - **User ID**: `sa_api`
   - **User directory**: `INTERNAL`
   - **Name**: `Service Account - API`

### Assigning Permissions

1. In QMC, go to **Security Rules**
2. Create a rule or assign the user to a role with:
   - Read access to Apps
   - Read access to Users
   - Update access to Apps (for ownership transfer)
   - Read access to Reload Tasks
   - Update access to Reload Tasks (for ownership transfer)

### Using a Windows Domain Account

If using a domain account instead of INTERNAL:

1. Set **User Directory** to your Windows domain (e.g., `MYDOMAIN`)
2. Set **User ID** to the Windows username (e.g., `svc_qlikapi`)
3. Ensure the account has logged in to Qlik Sense at least once
