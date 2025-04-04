# database.py
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

DB_FILE = Path("chats.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Create chats table (unchanged)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Create messages table with attachment_paths (JSON TEXT)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'model', 'error', 'system')),
            content TEXT NOT NULL,
            attachment_paths TEXT NULL, -- Store JSON list of paths
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats (chat_id) ON DELETE CASCADE
        )
    """)
    try:
        cursor.execute("SELECT attachment_path FROM messages LIMIT 1")
        try:
            cursor.execute("SELECT attachment_paths FROM messages LIMIT 1")
            print("Warning: Both 'attachment_path' and 'attachment_paths' columns exist.")
        except sqlite3.OperationalError:
            print("Renaming 'attachment_path' column to 'attachment_paths'...")
            cursor.execute("ALTER TABLE messages RENAME COLUMN attachment_path TO attachment_paths")
            print("Column renamed.")
    except sqlite3.OperationalError:
        try:
            cursor.execute("SELECT attachment_paths FROM messages LIMIT 1")
        except sqlite3.OperationalError:
            print("Error: Could not find or create 'attachment_paths' column.")

    conn.commit()
    conn.close()
    print("Database initialized.")

def create_new_chat(title: str = "New Chat") -> int:
    # (Unchanged)
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("INSERT INTO chats (title) VALUES (?)", (title,))
    chat_id = cursor.lastrowid; conn.commit(); conn.close()
    print(f"Created new chat with ID: {chat_id}"); return chat_id

def add_message_to_chat(chat_id: int, role: str, content: str, attachment_paths: List[str] | None = None):
    conn = get_db_connection(); cursor = conn.cursor()
    # Convert list of paths to JSON string, or None if list is empty/None
    paths_json = json.dumps(attachment_paths) if attachment_paths else None
    try:
        cursor.execute(
            "INSERT INTO messages (chat_id, role, content, attachment_paths) VALUES (?, ?, ?, ?)",
            (chat_id, role, content, paths_json) # Pass JSON string
        )
        conn.commit()
        print(f"Added message for chat {chat_id}. Role: {role}, Attachments JSON: {paths_json}") # Log saved paths
    except Exception as e:
        print(f"Error adding message to database: {e}")
        conn.rollback() # Rollback on error
    finally:
        conn.close()


# MODIFIED: Retrieve JSON paths and parse back to list
def get_chat_history(chat_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection(); cursor = conn.cursor()
    # Select the new column name
    cursor.execute(
        "SELECT role, content, attachment_paths FROM messages WHERE chat_id = ? ORDER BY timestamp ASC",
        (chat_id,)
    )
    history = []
    for row in cursor.fetchall():
        paths_json = row["attachment_paths"]
        attachment_paths_list = []
        if paths_json:
            try:
                # Parse JSON string back to list
                loaded_list = json.loads(paths_json)
                # Ensure it's actually a list of strings (basic check)
                if isinstance(loaded_list, list) and all(isinstance(p, str) for p in loaded_list):
                    attachment_paths_list = loaded_list
                else:
                     print(f"Warning: Parsed attachment_paths is not a list of strings: {loaded_list}")
            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse attachment_paths JSON for message: {e}. JSON: '{paths_json}'")
            except Exception as e:
                 print(f"Warning: Unexpected error parsing attachment_paths: {e}")

        history.append({
            "role": row["role"],
            "parts": [row["content"]], # API history usually just needs text
            "attachment_paths": attachment_paths_list # Add the parsed list
        })
    conn.close()
    return history

# (get_all_chats, update_chat_title, delete_chat - unchanged)
def get_all_chats() -> List[Tuple[int, str, str]]:
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("SELECT chat_id, title, created_at FROM chats ORDER BY created_at DESC")
    chats = [(row["chat_id"], row["title"], row["created_at"]) for row in cursor.fetchall()]
    conn.close(); return chats

def update_chat_title(chat_id: int, new_title: str):
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE chats SET title = ? WHERE chat_id = ?", (new_title, chat_id))
    conn.commit(); conn.close(); print(f"Updated title for chat {chat_id} to '{new_title}'")

def delete_chat(chat_id: int):
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
    conn.commit(); conn.close(); print(f"Deleted chat with ID: {chat_id}")