import os
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional

# Load env vars from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    """Returns a connection to the PostgreSQL database."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    
    # Use DictCursor to emulate the behavior of sqlite3.Row
    # This allows accessing columns by name like row['id']
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
    return conn


def init_db() -> None:
    """Initializes the database schema."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            # Users table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Todos table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    completed BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    due_date TEXT
                )
                """
            )
            connection.commit()


def create_user(username: str, email: Optional[str], password_hash: str):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, username, email, created_at
                """,
                (username, email, password_hash),
            )
            user = cursor.fetchone()
            connection.commit()
            return user


def get_user_by_username(username: str):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, email, password_hash, created_at FROM users WHERE username = %s",
                (username,),
            )
            return cursor.fetchone()


def get_user_by_id(user_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, email, created_at FROM users WHERE id = %s",
                (user_id,),
            )
            return cursor.fetchone()


def create_todo(user_id: int, title: str, due_date: Optional[str] = None):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO todos (user_id, title, completed, due_date)
                VALUES (%s, %s, FALSE, %s)
                RETURNING id, user_id, title, completed, due_date
                """,
                (user_id, title, due_date),
            )
            todo = cursor.fetchone()
            connection.commit()
            return todo


def get_todos_by_user(user_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, user_id, title, completed, due_date FROM todos WHERE user_id = %s ORDER BY id DESC",
                (user_id,),
            )
            return cursor.fetchall()


def update_todo(user_id: int, todo_id: int, title: Optional[str] = None, completed: Optional[bool] = None, due_date: Optional[str] = None):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM todos WHERE id = %s AND user_id = %s", (todo_id, user_id))
            todo = cursor.fetchone()
            if not todo:
                return None
            
            new_title = title if title is not None else todo["title"]
            new_completed = completed if completed is not None else todo["completed"]
            
            if due_date == "":
                new_due_date = None
            else:
                new_due_date = due_date if due_date is not None else todo["due_date"]
            
            cursor.execute(
                """
                UPDATE todos 
                SET title = %s, completed = %s, due_date = %s 
                WHERE id = %s AND user_id = %s 
                RETURNING id, user_id, title, completed, due_date
                """,
                (new_title, new_completed, new_due_date, todo_id, user_id),
            )
            updated = cursor.fetchone()
            connection.commit()
            return updated


def delete_todo(user_id: int, todo_id: int) -> bool:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM todos WHERE id = %s AND user_id = %s",
                (todo_id, user_id)
            )
            connection.commit()
            return cursor.rowcount > 0
