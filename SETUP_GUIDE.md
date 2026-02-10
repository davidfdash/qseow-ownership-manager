# QSEoW Ownership Manager - Setup Guide

This guide walks you through pulling the project from GitHub and deploying it using Docker Compose.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) installed
- Qlik Sense Enterprise on Windows server with API access
- Admin access to export certificates from the Qlik Management Console (QMC)

## Step 1: Export Certificates from Qlik Sense

### Using the QMC

1. Log in to the **Qlik Management Console (QMC)**
   - URL: `https://your-qlik-server/qmc`

2. Navigate to **Certificates** (under Configure System)

3. Click **Export certificates**

4. Fill in the export dialog:
   - **Machine name**: Enter a name (e.g., `ownership-manager`)
   - **Include secret key**: Checked
   - **Export file format**: **Platform independent PEM-format**
   - **Certificate password**: Leave empty

5. Click **Export**

6. Download the ZIP file containing:
   - `client.pem` - The client certificate
   - `client_key.pem` - The private key
   - `root.pem` - The root CA certificate (optional)

## Step 2: Clone the Repository

```bash
git clone https://github.com/davidfdash/qseow-ownership-manager.git
cd qseow-ownership-manager
```

## Step 3: Place Certificates

Copy your exported certificate files into the `certs/` directory:

```bash
mkdir -p certs
cp /path/to/client.pem certs/client.pem
cp /path/to/client_key.pem certs/client_key.pem
```

On Linux, restrict permissions:

```bash
chmod 600 certs/*.pem
```

> **Note:** The `certs/` directory is gitignored. Certificate files are never committed to version control.

## Step 4: Configure Environment

### Create the .env file

```bash
cp .env.example .env
```

### Generate an encryption key

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If Python is not installed locally, you can generate the key after the containers start and update `.env` then.

### Edit .env

Open `.env` and fill in the values:

```env
# PostgreSQL Configuration (the db service runs in Docker, so use "db" as the host)
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=qseow_ownership
POSTGRES_USER=postgres
POSTGRES_PASSWORD=choose-a-strong-password

# Encryption key (paste the key generated above)
ENCRYPTION_KEY=your-generated-fernet-key

# QSEoW Server Configuration
QSEOW_SERVER_URL=https://your-qlik-server:4242
QSEOW_CERT_PATH=/app/certs/client.pem
QSEOW_KEY_PATH=/app/certs/client_key.pem
QSEOW_USER_DIRECTORY=INTERNAL
QSEOW_USER_ID=sa_api
```

> **Important:** Certificate paths must use the container path `/app/certs/`, not your local filesystem path. Docker Compose mounts `./certs` to `/app/certs` inside the container.

## Step 5: Build and Start

```bash
docker-compose up -d --build
```

This starts two containers:
- **db** - PostgreSQL 15 database
- **app** - The QSEoW Ownership Manager (Reflex web app)

The app container waits for PostgreSQL to be healthy before starting.

### Verify the containers are running

```bash
docker-compose ps
```

You should see both `db` and `app` with status `Up` or `healthy`.

### Check logs if something goes wrong

```bash
# All services
docker-compose logs

# App only
docker-compose logs app

# Follow logs in real time
docker-compose logs -f app
```

## Step 6: Access the Application

Open your browser to:

- **Frontend**: `http://localhost:3000`
- **Backend API**: `http://localhost:8000`

If deploying to a remote server, replace `localhost` with the server's IP address or hostname.

## Step 7: Add Your First Server

1. Click the **+** button next to "Select server..."

2. Fill in the server details:
   - **Server Name**: A friendly name (e.g., "Production Qlik")
   - **Server URL**: `https://your-qlik-server:4242`
   - **Client Certificate Path**: `/app/certs/client.pem`
   - **Client Key Path**: `/app/certs/client_key.pem`
   - **Root CA Certificate Path**: `/app/certs/root.pem` (optional)
   - **User Directory**: `INTERNAL` (or your Windows domain)
   - **User ID**: `sa_api` (or your service account)

3. Click **Test Connection**
   - If successful, you'll see "Connection successful!"
   - If failed, check the troubleshooting section below

4. Click **Create Server**

## Step 8: Sync and Manage Ownership

