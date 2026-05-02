import os
import psycopg2
import psycopg2.extras
from typing import Optional, List, Any

# Get the database URL from environment variables
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set. Please configure it in Vercel or your .env file.")
    
    # Connect to the Postgres database
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db() -> None:
    """Initialize the database tables if they don't exist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Postgres uses SERIAL for auto-incrementing IDs
            cur.execute(
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
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    completed BOOLEAN NOT NULL DEFAULT FALSE,
                    due_date TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        conn.commit()


def create_user(username: str, email: Optional[str], password_hash: str) -> Any:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, username, email, created_at
                """,
                (username, email, password_hash),
            )
            user = cur.fetchone()
            conn.commit()
            if user is None:
                raise RuntimeError("Created user could not be loaded")
            return user


def get_user_by_username(username: str) -> Optional[Any]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT id, username, email, password_hash, created_at FROM users WHERE username = %s",
                (username,),
            )
            return cur.fetchone()


def get_user_by_id(user_id: int) -> Optional[Any]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT id, username, email, created_at FROM users WHERE id = %s",
                (user_id,),
            )
            return cur.fetchone()


def create_todo(user_id: int, title: str, due_date: Optional[str] = None) -> Any:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                INSERT INTO todos (user_id, title, completed, due_date) 
                VALUES (%s, %s, FALSE, %s) 
                RETURNING id, user_id, title, completed, due_date
                """,
                (user_id, title, due_date),
            )
            todo = cur.fetchone()
            conn.commit()
            if todo is None:
                raise RuntimeError("Created todo could not be loaded")
            return todo


def get_todos_by_user(user_id: int) -> List[Any]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT id, user_id, title, completed, due_date FROM todos WHERE user_id = %s ORDER BY id DESC",
                (user_id,),
            )
            return cur.fetchall()


def update_todo(user_id: int, todo_id: int, title: Optional[str] = None, completed: Optional[bool] = None, due_date: Optional[str] = None) -> Optional[Any]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM todos WHERE id = %s AND user_id = %s", (todo_id, user_id))
            todo = cur.fetchone()
            if not todo:
                return None
            
            new_title = title if title is not None else todo["title"]
            new_completed = completed if completed is not None else todo["completed"]
            
            if due_date == "":
                new_due_date = None
            else:
                new_due_date = due_date if due_date is not None else todo["due_date"]
            
            cur.execute(
                """
                UPDATE todos 
                SET title = %s, completed = %s, due_date = %s 
                WHERE id = %s AND user_id = %s
                RETURNING id, user_id, title, completed, due_date
                """,
                (new_title, new_completed, new_due_date, todo_id, user_id),
            )
            updated_todo = cur.fetchone()
            conn.commit()
            return updated_todo


def delete_todo(user_id: int, todo_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM todos WHERE id = %s AND user_id = %s",
                (todo_id, user_id)
            )
            conn.commit()
            return cur.rowcount > 0
