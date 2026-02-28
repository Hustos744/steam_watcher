from __future__ import annotations

from contextlib import contextmanager

import psycopg


class StateRepository:
    def __init__(self, database_url: str, retention_days: int = 30):
        self.database_url = database_url
        self.retention_days = retention_days
        self._init_db()

    @contextmanager
    def _connect(self):
        with psycopg.connect(self.database_url) as conn:
            yield conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS posted_deals (
                        appid INTEGER NOT NULL,
                        discount_expiration BIGINT NOT NULL,
                        final_price INTEGER NOT NULL,
                        posted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (appid, discount_expiration, final_price)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS blocked_appids (
                        appid INTEGER PRIMARY KEY,
                        source TEXT NOT NULL,
                        first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            conn.commit()

    def cleanup_expired_records(self) -> tuple[int, int]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM posted_deals
                    WHERE posted_at < NOW() - (%s || ' days')::INTERVAL
                    """,
                    (self.retention_days,),
                )
                posted_deleted = cur.rowcount

                cur.execute(
                    """
                    DELETE FROM blocked_appids
                    WHERE last_seen_at < NOW() - (%s || ' days')::INTERVAL
                    """,
                    (self.retention_days,),
                )
                blocked_deleted = cur.rowcount
            conn.commit()
        return posted_deleted, blocked_deleted

    def was_posted(self, appid: int, discount_expiration: int, final_price: int) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM posted_deals
                    WHERE appid = %s AND discount_expiration = %s AND final_price = %s
                    LIMIT 1
                    """,
                    (appid, discount_expiration, final_price),
                )
                return cur.fetchone() is not None

    def mark_posted(self, appid: int, discount_expiration: int, final_price: int) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO posted_deals(appid, discount_expiration, final_price)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (appid, discount_expiration, final_price) DO NOTHING
                    """,
                    (appid, discount_expiration, final_price),
                )
            conn.commit()

    def upsert_blocked_appids(self, appids: set[int], source: str = "curator") -> int:
        if not appids:
            return 0

        new_count = 0
        with self._connect() as conn:
            with conn.cursor() as cur:
                for appid in appids:
                    cur.execute(
                        """
                        INSERT INTO blocked_appids(appid, source)
                        VALUES (%s, %s)
                        ON CONFLICT (appid) DO NOTHING
                        RETURNING appid
                        """,
                        (appid, source),
                    )
                    if cur.fetchone() is not None:
                        new_count += 1

                    cur.execute(
                        """
                        UPDATE blocked_appids
                        SET last_seen_at = NOW(), source = %s
                        WHERE appid = %s
                        """,
                        (source, appid),
                    )
            conn.commit()
        return new_count

    def get_blocked_appids(self) -> set[int]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT appid FROM blocked_appids")
                rows = cur.fetchall()
                return {int(row[0]) for row in rows}
