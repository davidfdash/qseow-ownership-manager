"""Service layer for QSEoW Ownership Manager."""

from typing import List, Dict, Optional, Tuple
from datetime import datetime

from .api.qrs_client import QRSClient
from .database.models import DatabaseManager, ServerConfig
from .config import Config


class ServerService:
    """Service for managing QSEoW server configurations."""

    def __init__(self):
        """Initialize server service."""
        self.db = DatabaseManager()

    def get_all_servers(self) -> List[Dict]:
        """Get all servers (without credentials)."""
        return self.db.get_all_servers()

    def get_server_by_id(self, server_id: int) -> Optional[Dict]:
        """Get a server by ID."""
        return self.db.get_server_by_id(server_id)

    def get_server_config(self, server_id: int) -> Optional[ServerConfig]:
        """Get full server config with decrypted credentials."""
        return self.db.get_server_config(server_id)

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
        """Create a new server configuration."""
        return self.db.create_server(
            name=name,
            server_url=server_url,
            cert_path=cert_path,
            key_path=key_path,
            root_cert_path=root_cert_path,
            user_directory=user_directory,
            user_id=user_id,
            notes=notes,
        )

    def update_server(self, server_id: int, **kwargs) -> bool:
        """Update a server configuration."""
        return self.db.update_server(server_id, **kwargs)

    def delete_server(self, server_id: int) -> bool:
        """Delete (deactivate) a server."""
        return self.db.delete_server(server_id)

    def test_connection(self, server_config: ServerConfig) -> Tuple[bool, str]:
        """
        Test connection to a QSEoW server.

        Args:
            server_config: Server configuration

        Returns:
            Tuple of (success, message)
        """
        try:
            client = QRSClient(
                server_url=server_config.server_url,
                cert_path=server_config.cert_path,
                key_path=server_config.key_path,
                root_cert_path=server_config.root_cert_path,
                user_directory=server_config.user_directory,
                user_id=server_config.user_id,
            )
            if client.test_connection():
                return True, "Connection successful"
            else:
                return False, "Connection failed"
        except Exception as e:
            return False, str(e)