1. Select your server from the dropdown
2. Click **Sync from Qlik** to pull apps and reload tasks
3. Use filters to find objects by type, owner, stream, or name
4. Select objects using checkboxes
5. Click **Transfer Ownership** and choose the new owner
6. Check the audit log to verify the transfers

## Updating

To pull the latest version and redeploy:

```bash
git pull
docker-compose up -d --build
```

## Stopping and Removing

```bash
# Stop containers (data is preserved in the PostgreSQL volume)
docker-compose down

# Stop and remove all data (including the database)
docker-compose down -v
```

## Deploying to AWS EC2

Deployment scripts are provided in the `deploy/` directory for automated EC2 provisioning.

### Prerequisites

- AWS CLI configured, or `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` set as environment variables
- Python 3 with `boto3` installed (`pip install -r deploy/requirements.txt`)

### Deploy

```bash
python deploy/deploy_ec2.py
```

This creates a `t3.micro` instance in `us-east-1` with:
- Docker and Docker Compose installed
- The repository cloned and built
- Security group allowing ports 22 (SSH), 3000 (frontend), and 8000 (backend API)

After the instance is running, copy your certificate files to it:

```bash
scp -i ~/qseow-ownership-manager-key.pem certs/client.pem ec2-user@<public-ip>:/opt/qseow-ownership-manager/certs/
scp -i ~/qseow-ownership-manager-key.pem certs/client_key.pem ec2-user@<public-ip>:/opt/qseow-ownership-manager/certs/
```

Then SSH in and restart the app:

```bash
ssh -i ~/qseow-ownership-manager-key.pem ec2-user@<public-ip>
cd /opt/qseow-ownership-manager
sudo docker-compose restart app
```

The application will be available at `http://<public-ip>:3000`.

## Troubleshooting

### "Connection Failed" Error

1. **Wrong URL format**: Ensure the URL includes protocol and port
   - Correct: `https://qlikserver.domain.com:4242`
   - Wrong: `qlikserver.domain.com`

2. **Wrong certificate paths**: When running in Docker, paths must start with `/app/certs/`, not your local filesystem path

3. **Certificate issues**:
   - Verify certificate files are in PEM format (not DER or PFX)
   - Ensure the private key is not password-protected
   - Check the certificates were exported with "Include secret key" enabled

4. **Network issues**:
   - Verify you can reach the Qlik server on port 4242 from the machine running Docker
   - Check firewall rules on both ends

5. **User permissions**:
   - The user (e.g., `sa_api`) must have RootAdmin or appropriate roles in QMC

### Container Won't Start

1. Check logs: `docker-compose logs app`
2. Verify `.env` file exists and has all required variables
3. Ensure PostgreSQL is healthy: `docker-compose logs db`

### "No Objects Found" After Sync

1. Verify the service account has read access to apps in QMC Security Rules
2. Check the Qlik Sense Repository logs for access denied errors
3. Ensure apps exist and are visible in the Qlik Hub

### Database Issues

The PostgreSQL database runs inside Docker. To connect directly:

```bash
docker-compose exec db psql -U postgres -d qseow_ownership
```

To reset the database completely:

```bash
docker-compose down -v
docker-compose up -d --build
```

## Security Best Practices

- **Never commit certificates** to version control (`.gitignore` excludes `*.pem` files)
- **Use a strong password** for PostgreSQL in `.env`
- **Restrict network access** - don't expose ports 3000/8000 to the public internet without a reverse proxy and authentication
- **Review the audit log** regularly for unexpected ownership changes
- **Rotate the encryption key** if it is compromised (re-add server configurations after changing it)

## Appendix: QRS API Service Account Setup

### Creating a Service Account in QMC

1. Go to **Users** in QMC
2. Click **Create new**
3. Fill in:
   - **User ID**: `sa_api`
   - **User directory**: `INTERNAL`
   - **Name**: `Service Account - API`

### Assigning Permissions

1. Go to **Security Rules** in QMC
2. Create or edit a rule granting the service account:
   - Read access to Apps, Users, Streams, and Reload Tasks
   - Update access to Apps and Reload Tasks (for ownership transfer)

### Using a Windows Domain Account

If using a domain account instead of INTERNAL:

1. Set **User Directory** to your Windows domain (e.g., `MYDOMAIN`)
2. Set **User ID** to the Windows username (e.g., `svc_qlikapi`)
3. Ensure the account has logged in to Qlik Sense at least once
