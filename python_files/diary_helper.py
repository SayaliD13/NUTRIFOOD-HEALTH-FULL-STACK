
from datetime import datetime


def add_note(conn, username, note_text, mood):
    conn.execute(
        'INSERT INTO diary_notes (username, note_text, mood, date_added) VALUES (?, ?, ?, ?)',
        (username, note_text, mood, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()


def get_notes(conn, username):
    return conn.execute(
        'SELECT * FROM diary_notes WHERE username = ? ORDER BY id DESC', (username,)
    ).fetchall()


def delete_note(conn, username, note_id):
    conn.execute('DELETE FROM diary_notes WHERE id = ? AND username = ?', (note_id, username))
    conn.commit()
