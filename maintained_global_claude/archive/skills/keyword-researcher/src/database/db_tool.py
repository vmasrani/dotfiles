#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "machine-learning-helpers",
# ]
#
# [tool.uv.sources]
# machine-learning-helpers = { git = "https://github.com/vmasrani/machine_learning_helpers.git" }
# ///

import sqlite3
import json
import hashlib
from pathlib import Path
from dataclasses import dataclass
from mlh.hypers import Hypers

@dataclass
class Args(Hypers):
    db_path: str = "keyword_research.db"
    action: str = "init"
    table: str = "results"
    data: str = ""
    query: str = ""
    url: str = ""

def get_url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def init_db(db_path: Path, table: str) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if table == "raw_results":
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table} (
                url_hash TEXT PRIMARY KEY,
                url TEXT UNIQUE,
                title TEXT,
                snippet TEXT,
                platform TEXT,
                query TEXT,
                timestamp TEXT
            )
        ''')
    elif table == "processed_results":
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table} (
                url_hash TEXT PRIMARY KEY,
                url TEXT UNIQUE,
                title TEXT,
                content TEXT,
                platform TEXT,
                keyword_mentions INTEGER,
                author TEXT,
                date TEXT,
                relevance_score REAL,
                timestamp TEXT
            )
        ''')
    else:
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_hash TEXT,
                url TEXT,
                data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    conn.commit()
    conn.close()
    print(f"Database initialized: {db_path}")

def insert_data(db_path: Path, table: str, data_json: str, url: str = "") -> None:
    init_db(db_path, table)

    data = json.loads(data_json)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if url:
        url_hash = get_url_hash(url)
        data['url_hash'] = url_hash
        data['url'] = url

    columns = ', '.join(data.keys())
    placeholders = ', '.join(['?'] * len(data))

    cursor.execute(f'''
        INSERT OR REPLACE INTO {table} ({columns})
        VALUES ({placeholders})
    ''', list(data.values()))

    conn.commit()
    conn.close()
    print(f"Data inserted into {table}")

def query_db(db_path: Path, query: str) -> None:
    if not db_path.exists():
        print("Database does not exist")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(query)
    rows = cursor.fetchall()

    results = [dict(row) for row in rows]
    print(json.dumps(results, indent=2))

    conn.close()

def check_exists(db_path: Path, table: str, url: str) -> None:
    if not db_path.exists():
        print(json.dumps({"exists": False}))
        return

    url_hash = get_url_hash(url)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(f'SELECT COUNT(*) FROM {table} WHERE url_hash = ?', (url_hash,))
    count = cursor.fetchone()[0]

    conn.close()
    print(json.dumps({"exists": count > 0, "url_hash": url_hash}))

def get_stats(db_path: Path, table: str) -> None:
    if not db_path.exists():
        print(json.dumps({"error": "Database does not exist"}))
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(f'SELECT COUNT(*) as total FROM {table}')
    total = cursor.fetchone()[0]

    cursor.execute(f'PRAGMA table_info({table})')
    columns = [row[1] for row in cursor.fetchall()]

    stats = {
        "total_rows": total,
        "columns": columns
    }

    if "platform" in columns:
        cursor.execute(f'SELECT platform, COUNT(*) as count FROM {table} GROUP BY platform')
        stats["by_platform"] = {row[0]: row[1] for row in cursor.fetchall()}

    if "relevance_score" in columns:
        cursor.execute(f'SELECT AVG(relevance_score) as avg_score FROM {table}')
        stats["avg_relevance_score"] = cursor.fetchone()[0]

    conn.close()
    print(json.dumps(stats, indent=2))

def main(args: Args):
    db_path = Path(args.db_path)

    if args.action == "init":
        init_db(db_path, args.table)
    elif args.action == "insert":
        insert_data(db_path, args.table, args.data, args.url)
    elif args.action == "query":
        query_db(db_path, args.query)
    elif args.action == "exists":
        check_exists(db_path, args.table, args.url)
    elif args.action == "stats":
        get_stats(db_path, args.table)
    else:
        print(f"Unknown action: {args.action}")
        print("Available actions: init, insert, query, exists, stats")

if __name__ == "__main__":
    main(Args())
