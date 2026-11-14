import os
import sqlite3

from flask import Flask, g, jsonify, request


app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("DATABASE", "notes.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def current_user():
    token = request.headers.get("X-Token", "")
    return get_db().execute("SELECT id, name FROM users WHERE token = ?", (token,)).fetchone()


@app.get("/notes/<int:note_id>")
def get_note(note_id):
    if current_user() is None:
        return jsonify(error="Unauthorized"), 401
    note = get_db().execute(
        "SELECT id, user_id, title, body FROM notes WHERE id = ?", (note_id,)
    ).fetchone()
    if note is None:
        return jsonify(error="Not found"), 404
    return jsonify(dict(note))


@app.get("/search")
def search():
    user = current_user()
    if user is None:
        return jsonify(error="Unauthorized"), 401
    query = request.args.get("q", "")
    notes = get_db().execute(
        f"SELECT id, user_id, title, body FROM notes WHERE user_id = {user['id']} "
        f"AND (title LIKE '%{query}%' OR body LIKE '%{query}%')"
    ).fetchall()
    return jsonify([dict(note) for note in notes])


@app.get("/admin/users")
def list_users():
    users = get_db().execute("SELECT id, name FROM users ORDER BY id").fetchall()
    return jsonify([dict(user) for user in users])