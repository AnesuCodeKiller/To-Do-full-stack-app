import sqlite3
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).resolve().parents[1] / "todo_auth.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                completed BOOLEAN NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        try:
            connection.execute("ALTER TABLE todos ADD COLUMN due_date TEXT")
        except sqlite3.OperationalError:
            pass


def create_user(username: str, email: Optional[str], password_hash: str) -> sqlite3.Row:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (username, email, password_hash),
        )
        user_id = cursor.lastrowid
        user = connection.execute(
            "SELECT id, username, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            raise RuntimeError("Created user could not be loaded")
        return user


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            "SELECT id, username, email, password_hash, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()


def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            "SELECT id, username, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


def create_todo(user_id: int, title: str, due_date: Optional[str] = None) -> sqlite3.Row:
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO todos (user_id, title, completed, due_date) VALUES (?, ?, 0, ?)",
            (user_id, title, due_date),
        )
          
        todo_id = cursor.lastrowid
        todo = connection.execute(
            "SELECT id, user_id, title, completed, due_date FROM todos WHERE id = ?",
            (todo_id,),
        ).fetchone()
        if todo is None:
            raise RuntimeError("Created todo could not be loaded")
        return todo


def get_todos_by_user(user_id: int) -> list[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            "SELECT id, user_id, title, completed, due_date FROM todos WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()


def update_todo(user_id: int, todo_id: int, title: Optional[str] = None, completed: Optional[bool] = None, due_date: Optional[str] = None) -> Optional[sqlite3.Row]:
    with get_connection() as connection:
        todo = connection.execute("SELECT * FROM todos WHERE id = ? AND user_id = ?", (todo_id, user_id)).fetchone()
        if not todo:
            return None
        
        new_title = title if title is not None else todo["title"]
        new_completed = completed if completed is not None else todo["completed"]
        
        if due_date == "":
            new_due_date = None
        else:
            new_due_date = due_date if due_date is not None else todo["due_date"]
        
        connection.execute(
            "UPDATE todos SET title = ?, completed = ?, due_date = ? WHERE id = ? AND user_id = ?",
            (new_title, new_completed, new_due_date, todo_id, user_id),
        )
        
        return connection.execute(
            "SELECT id, user_id, title, completed, due_date FROM todos WHERE id = ?",
            (todo_id,),
        ).fetchone()


def delete_todo(user_id: int, todo_id: int) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM todos WHERE id = ? AND user_id = ?",
            (todo_id, user_id)
        )
        return cursor.rowcount > 0
