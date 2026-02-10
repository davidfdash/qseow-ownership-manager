"""Qlik Sense Enterprise on Windows QRS API client for managing objects and ownership.

Built against the Qlik Sense Repository Service API documentation:
https://help.qlik.com/en-US/sense-developer/November2025/Subsystems/RepositoryServiceAPI/
"""

import json
import random
import string
import requests
import urllib3
from typing import List, Dict, Optional
from datetime import datetime, timezone

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _generate_xrf_key() -> str:
    """Generate a random 16-character XRF key (letters and digits)."""
    characters = string.ascii_letters + string.digits
    return "".join(random.choices(characters, k=16))


class QRSClient:
    """Client for interacting with Qlik Repository Service (QRS) API.

    Authentication uses client certificates issued by the Qlik Sense
    internal CA. All requests include the mandatory XRF key for CSRF
    protection as both a query parameter and header.

    Reference: https://help.qlik.com/en-US/sense-developer/November2025/
    Subsystems/RepositoryServiceAPI/Content/Sense_RepositoryServiceAPI/
    RepositoryServiceAPI-Getting-Started.htm
    """

    def __init__(
        self,
        server_url: str,
        cert_path: str,
        key_path: str,
        user_directory: str = "INTERNAL",
        user_id: str = "sa_api",
        root_cert_path: Optional[str] = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.cert_path = cert_path
        self.key_path = key_path
        self.user_directory = user_directory
        self.user_id = user_id
        self.root_cert_path = root_cert_path
        self.xrf = _generate_xrf_key()

        self.session = requests.Session()
        self.session.cert = (cert_path, key_path)
        self.session.verify = root_cert_path if root_cert_path else False

        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Qlik-XrfKey": self.xrf,
            "X-Qlik-User": f"UserDirectory={user_directory};UserId={user_id}",
        })

    def _url(self, endpoint: str) -> str:
        """Build full URL with xrfkey query parameter."""
        separator = "&" if "?" in endpoint else "?"
        return f"{self.server_url}/qrs/{endpoint}{separator}xrfkey={self.xrf}"

    # ---- Low-level HTTP helpers ----

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> requests.Response:
        """Perform a GET request to a QRS endpoint."""
        response = self.session.get(self._url(endpoint), params=params)
        response.raise_for_status()
        return response

    def _put(self, endpoint: str, data: Dict) -> requests.Response:
        """Perform a PUT request to a QRS endpoint."""
        response = self.session.put(self._url(endpoint), data=json.dumps(data))
        response.raise_for_status()
        return response

    # ---- Query helpers ----

    def _get_full(self, entity_type: str, filter_str: Optional[str] = None) -> List[Dict]:
        """GET /qrs/{entity_type}/full — returns all entities of a type.

        The /full endpoint returns complete entity representations.
        No pagination parameters are supported; the full result set is
        returned in a single response.

        Args:
            entity_type: QRS entity type (app, reloadtask, user, stream, etc.)
            filter_str: Optional QRS filter (e.g. "name eq 'My App'")
        """
        params = {}
        if filter_str:
            params["filter"] = filter_str
        return self._get(f"{entity_type}/full", params=params or None).json()

    def _get_entity(self, entity_type: str, entity_id: str) -> Optional[Dict]:
        """GET /qrs/{entity_type}/{id} — returns a single entity."""
        url = self._url(f"{entity_type}/{entity_id}")
        response = self.session.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _now_iso() -> str:
        """Current UTC time in the ISO format QRS expects for modifiedDate."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    # ---- Public API: read ----

    def get_all_objects(self) -> List[Dict]:
        """Fetch apps and reload tasks and return a normalised list."""
        all_objects = []

        for app in self._get_full("app"):
            stream = app.get("stream")
            all_objects.append({
                "object_id": app.get("id"),
                "resource_id": app.get("id"),
                "object_type": "app",
                "object_name": app.get("name", ""),
                "owner_id": app.get("owner", {}).get("id"),
                "owner_name": app.get("owner", {}).get("name"),
                "owner_directory": app.get("owner", {}).get("userDirectory"),
                "owner_user_id": app.get("owner", {}).get("userId"),
                "created_date": app.get("createdDate"),
                "modified_date": app.get("modifiedDate"),
                "description": app.get("description", ""),
                "stream_id": stream.get("id") if stream else None,
                "stream_name": stream.get("name") if stream else "Unpublished",
                "published": app.get("published", False),
                "extracted_date": datetime.now().isoformat(),
            })

        for task in self._get_full("reloadtask"):
            app_info = task.get("app", {})
            all_objects.append({
                "object_id": task.get("id"),
                "resource_id": task.get("id"),
                "object_type": "reload_task",
                "object_name": task.get("name", ""),
                "owner_id": task.get("owner", {}).get("id"),
                "owner_name": task.get("owner", {}).get("name"),
                "owner_directory": task.get("owner", {}).get("userDirectory"),
                "owner_user_id": task.get("owner", {}).get("userId"),
                "created_date": task.get("createdDate"),
                "modified_date": task.get("modifiedDate"),
                "description": f"Task for app: {app_info.get('name', 'Unknown')}",
                "stream_id": None,
                "stream_name": None,
                "published": None,
                "extracted_date": datetime.now().isoformat(),
            })

        return all_objects

    def get_users(self) -> List[Dict]:
        """GET /qrs/user/full — return all users."""
        return [
            {
                "user_id": u.get("id"),
                "user_name": u.get("name", ""),
                "user_directory": u.get("userDirectory", ""),
                "user_id_attr": u.get("userId", ""),
                "email": "",
                "status": "active" if not u.get("inactive") else "inactive",
            }
            for u in self._get_full("user")
            if u.get("id")
        ]

    def get_streams(self) -> List[Dict]:
        """GET /qrs/stream/full — return all streams."""
        return [
            {
                "stream_id": s.get("id"),
                "stream_name": s.get("name", ""),
                "owner_id": s.get("owner", {}).get("id"),
                "owner_name": s.get("owner", {}).get("name"),
            }
            for s in self._get_full("stream")
            if s.get("id")
        ]

    # ---- Public API: ownership transfer ----

    def _get_user_full(self, user_id: str) -> Dict:
        """Fetch the full user entity for use in owner updates."""
        user = self._get_entity("user", user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")
        return user

    def update_app_owner(self, app_id: str, resource_id: str, new_owner_id: str) -> bool:
        """Change the owner of an app.

        Per QRS API requirements:
        1. GET the full app entity
        2. Replace the 'owner' field with the full new-owner user object
        3. Set 'modifiedDate' to the current timestamp
        4. PUT the entire entity back
        """
        app = self._get_entity("app", resource_id)
        if not app:
            raise ValueError(f"App not found: {resource_id}")

        new_owner = self._get_user_full(new_owner_id)
        app["owner"] = new_owner
        app["modifiedDate"] = self._now_iso()

        self._put(f"app/{resource_id}", app)
        return True

    def update_reload_task_owner(self, task_id: str, resource_id: str, new_owner_id: str) -> bool:
        """Change the owner of a reload task.

        Same pattern as app ownership: GET full entity, replace owner
        with full user object, update modifiedDate, PUT back.
        """
        task = self._get_entity("reloadtask", resource_id)
        if not task:
            raise ValueError(f"Reload task not found: {resource_id}")

        new_owner = self._get_user_full(new_owner_id)
        task["owner"] = new_owner
        task["modifiedDate"] = self._now_iso()

        self._put(f"reloadtask/{resource_id}", task)
        return True

    def update_object_owner(self, object_id: str, resource_id: str, object_type: str, new_owner_id: str) -> bool:
        """Route ownership update to the correct entity-specific method."""
        object_type_lower = object_type.lower().replace("_", "")

        if object_type_lower == "app":
            return self.update_app_owner(object_id, resource_id, new_owner_id)
        elif object_type_lower in ("reloadtask", "reloadtask"):
            return self.update_reload_task_owner(object_id, resource_id, new_owner_id)
        else:
            raise ValueError(f"Ownership transfer not supported for object type: {object_type}")

    # ---- Connection test ----

    def test_connection(self) -> bool:
        """GET /qrs/about — verify connectivity and authentication."""
        try:
            self._get("about")
            return True
        except Exception:
            return False


# Backwards compatibility alias
QlikSenseClient = QRSClient
