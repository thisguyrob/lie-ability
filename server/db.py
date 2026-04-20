from __future__ import annotations
import json
import os
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "questions.db"
SEED_PATH = Path(__file__).parent.parent / "data" / "seed.json"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    try:
        conn.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS categories (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS questions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id  INTEGER NOT NULL REFERENCES categories(id),
                prompt       TEXT NOT NULL,
                answer       TEXT NOT NULL,
                group_name   TEXT,
                used_count   INTEGER DEFAULT 0,
                last_used_at TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS question_lies (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL REFERENCES questions(id),
                text        TEXT NOT NULL
            );
        """)
        conn.commit()

        row = conn.execute("SELECT COUNT(*) FROM categories").fetchone()
        if row[0] == 0 and SEED_PATH.exists():
            _seed_from_json(conn)
    finally:
        conn.close()


def _seed_from_json(conn: sqlite3.Connection) -> None:
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)

    category_ids: dict[str, int] = {}

    for entry in entries:
        cat_name = entry["category"]
        if cat_name not in category_ids:
            cur = conn.execute(
                "INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat_name,)
            )
            conn.commit()
            row = conn.execute("SELECT id FROM categories WHERE name = ?", (cat_name,)).fetchone()
            category_ids[cat_name] = row["id"]

        cat_id = category_ids[cat_name]
        cur = conn.execute(
            "INSERT INTO questions (category_id, prompt, answer, group_name) VALUES (?, ?, ?, ?)",
            (cat_id, entry["question"], entry["answer"], entry.get("group")),
        )
        q_id = cur.lastrowid
        for lie_text in entry.get("lies", []):
            conn.execute(
                "INSERT INTO question_lies (question_id, text) VALUES (?, ?)",
                (q_id, lie_text),
            )

    conn.commit()


# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

def get_categories(included_groups: list[str] | None = None) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT c.id, c.name,
                   COUNT(q.id) AS question_count
            FROM categories c
            LEFT JOIN questions q ON q.category_id = c.id
            GROUP BY c.id, c.name
            ORDER BY c.name
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_groups() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT COALESCE(group_name, '__ungrouped__') AS name,
                   COUNT(*) AS question_count
            FROM questions
            GROUP BY group_name
            ORDER BY group_name
        """).fetchall()
        result = []
        for r in rows:
            result.append({
                "name": "Ungrouped" if r["name"] == "__ungrouped__" else r["name"],
                "question_count": r["question_count"],
            })
        return result
    finally:
        conn.close()


def get_random_question(
    category_id: int,
    exclude_ids: set[int],
    player_histories: list[dict[str, str]],
    included_groups: list[str] | None = None,
) -> dict | None:
    conn = _connect()
    try:
        placeholders = ",".join("?" * len(exclude_ids)) if exclude_ids else "NULL"
        group_clause = ""
        params: list = [category_id]

        if included_groups is not None:
            group_ph = ",".join("?" * len(included_groups))
            group_clause = f"AND (group_name IN ({group_ph}) OR group_name IS NULL)"
            params.extend(included_groups)

        if exclude_ids:
            params.extend(list(exclude_ids))
            exclude_clause = f"AND id NOT IN ({placeholders})"
        else:
            exclude_clause = ""

        rows = conn.execute(f"""
            SELECT id, prompt, answer, group_name, last_used_at
            FROM questions
            WHERE category_id = ?
            {group_clause}
            {exclude_clause}
            ORDER BY last_used_at ASC NULLS FIRST
        """, params).fetchall()

        if not rows:
            return None

        candidates = [dict(r) for r in rows]
        weights = [_question_weight(c, player_histories) for c in candidates]
        chosen = random.choices(candidates, weights=weights, k=1)[0]

        lies_rows = conn.execute(
            "SELECT text FROM question_lies WHERE question_id = ? ORDER BY RANDOM()",
            (chosen["id"],),
        ).fetchall()
        chosen["lies"] = [r["text"] for r in lies_rows]

        return chosen
    finally:
        conn.close()


def _question_weight(question: dict, player_histories: list[dict[str, str]]) -> float:
    qid = str(question["id"])
    wrong = sum(1 for h in player_histories if h.get(qid) == "incorrect")
    seen_correct = sum(1 for h in player_histories if h.get(qid) == "correct")
    total_seen = wrong + seen_correct

    if total_seen == 0:
        return 3.0
    if wrong > 0:
        return 2.0 + (wrong / max(total_seen, 1))
    return 1.0


def mark_questions_used(question_ids: list[int]) -> None:
    if not question_ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        for qid in question_ids:
            conn.execute(
                "UPDATE questions SET used_count = used_count + 1, last_used_at = ? WHERE id = ?",
                (now, qid),
            )
        conn.commit()
    finally:
        conn.close()
