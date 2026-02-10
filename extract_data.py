#!/usr/bin/env python
"""CLI script to extract data from QSEoW servers."""

import argparse
import sys
from qseow_ownership_manager.services import OwnershipService, ServerService
from qseow_ownership_manager.config import Config


def main():
    parser = argparse.ArgumentParser(
        description="Extract ownership data from QSEoW servers"
    )
    parser.add_argument(
        "--server",
        type=str,
        help="Server name to extract from (if not specified, extracts from all active servers)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Extract from all active servers",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all configured servers",
    )

    args = parser.parse_args()

    try:
        Config.validate()
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    server_service = ServerService()
    servers = server_service.get_all_servers()

    if args.list:
        print("\nConfigured Servers:")
        print("-" * 60)
        for server in servers:
            status = "Active" if server.get("is_active") else "Inactive"
            print(f"  {server['name']} ({server['server_url']}) - {status}")
        print()
        return

    if not servers:
        print("No servers configured. Add servers through the web UI first.")
        sys.exit(1)

    # Determine which servers to process
    if args.server:
        # Find specific server
        target_servers = [s for s in servers if s["name"] == args.server and s.get("is_active")]
        if not target_servers:
            print(f"Server '{args.server}' not found or inactive")
            sys.exit(1)
    else:
        # All active servers
        target_servers = [s for s in servers if s.get("is_active")]

    print("=" * 60)
    print("QSEoW Ownership Data Extraction")
    print("=" * 60)

    for server in target_servers:
        print(f"\nProcessing: {server['name']}")
        print("-" * 40)

        server_config = server_service.get_server_config(server["id"])
        if not server_config:
            print(f"  ERROR: Could not load configuration for {server['name']}")
            continue

        service = OwnershipService(server_config)
        count, message = service.sync_from_qlik()

        print(f"  {message}")

    print("\n" + "=" * 60)
    print("Extraction complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
