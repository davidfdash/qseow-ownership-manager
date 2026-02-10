"""Configuration management for QSEoW Ownership Manager."""

import os
from pathlib import Path
from dotenv import load_dotenv
from cryptography.fernet import Fernet

# Load environment variables
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # PostgreSQL Configuration
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "qseow_ownership")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")

    # Encryption key for storing certificates/credentials
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")

    # Default QSEoW Server Configuration (for single-server mode)
    QSEOW_SERVER_URL: str = os.getenv("QSEOW_SERVER_URL", "")
    QSEOW_CERT_PATH: str = os.getenv("QSEOW_CERT_PATH", "")
    QSEOW_KEY_PATH: str = os.getenv("QSEOW_KEY_PATH", "")
    QSEOW_ROOT_CERT_PATH: str = os.getenv("QSEOW_ROOT_CERT_PATH", "")
    QSEOW_USER_DIRECTORY: str = os.getenv("QSEOW_USER_DIRECTORY", "INTERNAL")
    QSEOW_USER_ID: str = os.getenv("QSEOW_USER_ID", "sa_api")

    @classmethod
    def get_database_url(cls) -> str:
        """Get PostgreSQL connection URL."""
        return (
            f"postgresql://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}"
            f"@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}"
        )

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration is present."""
        errors = []

        # PostgreSQL is always required
        if not cls.POSTGRES_HOST:
            errors.append("POSTGRES_HOST is required")
        if not cls.POSTGRES_DB:
            errors.append("POSTGRES_DB is required")
        if not cls.POSTGRES_USER:
            errors.append("POSTGRES_USER is required")
        if not cls.POSTGRES_PASSWORD:
            errors.append("POSTGRES_PASSWORD is required")

        # Encryption key required for multi-server mode
        if not cls.ENCRYPTION_KEY:
            errors.append("ENCRYPTION_KEY is required (generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")")

        if errors:
            raise ValueError("Configuration errors:\n- " + "\n- ".join(errors))

    @classmethod
    def get_fernet(cls) -> Fernet:
        """Get Fernet instance for encryption/decryption."""
        if not cls.ENCRYPTION_KEY:
            raise ValueError("ENCRYPTION_KEY not configured")
        return Fernet(cls.ENCRYPTION_KEY.encode())

    @classmethod
    def encrypt_value(cls, value: str) -> str:
        """Encrypt a value for secure storage."""
        fernet = cls.get_fernet()
        return fernet.encrypt(value.encode()).decode()

    @classmethod
    def decrypt_value(cls, encrypted_value: str) -> str:
        """Decrypt a stored value."""
        fernet = cls.get_fernet()
        return fernet.decrypt(encrypted_value.encode()).decode()
