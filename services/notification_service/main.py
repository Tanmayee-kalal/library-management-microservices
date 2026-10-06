import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel


DB_PATH = os.getenv(
    "DB_PATH",
    "data/notifications.db",
)


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(
        os.path.dirname(DB_PATH) or ".",
        exist_ok=True,
    )

    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Notification Service",
    version="1.0",
    lifespan=lifespan,
)


class NotificationIn(BaseModel):
    member_id: int
    message: str


@app.get("/health")
def health():
    return {
        "service": "notification-service",
        "status": "healthy",
    }


@app.post("/notifications", status_code=201)
def create_notification(notification: NotificationIn):
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO notifications (member_id, message)
            VALUES (?, ?)
            """,
            (
                notification.member_id,
                notification.message,
            ),
        )

        notification_id = cursor.lastrowid

    return {
        "id": notification_id,
        "member_id": notification.member_id,
        "message": notification.message,
    }


@app.get("/notifications")
def list_notifications(
    member_id: int | None = None,
):
    with get_db() as conn:
        if member_id is None:
            rows = conn.execute(
                """
                SELECT *
                FROM notifications
                ORDER BY id
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT *
                FROM notifications
                WHERE member_id = ?
                ORDER BY id
                """,
                (member_id,),
            ).fetchall()

    return [dict(row) for row in rows]