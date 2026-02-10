"""Reflex UI for QSEoW Ownership Manager."""

import reflex as rx
from typing import List, Dict, Optional

from ..services import OwnershipService, ServerService
from ..database.models import ServerConfig


class State(rx.State):
    """Application state."""

    # Server management
    servers: List[Dict] = []
    current_server_id: int = 0
    current_server_name: str = ""

    # Server modal state
    show_server_modal: bool = False
    server_modal_mode: str = "add"  # "add" or "edit"
    server_form_name: str = ""
    server_form_url: str = ""
    server_form_cert_path: str = ""
    server_form_key_path: str = ""
    server_form_root_cert_path: str = ""
    server_form_user_directory: str = "INTERNAL"
    server_form_user_id: str = "sa_api"
    server_form_notes: str = ""
    server_test_result: str = ""
    editing_server_id: int = 0

    # Data state
    objects: List[Dict] = []
    users: List[Dict] = []
    owners: List[Dict] = []
    streams: List[Dict] = []
    object_types: List[str] = []
    audit_log: List[Dict] = []

    # Filter state
    filter_type: str = ""
    filter_owner: str = ""
    filter_stream: str = ""
    search_query: str = ""

    # Selection state
    selected_ids: List[str] = []
    select_all: bool = False

    # Transfer modal state
    show_transfer_modal: bool = False
    transfer_new_owner: str = ""
    transfer_reason: str = ""

    # Audit modal state
    show_audit_modal: bool = False

    # Status messages
    status_message: str = ""
    error_message: str = ""
    is_loading: bool = False

    # ==================== Service Accessors ====================

    def _get_server_service(self) -> ServerService:
        """Get server service instance."""
        return ServerService()

    def _get_service(self) -> OwnershipService:
        """Get ownership service for current server."""
        if self.current_server_id:
            server_config = self._get_server_service().get_server_config(
                self.current_server_id
            )
            if server_config:
                return OwnershipService(server_config)
        return OwnershipService()  # Legacy fallback

    @rx.var
    def server_options(self) -> List[str]:
        """Get server names for dropdown."""
        return [s["name"] for s in self.servers if s.get("is_active") is not False]

    @rx.var
    def has_servers(self) -> bool:
        """Check if any servers exist."""
        return len(self.servers) > 0

    @rx.var
    def has_active_server(self) -> bool:
        """Check if a server is selected."""
        return self.current_server_id > 0

    @rx.var
    def filtered_objects(self) -> List[Dict]:
        """Get filtered objects based on current filters."""
        result = self.objects

        if self.filter_type:
            result = [o for o in result if o.get("object_type") == self.filter_type]
        if self.filter_owner:
            result = [o for o in result if o.get("owner_id") == self.filter_owner]
        if self.filter_stream:
            if self.filter_stream == "unpublished":
                result = [o for o in result if not o.get("stream_id")]
            else:
                result = [o for o in result if o.get("stream_id") == self.filter_stream]
        if self.search_query:
            query = self.search_query.lower()
            result = [o for o in result if query in (o.get("object_name") or "").lower()]

        return result

    @rx.var
    def selected_count(self) -> int:
        """Get count of selected objects."""
        return len(self.selected_ids)

    @rx.var
    def owner_options(self) -> List[Dict]:
        """Get owner options for dropdown."""
        return [{"id": o["owner_id"] or "unknown", "label": f"{o['owner_name']} ({o.get('owner_directory', '')})"}
                for o in self.owners if o.get("owner_id")]

    @rx.var
    def user_options(self) -> List[Dict]:
        """Get user options for transfer dropdown."""
        return [{"id": u["user_id"], "label": f"{u['user_name']} ({u.get('user_directory', '')})"}
                for u in self.users]

    @rx.var
    def stream_options(self) -> List[Dict]:
        """Get stream options for dropdown."""
        return [{"id": s.get("stream_id") or "unpublished", "label": s["stream_name"]}
                for s in self.streams]

    # ==================== Server Management Methods ====================

    def load_servers(self):
        """Load all servers."""
        try:
            self.servers = self._get_server_service().get_all_servers()
            if self.servers and not self.current_server_id:
                active_servers = [s for s in self.servers if s.get("is_active") is not False]
                if active_servers:
                    self._select_server_internal(active_servers[0]["id"], active_servers[0]["name"])
        except Exception as e:
            self.error_message = f"Error loading servers: {str(e)}"

    def _select_server_internal(self, server_id: int, server_name: str):
        """Internal method to select a server."""
        self.current_server_id = server_id
        self.current_server_name = server_name
        self.objects = []
        self.users = []
        self.selected_ids = []

    def select_server_by_name(self, name: str):
        """Select a server by name."""
        if not name:
            return
        for server in self.servers:
            if server["name"] == name:
                self._select_server_internal(server["id"], server["name"])
                self.load_data()
                break

    def open_add_server_modal(self):
        """Open modal to add a new server."""
        self.server_modal_mode = "add"
        self.server_form_name = ""
        self.server_form_url = ""
        self.server_form_cert_path = ""
        self.server_form_key_path = ""
        self.server_form_root_cert_path = ""
        self.server_form_user_directory = "INTERNAL"
        self.server_form_user_id = "sa_api"
        self.server_form_notes = ""
        self.server_test_result = ""
        self.editing_server_id = 0
        self.show_server_modal = True

    def open_edit_server_modal(self, server_id: int):
        """Open modal to edit a server."""
        server = self._get_server_service().get_server_by_id(server_id)
        if server:
            self.server_modal_mode = "edit"
            self.server_form_name = server["name"]
            self.server_form_url = server["server_url"]
            self.server_form_cert_path = ""  # Don't show encrypted paths
            self.server_form_key_path = ""
            self.server_form_root_cert_path = ""
            self.server_form_user_directory = server.get("user_directory", "INTERNAL")
            self.server_form_user_id = server.get("user_id", "sa_api")
            self.server_form_notes = server.get("notes", "") or ""
            self.server_test_result = ""
            self.editing_server_id = server_id
            self.show_server_modal = True

    def close_server_modal(self):
        """Close the server modal."""
        self.show_server_modal = False
        self.server_test_result = ""

    def set_server_form_name(self, value: str):
        self.server_form_name = value

    def set_server_form_url(self, value: str):
        self.server_form_url = value

    def set_server_form_cert_path(self, value: str):
        self.server_form_cert_path = value

    def set_server_form_key_path(self, value: str):
        self.server_form_key_path = value

    def set_server_form_root_cert_path(self, value: str):
        self.server_form_root_cert_path = value

    def set_server_form_user_directory(self, value: str):
        self.server_form_user_directory = value

    def set_server_form_user_id(self, value: str):
        self.server_form_user_id = value

    def set_server_form_notes(self, value: str):
        self.server_form_notes = value

    def test_server_connection(self):
        """Test connection to the server."""
        if not self.server_form_url or not self.server_form_cert_path or not self.server_form_key_path:
            self.server_test_result = "Please fill in URL, certificate, and key paths"
            return

        try:
            from ..api.qrs_client import QRSClient
            client = QRSClient(
                server_url=self.server_form_url,
                cert_path=self.server_form_cert_path,
                key_path=self.server_form_key_path,
                root_cert_path=self.server_form_root_cert_path or None,
                user_directory=self.server_form_user_directory,
                user_id=self.server_form_user_id,
            )
            if client.test_connection():
                self.server_test_result = "Connection successful!"
            else:
                self.server_test_result = "Connection failed"
        except Exception as e:
            self.server_test_result = f"Error: {str(e)}"

    def save_server(self):
        """Save the server (create or update)."""
        if not self.server_form_name or not self.server_form_url:
            self.error_message = "Name and URL are required"
            return

        try:
            service = self._get_server_service()

            if self.server_modal_mode == "add":
                if not self.server_form_cert_path or not self.server_form_key_path:
                    self.error_message = "Certificate and key paths are required for new servers"
                    return

                service.create_server(
                    name=self.server_form_name,
                    server_url=self.server_form_url,
                    cert_path=self.server_form_cert_path,
                    key_path=self.server_form_key_path,
                    root_cert_path=self.server_form_root_cert_path or None,
                    user_directory=self.server_form_user_directory,
                    user_id=self.server_form_user_id,
                    notes=self.server_form_notes or None,
                )
                self.status_message = f"Server '{self.server_form_name}' created"
            else:
                update_kwargs = {
                    "name": self.server_form_name,
                    "server_url": self.server_form_url,
                    "user_directory": self.server_form_user_directory,
                    "user_id": self.server_form_user_id,
                    "notes": self.server_form_notes or None,
                }
                if self.server_form_cert_path:
                    update_kwargs["cert_path"] = self.server_form_cert_path
                if self.server_form_key_path:
                    update_kwargs["key_path"] = self.server_form_key_path
                if self.server_form_root_cert_path:
                    update_kwargs["root_cert_path"] = self.server_form_root_cert_path

                service.update_server(self.editing_server_id, **update_kwargs)
                self.status_message = f"Server '{self.server_form_name}' updated"

            self.close_server_modal()
            self.load_servers()

        except Exception as e:
            self.error_message = f"Error saving server: {str(e)}"

    def delete_server(self, server_id: int):
        """Delete a server."""
        try:
            self._get_server_service().delete_server(server_id)
            self.status_message = "Server deleted"
            self.load_servers()
            if self.current_server_id == server_id:
                self.current_server_id = 0
                self.current_server_name = ""
                self.objects = []
        except Exception as e:
            self.error_message = f"Error deleting server: {str(e)}"

    # ==================== Data Loading Methods ====================

    def load_data(self):
        """Load data from database."""
        if not self.current_server_id:
            return

        self.is_loading = True
        self.error_message = ""

        try:
            service = self._get_service()
            self.objects = service.get_objects()
            self.users = service.get_users()
            self.owners = service.get_owners()
            self.streams = service.get_streams()
            self.object_types = service.get_object_types()
            self.selected_ids = []
            self.select_all = False
        except Exception as e:
            self.error_message = f"Error loading data: {str(e)}"
        finally:
            self.is_loading = False

    def sync_from_qlik(self):
        """Sync data from QSEoW server."""
        if not self.current_server_id:
            self.error_message = "Please select a server first"
            return

        self.is_loading = True
        self.status_message = ""
        self.error_message = ""

        try:
            service = self._get_service()
            count, message = service.sync_from_qlik()
            self.status_message = message
            self.load_data()
        except Exception as e:
            self.error_message = f"Sync failed: {str(e)}"
        finally:
            self.is_loading = False

    # ==================== Filter Methods ====================

    def set_filter_type(self, value: str):
        self.filter_type = "" if value == "__all__" else value
        self.selected_ids = []

    def set_filter_owner(self, value: str):
        self.filter_owner = "" if value == "__all__" else value
        self.selected_ids = []

    def set_filter_stream(self, value: str):
        self.filter_stream = "" if value == "__all__" else value
        self.selected_ids = []

    def set_search_query(self, value: str):
        self.search_query = value

    def clear_filters(self):
        """Clear all filters."""
        self.filter_type = ""
        self.filter_owner = ""
        self.filter_stream = ""
        self.search_query = ""
        self.selected_ids = []

    # ==================== Selection Methods ====================

    def toggle_select(self, object_id: str):
        """Toggle selection of an object."""
        if object_id in self.selected_ids:
            self.selected_ids = [id for id in self.selected_ids if id != object_id]
        else:
            self.selected_ids = self.selected_ids + [object_id]

    def toggle_select_all(self, checked: bool):
        """Toggle select all."""
        self.select_all = checked
        if checked:
            self.selected_ids = [o["object_id"] for o in self.filtered_objects]
        else:
            self.selected_ids = []

    # ==================== Transfer Methods ====================

    def open_transfer_modal(self):
        """Open the transfer ownership modal."""
        if not self.selected_ids:
            self.error_message = "Please select at least one object"
            return
        self.show_transfer_modal = True
        self.transfer_new_owner = ""
        self.transfer_reason = ""

    def close_transfer_modal(self):
        """Close the transfer modal."""
        self.show_transfer_modal = False

    def set_transfer_new_owner(self, value: str):
        self.transfer_new_owner = value

    def set_transfer_reason(self, value: str):
        self.transfer_reason = value

    def execute_transfer(self):
        """Execute the ownership transfer."""
        if not self.transfer_new_owner:
            self.error_message = "Please select a new owner"
            return

        self.is_loading = True
        self.status_message = ""
        self.error_message = ""

        try:
            service = self._get_service()
            success, failed, errors = service.transfer_ownership(
                object_ids=self.selected_ids,
                new_owner_id=self.transfer_new_owner,
                reason=self.transfer_reason,
                changed_by="UI User",
            )

            if failed == 0:
                self.status_message = f"Successfully transferred {success} object(s)"
            else:
                self.status_message = f"Transferred {success}, failed {failed}"
                if errors:
                    self.error_message = "; ".join(errors[:3])

            self.close_transfer_modal()
            self.selected_ids = []
            self.sync_from_qlik()  # Refresh data

        except Exception as e:
            self.error_message = f"Transfer failed: {str(e)}"
        finally:
            self.is_loading = False

    # ==================== Audit Log Methods ====================

    def open_audit_modal(self):
        """Open the audit log modal."""
        try:
            service = self._get_service()
            self.audit_log = service.get_audit_log(100)
            self.show_audit_modal = True
        except Exception as e:
            self.error_message = f"Error loading audit log: {str(e)}"

    def close_audit_modal(self):
        """Close the audit log modal."""
        self.show_audit_modal = False

    # ==================== Message Methods ====================

    def clear_status(self):
        """Clear status message."""
        self.status_message = ""

    def clear_error(self):
        """Clear error message."""
        self.error_message = ""


