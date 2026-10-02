# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import MetaData, Table, create_engine, insert, make_url, select, text
from sqlalchemy.exc import SQLAlchemyError


def _database_url() -> str:
    configured_url = os.getenv("OVERTOURISM_DATABASE")
    if configured_url:
        return configured_url

    database_path = (
        Path(__file__).resolve().parents[3]
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

    database_url = database_url or _database_url()
    database = make_url(database_url)
    if (
        database.get_backend_name() == "sqlite"
        and database.database not in (None, "", ":memory:")
        and not Path(database.database).is_file()
    ):
        print("The configured SQLite database does not exist.", file=sys.stderr)
        return 1

    engine = create_engine(database)
    try:
        users = Table("users", MetaData(), autoload_with=engine)
        with engine.connect() as connection:
            if engine.dialect.name == "sqlite":
                connection.exec_driver_sql("BEGIN IMMEDIATE")
            elif engine.dialect.name == "postgresql":
                connection.execute(text("LOCK TABLE users IN EXCLUSIVE MODE"))
            else:
                raise RuntimeError(
                    f"First-admin bootstrap is unsupported for {engine.dialect.name}"
                )

            existing_user = (
                connection.execute(
                    select(users.c.role, users.c.is_active).where(
                        users.c.identifier == normalized_email
                    )
                )
                .mappings()
                .first()
            )
            if existing_user is not None:
                connection.rollback()
                if existing_user["role"] == "admin" and existing_user["is_active"]:
                    print(f"Admin already provisioned: {normalized_email}")
                    return 0
                print(
                    "The email already belongs to a non-admin or inactive user.",
                    file=sys.stderr,
                )
                return 1

            if connection.scalar(select(users.c.user_id).limit(1)) is not None:
                connection.rollback()
                print(
                    "Cannot bootstrap the first admin because the user registry is not empty.",
                    file=sys.stderr,
                )
                return 1

            now = datetime.now(UTC)
            connection.execute(
                insert(users).values(
                    user_id=uuid4().hex,
                    identifier=normalized_email,
                    subject=None,
                    role="admin",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            connection.commit()

        print(
            f"Pending admin created for {normalized_email}. "
            "Its first login must use a token with a verified matching email."
        )
        return 0
    except SQLAlchemyError:
        print("The initialized user registry is unavailable.", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Provision the first global admin in an empty user registry."
    )
    parser.add_argument("email", help="Verified email address of the first admin")
    args = parser.parse_args(argv)
    return bootstrap_admin(args.email)


if __name__ == "__main__":
    raise SystemExit(main())
