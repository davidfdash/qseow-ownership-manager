# QSEoW Ownership Manager

A web-based tool for managing object ownership in **Qlik Sense Enterprise on Windows (QSEoW)**. Transfer app and reload task ownership between users with full audit logging.

## Features

- **Multi-Server Support**: Manage multiple QSEoW environments from a single interface
- **Certificate Authentication**: Secure connection using Qlik client certificates
- **Ownership Transfer**: Bulk transfer ownership of apps and reload tasks
- **Audit Logging**: Complete history of all ownership changes
- **Stream Filtering**: Filter objects by stream, owner, or type
- **Search**: Find objects quickly by name

## Supported Object Types

- **Apps**: Qlik Sense applications
- **Reload Tasks**: Scheduled reload tasks

## Prerequisites

- Python 3.9+
- PostgreSQL 12+
- Qlik Sense Enterprise on Windows server
- Exported client certificates from QSEoW

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/qseow-ownership-manager.git
cd qseow-ownership-manager
```

### 2. Set Up Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 5. Generate Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Add the generated key to your `.env` file as `ENCRYPTION_KEY`.

### 6. Initialize and Run

```bash
reflex init
reflex run
```

Open your browser to `http://localhost:3000`

## Certificate Setup

QSEoW uses certificate-based authentication for API access. You need to export certificates from your Qlik Sense server.

### Export Certificates from QMC

1. Log in to the Qlik Management Console (QMC)
2. Go to **Certificates**
3. Click **Export certificates**
4. Enter a machine name (can be any identifier)
5. Select **Include secret key**
6. Export format: **Platform independent PEM-format**
7. Click **Export**

This creates three files:
- `client.pem` - Client certificate
- `client_key.pem` - Client private key
- `root.pem` - Root CA certificate

### Place Certificates

Place the exported certificates in the `certs/` directory:

```
qseow-ownership-manager/
├── certs/
│   ├── client.pem
│   ├── client_key.pem
│   └── root.pem
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_HOST` | Yes | PostgreSQL server hostname |
| `POSTGRES_PORT` | Yes | PostgreSQL port (default: 5432) |
| `POSTGRES_DB` | Yes | Database name |
| `POSTGRES_USER` | Yes | Database username |
| `POSTGRES_PASSWORD` | Yes | Database password |
| `ENCRYPTION_KEY` | Yes | Fernet key for encrypting credentials |

### Adding a Server in the UI

1. Click the **+** button next to the server dropdown
2. Enter server details:
   - **Name**: Display name for the server
   - **Server URL**: QRS API URL (e.g., `https://qlikserver.domain.com:4242`)
   - **Certificate Path**: Path to `client.pem`
   - **Key Path**: Path to `client_key.pem`
   - **Root CA Path**: Path to `root.pem` (optional)
   - **User Directory**: Usually `INTERNAL`
   - **User ID**: Usually `sa_api` or your service account
3. Click **Test Connection** to verify
4. Click **Create Server**

## Docker Deployment

### Build and Run

```bash
docker-compose up -d --build
```

### Mount Certificates

The `docker-compose.yml` mounts the `./certs` directory to `/app/certs` in the container. Update certificate paths in the server configuration to use `/app/certs/`.

### Example .env for Docker

```env
POSTGRES_HOST=your-database-host
POSTGRES_PORT=5432
POSTGRES_DB=qseow_ownership
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-secure-password
ENCRYPTION_KEY=your-fernet-key
```

## Architecture

```
qseow-ownership-manager/
├── qseow_ownership_manager/
│   ├── api/
│   │   └── qrs_client.py      # QRS API client with cert auth
│   ├── database/
│   │   └── models.py          # Database models and operations
│   ├── ui/
│   │   └── app.py             # Reflex UI components
│   ├── config.py              # Configuration management
│   └── services.py            # Business logic layer
├── certs/                     # Certificate storage (gitignored)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── rxconfig.py
```

## Database Schema

### Servers Table

Stores QSEoW server configurations with encrypted certificate paths.

### Object Ownership Tables

Daily snapshots of apps and reload tasks: `object_ownership_{server_slug}_{date}`

### Audit Log

Complete history of ownership changes: `{server_slug}_ownership_audit_log`

## Security Considerations

- Certificate paths are encrypted at rest using Fernet encryption
- Certificates are never committed to version control
- The `.gitignore` excludes all `.pem` files
- Use a strong, randomly generated `ENCRYPTION_KEY`
- Consider network security between this tool and your QSEoW servers

## Troubleshooting

### Connection Failed

1. Verify the server URL includes the port (default: 4242)
2. Check certificate paths are correct
3. Ensure certificates are not password-protected
4. Verify the user directory and user ID have appropriate permissions

### Certificate Errors

1. Ensure certificates are in PEM format
2. Check file permissions (readable by the application)
3. For self-signed certificates, the root CA may need to be trusted

### No Objects Found

1. Verify the service account has read access to apps
2. Check the QRS API is accessible from your machine
3. Review Qlik Sense logs for access denied errors

## License

MIT License