class OwnershipService:
    """Service for managing object ownership in QSEoW."""

    def __init__(self, server_config: Optional[ServerConfig] = None):
        """
        Initialize ownership service.

        Args:
            server_config: Server configuration (for multi-server mode)
        """
        self.server_config = server_config

        if server_config:
            self.db = DatabaseManager(server_slug=server_config.slug)
            self.client = QRSClient(
                server_url=server_config.server_url,
                cert_path=server_config.cert_path,
                key_path=server_config.key_path,
                root_cert_path=server_config.root_cert_path,
                user_directory=server_config.user_directory,
                user_id=server_config.user_id,
            )
        else:
            # Legacy single-server mode using environment variables
            self.db = DatabaseManager()
            if Config.QSEOW_SERVER_URL and Config.QSEOW_CERT_PATH:
                self.client = QRSClient(
                    server_url=Config.QSEOW_SERVER_URL,
                    cert_path=Config.QSEOW_CERT_PATH,
                    key_path=Config.QSEOW_KEY_PATH,
                    root_cert_path=Config.QSEOW_ROOT_CERT_PATH or None,
                    user_directory=Config.QSEOW_USER_DIRECTORY,
                    user_id=Config.QSEOW_USER_ID,
                )
            else:
                self.client = None

    def sync_from_qlik(self) -> Tuple[int, str]:
        """
        Sync objects and users from QSEoW server.

        Returns:
            Tuple of (object_count, message)
        """
        if not self.client:
            return 0, "No QSEoW server configured"

        try:
            # Fetch objects
            objects = self.client.get_all_objects()

            # Store objects
            table_name = self.db.get_dated_table_name("object_ownership")
            self.db.store_objects(objects, table_name)

            # Fetch and store users
            users = self.client.get_users()
            if self.db.server_slug:
                self.db.store_users(users)

            return len(objects), f"Synced {len(objects)} objects and {len(users)} users"
        except Exception as e:
            return 0, f"Sync failed: {str(e)}"

    def get_objects(
        self,
        object_type: Optional[str] = None,
        owner_id: Optional[str] = None,
        stream_id: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get objects with optional filtering.

        Args:
            object_type: Filter by object type
            owner_id: Filter by owner ID
            stream_id: Filter by stream ID
            search: Search in object name

        Returns:
            List of filtered objects
        """
        table_name = self.db.get_latest_object_table()
        if not table_name:
            return []

        objects = self.db.get_objects(table_name)

        # Apply filters
        if object_type:
            objects = [o for o in objects if o.get("object_type") == object_type]
        if owner_id:
            objects = [o for o in objects if o.get("owner_id") == owner_id]
        if stream_id:
            objects = [o for o in objects if o.get("stream_id") == stream_id]
        if search:
            search_lower = search.lower()
            objects = [o for o in objects if search_lower in (o.get("object_name") or "").lower()]

        return objects

    def get_object_types(self) -> List[str]:
        """Get distinct object types from the current data."""
        table_name = self.db.get_latest_object_table()
        if not table_name:
            return []

        objects = self.db.get_objects(table_name)
        return sorted(set(o.get("object_type", "") for o in objects if o.get("object_type")))

    def get_owners(self) -> List[Dict]:
        """Get list of owners from current data."""
        table_name = self.db.get_latest_object_table()
        if not table_name:
            return []

        objects = self.db.get_objects(table_name)
        owners = {}
        for obj in objects:
            owner_id = obj.get("owner_id")
            if owner_id and owner_id not in owners:
                owners[owner_id] = {
                    "owner_id": owner_id,
                    "owner_name": obj.get("owner_name", "Unknown"),
                    "owner_directory": obj.get("owner_directory", ""),
                    "owner_user_id": obj.get("owner_user_id", ""),
                }
        return sorted(owners.values(), key=lambda x: x.get("owner_name", ""))

    def get_streams(self) -> List[Dict]:
        """Get list of streams from current data."""
        table_name = self.db.get_latest_object_table()
        if not table_name:
            return []

        objects = self.db.get_objects(table_name)
        streams = {}
        for obj in objects:
            stream_id = obj.get("stream_id")
            stream_name = obj.get("stream_name", "Unpublished")
            key = stream_id or "unpublished"
            if key not in streams:
                streams[key] = {
                    "stream_id": stream_id,
                    "stream_name": stream_name,
                }
        return sorted(streams.values(), key=lambda x: x.get("stream_name", ""))

    def get_users(self) -> List[Dict]:
        """Get all users."""
        return self.db.get_users()

    def transfer_ownership(
        self,
        object_ids: List[str],
        new_owner_id: str,
        reason: str = "",
        changed_by: str = "System",
    ) -> Tuple[int, int, List[str]]:
        """
        Transfer ownership of objects to a new owner.

        Args:
            object_ids: List of object IDs to transfer
            new_owner_id: New owner user ID
            reason: Reason for the transfer
            changed_by: Who initiated the transfer

        Returns:
            Tuple of (success_count, failure_count, error_messages)
        """
        if not self.client:
            return 0, len(object_ids), ["No QSEoW server configured"]

        table_name = self.db.get_latest_object_table()
        if not table_name:
            return 0, len(object_ids), ["No object data available"]

        objects = self.db.get_objects(table_name)
        objects_by_id = {o["object_id"]: o for o in objects}

        # Get new owner info from users
        users = self.db.get_users()
        new_owner = next((u for u in users if u["user_id"] == new_owner_id), None)
        new_owner_name = new_owner["user_name"] if new_owner else "Unknown"

        success_count = 0
        failure_count = 0
        errors = []

        for object_id in object_ids:
            obj = objects_by_id.get(object_id)
            if not obj:
                failure_count += 1
                errors.append(f"Object not found: {object_id}")
                continue

            try:
                self.client.update_object_owner(
                    object_id=obj["object_id"],
                    resource_id=obj["resource_id"],
                    object_type=obj["object_type"],
                    new_owner_id=new_owner_id,
                )

                # Log success
                if self.db.server_slug:
                    self.db.log_ownership_change(
                        object_id=obj["object_id"],
                        object_type=obj["object_type"],
                        object_name=obj["object_name"],
                        old_owner_id=obj.get("owner_id", ""),
                        old_owner_name=obj.get("owner_name", ""),
                        new_owner_id=new_owner_id,
                        new_owner_name=new_owner_name,
                        changed_by=changed_by,
                        change_reason=reason,
                        status="success",
                    )

                success_count += 1

            except Exception as e:
                error_msg = str(e)
                failure_count += 1
                errors.append(f"{obj['object_name']}: {error_msg}")

                # Log failure
                if self.db.server_slug:
                    self.db.log_ownership_change(
                        object_id=obj["object_id"],
                        object_type=obj["object_type"],
                        object_name=obj["object_name"],
                        old_owner_id=obj.get("owner_id", ""),
                        old_owner_name=obj.get("owner_name", ""),
                        new_owner_id=new_owner_id,
                        new_owner_name=new_owner_name,
                        changed_by=changed_by,
                        change_reason=reason,
                        status="failed",
                        error_message=error_msg,
                    )

        return success_count, failure_count, errors

    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """Get audit log entries."""
        return self.db.get_audit_log(limit)
