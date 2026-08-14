"""
該表創建
assets
borrow_records
categories
locations
"""
from pathlib import Path
import sqlite3


DB_PATH = Path("data/lab.db")


def init_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_code TEXT,
            code_type TEXT,
            name TEXT NOT NULL,
            category_id INTEGER,
            location_id INTEGER,
            quantity REAL DEFAULT 0,
            status TEXT,
            specification TEXT,
            note TEXT,
            source_sheet TEXT,
            duplicate_warning INTEGER DEFAULT 0,

            FOREIGN KEY (category_id)
                REFERENCES categories(id),

            FOREIGN KEY (location_id)
                REFERENCES locations(id)
        );

        CREATE TABLE IF NOT EXISTS borrow_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_no INTEGER,
            timestamp TEXT,
            borrower_email TEXT,
            handler TEXT,
            item_name TEXT,
            original_asset_code TEXT,
            matched_asset_code TEXT,
            matched_asset_name TEXT,
            match_status TEXT,
            note TEXT,
            quantity REAL,
            quantity_estimated INTEGER DEFAULT 0,
            purpose TEXT,
            usage_location TEXT,
            borrow_date TEXT,
            return_date TEXT,
            returned INTEGER DEFAULT 0,
            original_note TEXT
        );
        """
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_database()
    print("Database initialized.")