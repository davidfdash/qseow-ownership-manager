"""Database models and management for QSEoW Ownership Manager."""

import re
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

from sqlalchemy import create_engine, text, MetaData, Table, Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import sessionmaker

from ..config import Config


@dataclass
class ServerConfig:
    """Configuration for a QSEoW server."""
    id: int
    name: str
    slug: str
    server_url: str
    cert_path: str
    key_path: str
    root_cert_path: Optional[str]
    user_directory: str
    user_id: str
    notes: Optional[str]


class DatabaseManager:
    """Manages database operations for QSEoW Ownership Manager."""

    def __init__(self, server_slug: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            server_slug: Optional server slug for server-specific tables
        """
        self.engine = create_engine(Config.get_database_url())
        self.Session = sessionmaker(bind=self.engine)
        self.metadata = MetaData()
        self.server_slug = server_slug

        # Ensure base tables exist
        self._create_servers_table()

    def _get_table_prefix(self) -> str:
        """Get table prefix for current server."""
        if self.server_slug:
            return f"{self.server_slug}_"
        return ""

    def get_dated_table_name(self, base_name: str) -> str:
        """Get table name with server prefix and current date."""
        prefix = self._get_table_prefix()
        date_str = datetime.now().strftime("%Y%m%d")
        return f"{base_name}_{prefix}{date_str}" if prefix else f"{base_name}_{date_str}"

    @staticmethod
    def generate_slug(name: str) -> str:
        """Generate a URL-safe slug from a name."""
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9]+', '_', slug)
        slug = slug.strip('_')
        return slug[:50]

    def _create_servers_table(self):
        """Create the servers table if it doesn't exist."""
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS servers (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    slug VARCHAR(100) NOT NULL UNIQUE,
                    server_url VARCHAR(500) NOT NULL,
                    cert_path_encrypted TEXT NOT NULL,
                    key_path_encrypted TEXT NOT NULL,
                    root_cert_path_encrypted TEXT,
                    user_directory VARCHAR(255) DEFAULT 'INTERNAL',
                    user_id VARCHAR(255) DEFAULT 'sa_api',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    notes TEXT
                )
            """))
            conn.commit()

    def create_server_tables(self, server_slug: str):
        """
        Create server-specific tables (users and audit log).

        Args:
            server_slug: Server slug for table naming
        """
        with self.engine.connect() as conn:
            # Users table
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {server_slug}_users (
                    user_id VARCHAR(100) PRIMARY KEY,
                    user_name VARCHAR(255),
                    user_directory VARCHAR(255),
                    user_id_attr VARCHAR(255),
                    email VARCHAR(255),
                    status VARCHAR(50)
                )
            """))

            # Audit log table
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {server_slug}_ownership_audit_log (
                    id SERIAL PRIMARY KEY,
                    object_id VARCHAR(100),
                    object_type VARCHAR(50),
                    object_name VARCHAR(500),
                    old_owner_id VARCHAR(100),
                    old_owner_name VARCHAR(255),
                    new_owner_id VARCHAR(100),
                    new_owner_name VARCHAR(255),
                    changed_by VARCHAR(255),
                    change_reason TEXT,
                    change_date TIMESTAMP DEFAULT NOW(),
                    status VARCHAR(50),
                    error_message TEXT
                )
            """))
            conn.commit()

    def create_object_table(self, table_name: str):
        """
        Create an object ownership table.

        Args:
            table_name: Full table name including date
        """
        with self.engine.connect() as conn:
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    object_id VARCHAR(100) PRIMARY KEY,
                    resource_id VARCHAR(100),
                    object_type VARCHAR(50),
                    object_name VARCHAR(500),
                    owner_id VARCHAR(100),
                    owner_name VARCHAR(255),
                    owner_directory VARCHAR(255),
                    owner_user_id VARCHAR(255),
                    created_date TIMESTAMP,
                    modified_date TIMESTAMP,
                    description TEXT,
                    stream_id VARCHAR(100),
                    stream_name VARCHAR(255),
                    published BOOLEAN,
                    extracted_date TIMESTAMP
                )
            """))
            conn.commit()

    # ==================== Server CRUD Operations ====================

    def get_all_servers(self) -> List[Dict]:
        """Get all servers (without decrypted credentials)."""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, slug, server_url, user_directory, user_id,
                       is_active, created_at, updated_at, notes
                FROM servers
                ORDER BY name
            """))
            return [dict(row._mapping) for row in result]

    def get_server_by_id(self, server_id: int) -> Optional[Dict]:
        """Get a server by ID (without decrypted credentials)."""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, slug, server_url, user_directory, user_id,
                       is_active, created_at, updated_at, notes
                FROM servers
                WHERE id = :server_id
            """), {"server_id": server_id})
            row = result.fetchone()
            return dict(row._mapping) if row else None

    def get_server_config(self, server_id: int) -> Optional[ServerConfig]:
        """Get full server config with decrypted credentials."""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, slug, server_url, cert_path_encrypted,
                       key_path_encrypted, root_cert_path_encrypted,
                       user_directory, user_id, notes
                FROM servers
                WHERE id = :server_id AND is_active = TRUE
            """), {"server_id": server_id})
            row = result.fetchone()

            if not row:
                return None

            row_dict = dict(row._mapping)
            return ServerConfig(
                id=row_dict["id"],
                name=row_dict["name"],
                slug=row_dict["slug"],
                server_url=row_dict["server_url"],
                cert_path=Config.decrypt_value(row_dict["cert_path_encrypted"]),
                key_path=Config.decrypt_value(row_dict["key_path_encrypted"]),
                root_cert_path=Config.decrypt_value(row_dict["root_cert_path_encrypted"]) if row_dict["root_cert_path_encrypted"] else None,
                user_directory=row_dict["user_directory"],
                user_id=row_dict["user_id"],
                notes=row_dict["notes"],
            )

    def create_server(
        self,
        name: str,
        server_url: str,
        cert_path: str,
        key_path: str,
        root_cert_path: Optional[str] = None,
        user_directory: str = "INTERNAL",
        user_id: str = "sa_api",
        notes: Optional[str] = None,
    ) -> int:
        """
        Create a new server.

        Args:
            name: Display name for the server
            server_url: QRS server URL
            cert_path: Path to client certificate
            key_path: Path to client key
            root_cert_path: Path to root CA certificate (optional)
            user_directory: User directory for authentication
            user_id: User ID for authentication
            notes: Optional notes

        Returns:
            New server ID
        """
        slug = self.generate_slug(name)

        # Encrypt certificate paths
        cert_path_encrypted = Config.encrypt_value(cert_path)
        key_path_encrypted = Config.encrypt_value(key_path)
        root_cert_path_encrypted = Config.encrypt_value(root_cert_path) if root_cert_path else None

        with self.engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO servers (name, slug, server_url, cert_path_encrypted,
                                    key_path_encrypted, root_cert_path_encrypted,
                                    user_directory, user_id, notes)
                VALUES (:name, :slug, :server_url, :cert_path_encrypted,
                        :key_path_encrypted, :root_cert_path_encrypted,
                        :user_directory, :user_id, :notes)
                RETURNING id
            """), {
                "name": name,
                "slug": slug,
                "server_url": server_url,
                "cert_path_encrypted": cert_path_encrypted,
                "key_path_encrypted": key_path_encrypted,
                "root_cert_path_encrypted": root_cert_path_encrypted,
                "user_directory": user_directory,
                "user_id": user_id,
                "notes": notes,
            })
            server_id = result.fetchone()[0]
            conn.commit()

        # Create server-specific tables
        self.create_server_tables(slug)

        return server_id

    def update_server(
        self,
        server_id: int,
        name: Optional[str] = None,
        server_url: Optional[str] = None,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
        root_cert_path: Optional[str] = None,
        user_directory: Optional[str] = None,
        user_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Update an existing server."""
        updates = []
        params = {"server_id": server_id}

        if name is not None:
            updates.append("name = :name")
            params["name"] = name
        if server_url is not None:
            updates.append("server_url = :server_url")
            params["server_url"] = server_url
        if cert_path is not None:
            updates.append("cert_path_encrypted = :cert_path_encrypted")
            params["cert_path_encrypted"] = Config.encrypt_value(cert_path)
        if key_path is not None:
            updates.append("key_path_encrypted = :key_path_encrypted")
            params["key_path_encrypted"] = Config.encrypt_value(key_path)
        if root_cert_path is not None:
            updates.append("root_cert_path_encrypted = :root_cert_path_encrypted")
            params["root_cert_path_encrypted"] = Config.encrypt_value(root_cert_path) if root_cert_path else None
        if user_directory is not None:
            updates.append("user_directory = :user_directory")
            params["user_directory"] = user_directory
        if user_id is not None:
            updates.append("user_id = :user_id")
            params["user_id"] = user_id
        if notes is not None:
            updates.append("notes = :notes")
            params["notes"] = notes

        if not updates:
            return False

        updates.append("updated_at = NOW()")

        with self.engine.connect() as conn:
            conn.execute(text(f"""
                UPDATE servers
                SET {', '.join(updates)}
                WHERE id = :server_id
            """), params)
            conn.commit()

        return True

    def delete_server(self, server_id: int) -> bool:
        """Soft delete a server by marking it inactive."""
        with self.engine.connect() as conn:
            conn.execute(text("""
                UPDATE servers
                SET is_active = FALSE, updated_at = NOW()
                WHERE id = :server_id
            """), {"server_id": server_id})
            conn.commit()
        return True

    # ==================== Object Operations ====================

    def store_objects(self, objects: List[Dict], table_name: str):
        """
        Store objects in the database.

        Args:
            objects: List of object dictionaries
            table_name: Target table name
        """
        self.create_object_table(table_name)

        with self.engine.connect() as conn:
            for obj in objects:
                conn.execute(text(f"""
                    INSERT INTO {table_name} (
                        object_id, resource_id, object_type, object_name,
                        owner_id, owner_name, owner_directory, owner_user_id,
                        created_date, modified_date, description,
                        stream_id, stream_name, published, extracted_date
                    ) VALUES (
                        :object_id, :resource_id, :object_type, :object_name,
                        :owner_id, :owner_name, :owner_directory, :owner_user_id,
                        :created_date, :modified_date, :description,
                        :stream_id, :stream_name, :published, :extracted_date
                    )
                    ON CONFLICT (object_id) DO UPDATE SET
                        resource_id = EXCLUDED.resource_id,
                        object_type = EXCLUDED.object_type,
                        object_name = EXCLUDED.object_name,
                        owner_id = EXCLUDED.owner_id,
                        owner_name = EXCLUDED.owner_name,
                        owner_directory = EXCLUDED.owner_directory,
                        owner_user_id = EXCLUDED.owner_user_id,
                        created_date = EXCLUDED.created_date,
                        modified_date = EXCLUDED.modified_date,
                        description = EXCLUDED.description,
                        stream_id = EXCLUDED.stream_id,
                        stream_name = EXCLUDED.stream_name,
                        published = EXCLUDED.published,
                        extracted_date = EXCLUDED.extracted_date
                """), obj)
            conn.commit()

    def get_objects(self, table_name: str) -> List[Dict]:
        """Get all objects from a table."""
        with self.engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {table_name} ORDER BY object_name"))
            return [dict(row._mapping) for row in result]

    def get_latest_object_table(self) -> Optional[str]:
        """Get the most recent object ownership table name."""
        prefix = self._get_table_prefix()
        pattern = f"object_ownership_{prefix}%" if prefix else "object_ownership_%"

        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name LIKE :pattern
                ORDER BY table_name DESC
                LIMIT 1
            """), {"pattern": pattern})
            row = result.fetchone()
            return row[0] if row else None

    # ==================== User Operations ====================

    def store_users(self, users: List[Dict]):
        """Store users in the server-specific users table."""
        if not self.server_slug:
            raise ValueError("Server slug required for storing users")

        table_name = f"{self.server_slug}_users"

        with self.engine.connect() as conn:
            for user in users:
                conn.execute(text(f"""
                    INSERT INTO {table_name} (
                        user_id, user_name, user_directory, user_id_attr, email, status
                    ) VALUES (
                        :user_id, :user_name, :user_directory, :user_id_attr, :email, :status
                    )
                    ON CONFLICT (user_id) DO UPDATE SET
                        user_name = EXCLUDED.user_name,
                        user_directory = EXCLUDED.user_directory,
                        user_id_attr = EXCLUDED.user_id_attr,
                        email = EXCLUDED.email,
                        status = EXCLUDED.status
                """), user)
            conn.commit()

    def get_users(self) -> List[Dict]:
        """Get all users from the server-specific users table."""
        if not self.server_slug:
            return []

        table_name = f"{self.server_slug}_users"

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"SELECT * FROM {table_name} ORDER BY user_name"))
                return [dict(row._mapping) for row in result]
        except Exception:
            return []

    # ==================== Audit Log Operations ====================

    def log_ownership_change(
        self,
        object_id: str,
        object_type: str,
        object_name: str,
        old_owner_id: str,
        old_owner_name: str,
        new_owner_id: str,
        new_owner_name: str,
        changed_by: str,
        change_reason: str,
        status: str,
        error_message: Optional[str] = None,
    ):
        """Log an ownership change to the audit log."""
        if not self.server_slug:
            raise ValueError("Server slug required for audit logging")

        table_name = f"{self.server_slug}_ownership_audit_log"

        with self.engine.connect() as conn:
            conn.execute(text(f"""
                INSERT INTO {table_name} (
                    object_id, object_type, object_name,
                    old_owner_id, old_owner_name, new_owner_id, new_owner_name,
                    changed_by, change_reason, status, error_message
                ) VALUES (
                    :object_id, :object_type, :object_name,
                    :old_owner_id, :old_owner_name, :new_owner_id, :new_owner_name,
                    :changed_by, :change_reason, :status, :error_message
                )
            """), {
                "object_id": object_id,
                "object_type": object_type,
                "object_name": object_name,
                "old_owner_id": old_owner_id,
                "old_owner_name": old_owner_name,
                "new_owner_id": new_owner_id,
                "new_owner_name": new_owner_name,
                "changed_by": changed_by,
                "change_reason": change_reason,
                "status": status,
                "error_message": error_message,
            })
            conn.commit()

    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """Get recent audit log entries."""
        if not self.server_slug:
            return []

        table_name = f"{self.server_slug}_ownership_audit_log"

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT * FROM {table_name}
                    ORDER BY change_date DESC
                    LIMIT :limit
                """), {"limit": limit})
                return [dict(row._mapping) for row in result]
        except Exception:
            return []
