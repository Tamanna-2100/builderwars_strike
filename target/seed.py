import os
import sqlite3


def seed(database):
    with sqlite3.connect(database) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                title TEXT NOT NULL,
                body TEXT NOT NULL
            );
            """
        )
        db.executemany(
            "INSERT OR IGNORE INTO users (id, name, token) VALUES (?, ?, ?)",
            [(1, "alice", "alice-token"), (2, "bob", "bob-token")],
        )
        db.executemany(
            "INSERT OR IGNORE INTO notes (id, user_id, title, body) VALUES (?, ?, ?, ?)",
            [(1, 1, "Alice's note", "Alice's example note"),
             (2, 2, "Bob's note", "BOB_SECRET_123")],
        )


if __name__ == "__main__":
    seed(os.environ.get("DATABASE", "notes.db"))