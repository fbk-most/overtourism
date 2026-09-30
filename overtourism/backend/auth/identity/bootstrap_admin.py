# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from overtourism.backend.auth.identity.sql_repository import SQLUserRepository
from overtourism.backend.auth.identity.user_manager import UserManager
from overtourism.backend.auth.identity.users import UserRole
from overtourism.dt_manager.stores.classes.sql.store import SQLStore


def _database_url() -> str:
    configured_url = os.getenv("OVERTOURISM_DATABASE")
    if configured_url:
        return configured_url

    database_path = (
        Path(__file__).resolve().parents[2]
        / "overtourism"
        / "database"
        / "overtourism.sqlite"
    )
    return f"sqlite:///{database_path}"


def bootstrap_admin(email: str, database_url: str | None = None) -> int:
    normalized_email = email.strip().casefold()
    local_part, separator, domain = normalized_email.partition("@")
    if not separator or not local_part or not domain or "@" in domain:
        print("Provide a valid admin email address.", file=sys.stderr)
        return 2

    store = SQLStore(database_url or _database_url())
    try:
        repository = SQLUserRepository(store.engine, store.session_factory)
        user_manager = UserManager(repository)
        existing_user = next(
            (
                user
                for user in user_manager.list_users()
                if user.identifier == normalized_email
            ),
            None,
        )
        if existing_user is not None:
            if existing_user.role is UserRole.ADMIN and existing_user.is_active:
                print(f"Admin already provisioned: {normalized_email}")
                return 0
            print(
                "The email already belongs to a non-admin or inactive user.",
                file=sys.stderr,
            )
            return 1

        try:
            user = user_manager.create_first_admin(normalized_email)
        except ValueError:
            print(
                "Cannot bootstrap the first admin because the user registry is not empty.",
                file=sys.stderr,
            )
            return 1

        print(
            f"Pending admin created for {user.identifier}. "
            "Its first login must use a token with a verified matching email."
        )
        return 0
    finally:
        store.engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Provision the first global admin in an empty user registry."
    )
    parser.add_argument("email", help="Verified email address of the first admin")
    args = parser.parse_args(argv)
    return bootstrap_admin(args.email)


if __name__ == "__main__":
    raise SystemExit(main())
