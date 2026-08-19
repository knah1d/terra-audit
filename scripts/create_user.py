#!/usr/bin/env python3
"""
Bootstrap a login for terra-audit — Phase 1 of the multi-tenant auth plan
(.claude/plans/misty-growing-yao.md).

This is a plain CLI script, not part of the Streamlit app: there's no
in-app signup/invite flow yet (that's Phase 4), so the very first admin
per organization has to be created out-of-band by the operator. Run it
once per person who needs a login.

Usage:
    python scripts/create_user.py --email you@org.com --password '...' \\
        --org-id default --role admin
"""

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_connection, initialize_database
from src.auth import hash_password, get_user_by_email

VALID_ROLES = ("admin", "analyst", "viewer")


def create_user(email: str, password: str, org_id: str, role: str) -> str:
    email = email.strip().lower()
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {VALID_ROLES}, got {role!r}")
    if get_user_by_email(email) is not None:
        raise ValueError(f"a user with email {email!r} already exists")

    with get_db_connection() as conn:
        org = conn.execute(
            "SELECT org_id FROM organizations WHERE org_id = ?", (org_id,)
        ).fetchone()
        if org is None:
            conn.execute(
                "INSERT INTO organizations (org_id, name) VALUES (?, ?)",
                (org_id, org_id),
            )
        user_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO users (user_id, org_id, email, password_hash, role)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, org_id, email, hash_password(password), role),
        )
        conn.commit()
    return user_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--org-id", required=True, help="Existing or new organization id (e.g. 'default', 'acme')")
    parser.add_argument("--role", default="analyst", choices=VALID_ROLES)
    args = parser.parse_args()

    initialize_database()
    user_id = create_user(args.email, args.password, args.org_id, args.role)
    print(f"Created user {args.email!r} (user_id={user_id}, org_id={args.org_id!r}, role={args.role!r})")


if __name__ == "__main__":
    main()
