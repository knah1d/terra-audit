#!/usr/bin/env python3
"""
Bootstrap a login for terra-audit — Phase 1 of the multi-tenant auth plan
(.claude/plans/misty-growing-yao.md).

This is a plain CLI script, not part of the Streamlit app. As of Phase 4
there IS an in-app "Team" invite flow (app.py, admin-only) for adding
teammates within an *existing* org — but this script is still how the
very first org+admin gets created in the first place, since nobody can
log in yet to use that in-app flow. Run it once per new organization.

Usage:
    python scripts/create_user.py --email you@org.com --password '...' \\
        --org-id default --role admin
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from src.database import get_db_connection, initialize_database
from src.auth import create_org_user, VALID_ROLES


def create_user(email: str, password: str, org_id: str, role: str) -> str:
    """Ensures the org row exists (this script is also how a brand-new org
    gets created, unlike the in-app Team flow which only adds users to an
    org that already has an admin), then delegates the actual user-row
    creation to src.auth.create_org_user so this logic lives in one place."""
    with get_db_connection() as conn:
        org = conn.execute(
            text("SELECT org_id FROM organizations WHERE org_id = :org_id"), {"org_id": org_id}
        ).fetchone()
        if org is None:
            conn.execute(
                text("INSERT INTO organizations (org_id, name) VALUES (:org_id, :name)"),
                {"org_id": org_id, "name": org_id},
            )
            conn.commit()
    return create_org_user(org_id, email, password, role)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--org-id", required=True, help="Existing or new organization id (e.g. 'default', 'acme')")
    parser.add_argument("--role", default="analyst", choices=sorted(VALID_ROLES))
    args = parser.parse_args()

    initialize_database()
    user_id = create_user(args.email, args.password, args.org_id, args.role)
    print(f"Created user {args.email!r} (user_id={user_id}, org_id={args.org_id!r}, role={args.role!r})")


if __name__ == "__main__":
    main()