# ==================== UI Components ====================


def server_selector():
    """Create the server selector component."""
    return rx.hstack(
        rx.text("Server:", font_weight="bold", color="gray"),
        rx.el.select(
            rx.el.option("Select server...", value=""),
            rx.foreach(
                State.server_options,
                lambda name: rx.el.option(name, value=name),
            ),
            value=State.current_server_name,
            on_change=State.select_server_by_name,
            style={
                "padding": "8px 12px",
                "border": "1px solid #ccc",
                "border_radius": "6px",
                "min_width": "200px",
                "cursor": "pointer",
            },
        ),
        rx.button(
            rx.icon("plus", size=16),
            on_click=State.open_add_server_modal,
            variant="outline",
            size="2",
            title="Add Server",
        ),
        spacing="2",
        align="center",
    )


def server_management_modal():
    """Server management modal."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.cond(
                    State.server_modal_mode == "add",
                    "Add New Server",
                    "Edit Server",
                )
            ),
            rx.vstack(
                rx.text("Server Name", font_weight="bold", size="2"),
                rx.input(
                    value=State.server_form_name,
                    on_change=State.set_server_form_name,
                    placeholder="My QSEoW Server",
                    width="100%",
                ),
                rx.text("Server URL", font_weight="bold", size="2"),
                rx.input(
                    value=State.server_form_url,
                    on_change=State.set_server_form_url,
                    placeholder="https://qlikserver.domain.com:4242",
                    width="100%",
                ),
                rx.text("Client Certificate Path (.pem)", font_weight="bold", size="2"),
                rx.input(
                    value=State.server_form_cert_path,
                    on_change=State.set_server_form_cert_path,
                    placeholder="/path/to/client.pem",
                    width="100%",
                ),
                rx.text("Client Key Path (.pem)", font_weight="bold", size="2"),
                rx.input(
                    value=State.server_form_key_path,
                    on_change=State.set_server_form_key_path,
                    placeholder="/path/to/client_key.pem",
                    width="100%",
                ),
                rx.text("Root CA Certificate Path (optional)", font_weight="bold", size="2"),
                rx.input(
                    value=State.server_form_root_cert_path,
                    on_change=State.set_server_form_root_cert_path,
                    placeholder="/path/to/root.pem",
                    width="100%",
                ),
                rx.hstack(
                    rx.vstack(
                        rx.text("User Directory", font_weight="bold", size="2"),
                        rx.input(
                            value=State.server_form_user_directory,
                            on_change=State.set_server_form_user_directory,
                            placeholder="INTERNAL",
                            width="100%",
                        ),
                        width="50%",
                    ),
                    rx.vstack(
                        rx.text("User ID", font_weight="bold", size="2"),
                        rx.input(
                            value=State.server_form_user_id,
                            on_change=State.set_server_form_user_id,
                            placeholder="sa_api",
                            width="100%",
                        ),
                        width="50%",
                    ),
                    width="100%",
                ),
                rx.text("Notes", font_weight="bold", size="2"),
                rx.text_area(
                    value=State.server_form_notes,
                    on_change=State.set_server_form_notes,
                    placeholder="Optional notes about this server...",
                    width="100%",
                ),
                rx.hstack(
                    rx.button(
                        "Test Connection",
                        on_click=State.test_server_connection,
                        variant="outline",
                    ),
                    rx.cond(
                        State.server_test_result != "",
                        rx.text(
                            State.server_test_result,
                            color=rx.cond(
                                State.server_test_result.contains("successful"),
                                "green",
                                "red",
                            ),
                            size="2",
                        ),
                        rx.text(""),
                    ),
                    align="center",
                ),
                rx.hstack(
                    rx.button(
                        "Cancel",
                        on_click=State.close_server_modal,
                        variant="outline",
                    ),
                    rx.button(
                        rx.cond(
                            State.server_modal_mode == "add",
                            "Create Server",
                            "Update Server",
                        ),
                        on_click=State.save_server,
                    ),
                    justify="end",
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
            max_width="500px",
        ),
        open=State.show_server_modal,
        on_open_change=State.set_show_server_modal,
    )


def filters():
    """Filter controls."""
    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.text("Object Type", size="1", color="gray"),
                rx.select.root(
                    rx.select.trigger(placeholder="All Types"),
                    rx.select.content(
                        rx.select.item("All Types", value="__all__"),
                        rx.foreach(
                            State.object_types,
                            lambda t: rx.select.item(t, value=t),
                        ),
                    ),
                    value=State.filter_type,
                    on_change=State.set_filter_type,
                ),
                spacing="1",
            ),
            rx.vstack(
                rx.text("Owner", size="1", color="gray"),
                rx.select.root(
                    rx.select.trigger(placeholder="All Owners"),
                    rx.select.content(
                        rx.select.item("All Owners", value="__all__"),
                        rx.foreach(
                            State.owner_options,
                            lambda o: rx.select.item(o["label"], value=o["id"]),
                        ),
                    ),
                    value=State.filter_owner,
                    on_change=State.set_filter_owner,
                ),
                spacing="1",
            ),
            rx.vstack(
                rx.text("Stream", size="1", color="gray"),
                rx.select.root(
                    rx.select.trigger(placeholder="All Streams"),
                    rx.select.content(
                        rx.select.item("All Streams", value="__all__"),
                        rx.foreach(
                            State.stream_options,
                            lambda s: rx.select.item(s["label"], value=s["id"]),
                        ),
                    ),
                    value=State.filter_stream,
                    on_change=State.set_filter_stream,
                ),
                spacing="1",
            ),
            rx.vstack(
                rx.text("Search", size="1", color="gray"),
                rx.input(
                    value=State.search_query,
                    on_change=State.set_search_query,
                    placeholder="Search by name...",
                ),
                spacing="1",
            ),
            rx.button(
                "Clear",
                on_click=State.clear_filters,
                variant="outline",
                size="2",
            ),
            spacing="4",
            align="end",
            wrap="wrap",
        ),
        padding="4",
    )


def object_table():
    """Object data table."""
    return rx.box(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell(
                        rx.checkbox(
                            checked=State.select_all,
                            on_change=State.toggle_select_all,
                        ),
                        width="40px",
                    ),
                    rx.table.column_header_cell("Name"),
                    rx.table.column_header_cell("Type"),
                    rx.table.column_header_cell("Owner"),
                    rx.table.column_header_cell("Stream"),
                    rx.table.column_header_cell("Published"),
                ),
            ),
            rx.table.body(
                rx.foreach(
                    State.filtered_objects,
                    lambda obj: rx.table.row(
                        rx.table.cell(
                            rx.checkbox(
                                checked=State.selected_ids.contains(obj["object_id"]),
                                on_change=lambda: State.toggle_select(obj["object_id"]),
                            ),
                        ),
                        rx.table.cell(obj["object_name"]),
                        rx.table.cell(
                            rx.badge(obj["object_type"], variant="soft"),
                        ),
                        rx.table.cell(
                            rx.text(rx.cond(obj["owner_name"], obj["owner_name"], "Unknown"), size="2"),
                        ),
                        rx.table.cell(
                            rx.text(rx.cond(obj["stream_name"], obj["stream_name"], "Unpublished"), size="2"),
                        ),
                        rx.table.cell(
                            rx.cond(
                                obj["published"],
                                rx.badge("Yes", color_scheme="green"),
                                rx.badge("No", color_scheme="gray"),
                            ),
                        ),
                    ),
                ),
            ),
            width="100%",
        ),
        overflow_x="auto",
    )


def transfer_modal():
    """Transfer ownership modal."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Transfer Ownership"),
            rx.vstack(
                rx.text(
                    f"Transfer {State.selected_count} selected object(s) to:",
                    size="2",
                ),
                rx.select.root(
                    rx.select.trigger(placeholder="Select new owner..."),
                    rx.select.content(
                        rx.foreach(
                            State.user_options,
                            lambda u: rx.select.item(u["label"], value=u["id"]),
                        ),
                    ),
                    value=State.transfer_new_owner,
                    on_change=State.set_transfer_new_owner,
                ),
                rx.text("Reason (optional)", size="2", color="gray"),
                rx.text_area(
                    value=State.transfer_reason,
                    on_change=State.set_transfer_reason,
                    placeholder="Enter reason for transfer...",
                    width="100%",
                ),
                rx.hstack(
                    rx.button(
                        "Cancel",
                        on_click=State.close_transfer_modal,
                        variant="outline",
                    ),
                    rx.button(
                        "Transfer",
                        on_click=State.execute_transfer,
                        color_scheme="blue",
                    ),
                    justify="end",
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
            max_width="400px",
        ),
        open=State.show_transfer_modal,
        on_open_change=State.set_show_transfer_modal,
    )


