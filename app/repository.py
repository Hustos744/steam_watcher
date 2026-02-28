import sqlite3
from pathlib import Path


class StateRepository:
    def __init__(self, sqlite_path: str):
        self.sqlite_path = sqlite_path
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.sqlite_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS posted_deals (
                    appid INTEGER NOT NULL,
                    discount_expiration INTEGER NOT NULL,
                    final_price INTEGER NOT NULL,
                    posted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (appid, discount_expiration, final_price)
                )
                """
            )
            conn.commit()

    def was_posted(self, appid: int, discount_expiration: int, final_price: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT 1
                FROM posted_deals
                WHERE appid = ? AND discount_expiration = ? AND final_price = ?
                LIMIT 1
                """,
                (appid, discount_expiration, final_price),
            )
            return cursor.fetchone() is not None

    def mark_posted(self, appid: int, discount_expiration: int, final_price: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO posted_deals(appid, discount_expiration, final_price)
                VALUES (?, ?, ?)
                """,
                (appid, discount_expiration, final_price),
            )
            conn.commit()
