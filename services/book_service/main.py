import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


DB_PATH = os.getenv("DB_PATH", "data/books.db")


SEED_BOOKS = [
    ("The Alchemist", "Paulo Coelho"),
    ("1984", "George Orwell"),
    ("To Kill a Mockingbird", "Harper Lee"),
    ("The Great Gatsby", "F. Scott Fitzgerald"),
    ("Pride and Prejudice", "Jane Austen"),
    ("The Hobbit", "J.R.R. Tolkien"),
    ("Harry Potter", "J.K. Rowling"),
    ("The Kite Runner", "Khaled Hosseini"),
    ("Atomic Habits", "James Clear"),
    ("The Book Thief", "Markus Zusak"),
]


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_book(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "author": row["author"],
        "available": bool(row["available"]),
    }


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                available INTEGER NOT NULL DEFAULT 1
            )
            """
        )

        count = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]

        if count == 0:
            conn.executemany(
                "INSERT INTO books (title, author) VALUES (?, ?)",
                SEED_BOOKS,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Book Service",
    version="1.0",
    lifespan=lifespan,
)


class BookIn(BaseModel):
    title: str
    author: str


class AvailabilityIn(BaseModel):
    available: bool


@app.get("/health")
def health():
    return {
        "service": "book-service",
        "status": "healthy",
    }


@app.get("/books")
def list_books():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM books ORDER BY id"
        ).fetchall()

    return [row_to_book(row) for row in rows]


@app.post("/books")
def add_book(book: BookIn):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO books (title, author, available) VALUES (?, ?, 1)",
            (book.title, book.author),
        )
        book_id = cursor.lastrowid

    return get_book(book_id)


@app.get("/books/{book_id}")
def get_book(book_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM books WHERE id = ?",
            (book_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Book not found",
        )

    return row_to_book(row)


@app.patch("/books/{book_id}/availability")
def set_availability(book_id: int, body: AvailabilityIn):
    get_book(book_id)

    with get_db() as conn:
        conn.execute(
            "UPDATE books SET available = ? WHERE id = ?",
            (int(body.available), book_id),
        )

    return get_book(book_id)