def audit_modal():
    """Audit log modal."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Ownership Change Audit Log"),
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Date"),
                            rx.table.column_header_cell("Object"),
                            rx.table.column_header_cell("From"),
                            rx.table.column_header_cell("To"),
                            rx.table.column_header_cell("Status"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            State.audit_log,
                            lambda log: rx.table.row(
                                rx.table.cell(
                                    rx.text(log["change_date"], size="1"),
                                ),
                                rx.table.cell(
                                    rx.text(log["object_name"], size="2"),
                                ),
                                rx.table.cell(
                                    rx.text(rx.cond(log["old_owner_name"], log["old_owner_name"], "-"), size="2"),
                                ),
                                rx.table.cell(
                                    rx.text(rx.cond(log["new_owner_name"], log["new_owner_name"], "-"), size="2"),
                                ),
                                rx.table.cell(
                                    rx.cond(
                                        log["status"] == "success",
                                        rx.badge("Success", color_scheme="green"),
                                        rx.badge("Failed", color_scheme="red"),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    width="100%",
                ),
                max_height="400px",
                overflow_y="auto",
            ),
            rx.hstack(
                rx.button(
                    "Close",
                    on_click=State.close_audit_modal,
                ),
                justify="end",
                width="100%",
                padding_top="3",
            ),
            max_width="800px",
        ),
        open=State.show_audit_modal,
        on_open_change=State.set_show_audit_modal,
    )


def navbar():
    """Navigation bar."""
    return rx.box(
        rx.hstack(
            rx.heading("QSEoW Ownership Manager", size="5"),
            rx.spacer(),
            server_selector(),
            rx.button(
                rx.icon("refresh-cw", size=16),
                "Sync from Qlik",
                on_click=State.sync_from_qlik,
                loading=State.is_loading,
                disabled=~State.has_active_server,
            ),
            rx.button(
                rx.icon("file-text", size=16),
                "Audit Log",
                on_click=State.open_audit_modal,
                variant="outline",
                disabled=~State.has_active_server,
            ),
            spacing="4",
            align="center",
            padding="4",
        ),
        border_bottom="1px solid #eee",
        background="white",
    )


def status_bar():
    """Status and error messages."""
    return rx.vstack(
        rx.cond(
            State.status_message != "",
            rx.callout(
                State.status_message,
                icon="check",
                color_scheme="green",
            ),
            rx.text(""),
        ),
        rx.cond(
            State.error_message != "",
            rx.callout(
                State.error_message,
                icon="alert-triangle",
                color_scheme="red",
            ),
            rx.text(""),
        ),
        width="100%",
    )


def action_bar():
    """Action buttons."""
    return rx.hstack(
        rx.text(f"{State.selected_count} selected", color="gray", size="2"),
        rx.button(
            "Transfer Ownership",
            on_click=State.open_transfer_modal,
            disabled=State.selected_count == 0,
        ),
        justify="between",
        align="center",
        padding="2",
    )


def no_server_message():
    """Message shown when no servers are configured."""
    return rx.center(
        rx.vstack(
            rx.icon("server", size=48, color="gray"),
            rx.heading("No Servers Configured", size="4", color="gray"),
            rx.text(
                "Click the + button above to add a QSEoW server.",
                color="gray",
            ),
            rx.button(
                "Add Server",
                on_click=State.open_add_server_modal,
            ),
            spacing="4",
            align="center",
        ),
        height="400px",
    )


def index():
    """Main page."""
    return rx.box(
        navbar(),
        rx.box(
            status_bar(),
            rx.cond(
                State.has_active_server,
                rx.vstack(
                    filters(),
                    action_bar(),
                    object_table(),
                    spacing="4",
                    width="100%",
                ),
                no_server_message(),
            ),
            padding="4",
            max_width="1400px",
            margin="0 auto",
        ),
        transfer_modal(),
        audit_modal(),
        server_management_modal(),
        on_mount=[State.load_servers, State.load_data],
    )


app = rx.App()
app.add_page(index, route="/")
