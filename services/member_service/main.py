import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


DB_PATH = os.getenv("DB_PATH", "data/members.db")


SEED_MEMBERS = [
    ("Diya Patel", "diya@example.com"),
    ("Arjun Kumar", "arjun@example.com"),
    ("Meera Shah", "meera@example.com"),
    ("Rohan Singh", "rohan@example.com"),
    ("Ananya Rao", "ananya@example.com"),
]


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_member(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "active": bool(row["active"]),
    }


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )

        count = conn.execute(
            "SELECT COUNT(*) FROM members"
        ).fetchone()[0]

        if count == 0:
            conn.executemany(
                "INSERT INTO members (name, email) VALUES (?, ?)",
                SEED_MEMBERS,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Member Service",
    version="1.0",
    lifespan=lifespan,
)


class MemberIn(BaseModel):
    name: str
    email: str


@app.get("/health")
def health():
    return {
        "service": "member-service",
        "status": "healthy",
    }


@app.get("/members")
def list_members():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM members ORDER BY id"
        ).fetchall()

    return [row_to_member(row) for row in rows]


@app.post("/members", status_code=201)
def add_member(member: MemberIn):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO members (name, email, active) VALUES (?, ?, 1)",
            (member.name, member.email),
        )
        member_id = cursor.lastrowid

    return get_member(member_id)


@app.get("/members/{member_id}")
def get_member(member_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM members WHERE id = ?",
            (member_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Member not found",
        )

    return row_to_member(row)