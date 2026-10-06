import os
import sqlite3
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


DB_PATH = os.getenv("DB_PATH", "data/borrows.db")

BOOK_URL = os.getenv("BOOK_SERVICE_URL", "http://127.0.0.1:8001")
MEMBER_URL = os.getenv("MEMBER_SERVICE_URL", "http://127.0.0.1:8002")
NOTIFY_URL = os.getenv(
    "NOTIFICATION_SERVICE_URL",
    "http://127.0.0.1:8004",
)

client = httpx.Client(timeout=5.0)


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS borrows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                borrowed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                returned_at TEXT
            )
            """
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    client.close()


app = FastAPI(
    title="Borrow Service",
    version="1.0",
    lifespan=lifespan,
)


class BorrowIn(BaseModel):
    member_id: int
    book_id: int


def call(method, url, **kwargs):
    try:
        return client.request(method, url, **kwargs)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach service: {exc.__class__.__name__}",
        )


def fetch_book(book_id):
    response = call(
        "GET",
        f"{BOOK_URL}/books/{book_id}",
    )

    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Book not found",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Book Service returned an error",
        )

    return response.json()


def fetch_member(member_id):
    response = call(
        "GET",
        f"{MEMBER_URL}/members/{member_id}",
    )

    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Member not found",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Member Service returned an error",
        )

    return response.json()


def set_book_available(book_id, available):
    response = call(
        "PATCH",
        f"{BOOK_URL}/books/{book_id}/availability",
        json={"available": available},
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Book Service could not update availability",
        )

    return response.json()


def notify(member_id, message):
    try:
        response = client.post(
            f"{NOTIFY_URL}/notifications",
            json={
                "member_id": member_id,
                "message": message,
            },
        )

        response.raise_for_status()
        return response.json()["message"]

    except httpx.HTTPError:
        return "Not sent (Notification Service unavailable)"


@app.get("/health")
def health():
    return {
        "service": "borrow-service",
        "status": "healthy",
    }


@app.get("/services/status")
def services_status():
    services = {
        "book": BOOK_URL,
        "member": MEMBER_URL,
        "notification": NOTIFY_URL,
    }

    result = {}

    for name, url in services.items():
        try:
            response = client.get(
                f"{url}/health",
                timeout=2.0,
            )

            result[name] = (
                "healthy"
                if response.status_code == 200
                else "unhealthy"
            )

        except httpx.RequestError:
            result[name] = "unhealthy"

    return result


@app.get("/borrow/check")
def check_borrow(member_id: int, book_id: int):
    member = fetch_member(member_id)
    book = fetch_book(book_id)

    can_borrow = (
        member["active"]
        and book["available"]
    )

    return {
        "member": member["name"],
        "book": book["title"],
        "member_active": member["active"],
        "book_available": book["available"],
        "can_borrow": can_borrow,
    }


@app.post("/borrow", status_code=201)
def borrow_book(req: BorrowIn):
    member = fetch_member(req.member_id)

    if not member["active"]:
        raise HTTPException(
            status_code=400,
            detail="Member is not active",
        )

    book = fetch_book(req.book_id)

    if not book["available"]:
        raise HTTPException(
            status_code=409,
            detail="Book is already borrowed",
        )

    set_book_available(req.book_id, False)

    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO borrows (member_id, book_id)
            VALUES (?, ?)
            """,
            (req.member_id, req.book_id),
        )

        borrow_id = cursor.lastrowid

    message = notify(
        req.member_id,
        f"You borrowed '{book['title']}'",
    )

    return {
        "borrow_id": borrow_id,
        "member": member["name"],
        "book": book["title"],
        "notification": message,
    }


@app.post("/return/{borrow_id}")
def return_book(borrow_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM borrows WHERE id = ?",
            (borrow_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Borrow record not found",
        )

    if row["returned_at"] is not None:
        raise HTTPException(
            status_code=409,
            detail="Book is already returned",
        )

    book = fetch_book(row["book_id"])

    set_book_available(row["book_id"], True)

    with get_db() as conn:
        conn.execute(
            """
            UPDATE borrows
            SET returned_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (borrow_id,),
        )

    message = notify(
        row["member_id"],
        f"You returned '{book['title']}'",
    )

    return {
        "borrow_id": borrow_id,
        "book": book["title"],
        "notification": message,
    }


@app.get("/borrows")
def list_borrows():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM borrows
            ORDER BY id
            """
        ).fetchall()

    return [dict(row) for row in rows]