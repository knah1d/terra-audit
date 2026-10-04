"""Account preferences; device-resolved appearance is never persisted."""
from sqlalchemy import text
from src.database import get_db_connection


def initialize_tables(conn):
    column = "theme_preference TEXT NOT NULL DEFAULT 'system' CHECK (theme_preference IN ('system','light','dark'))"
    if conn.dialect.name == "sqlite":
        try:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {column}"))
        except Exception as exc:
            if "duplicate column name" not in str(exc).lower():
                raise
    else:
        conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column}"))


def preferences(user, theme=None):
    if theme is not None and theme not in {"system", "light", "dark"}:
        raise ValueError("Invalid theme preference")
    scope = {"u": user["user_id"], "o": user["org_id"]}
    with get_db_connection() as conn:
        if theme is not None:
            conn.execute(text("""UPDATE users SET theme_preference=:theme
                WHERE user_id=:u AND org_id=:o AND is_active=1"""), {**scope, "theme": theme})
        value = conn.execute(text("""SELECT theme_preference FROM users
            WHERE user_id=:u AND org_id=:o AND is_active=1"""), scope).scalar_one_or_none()
        if value is None:
            raise PermissionError("Active account not found")
        conn.commit()
    return {"theme_preference": value}
