"""
Memory Management System for Smart Assistant
Handles persistent storage, context management, and learning capabilities
"""

import sqlite3
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class MemoryManager:
    """Manages persistent memory and context for the smart assistant"""
    
    def __init__(self, db_path: str = "memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the memory database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Conversations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        user_input TEXT NOT NULL,
                        assistant_response TEXT NOT NULL,
                        context TEXT,
                        session_id TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # User preferences table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT UNIQUE NOT NULL,
                        value TEXT NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Device states table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS device_states (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_id TEXT NOT NULL,
                        state TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        context TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Learning patterns table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS learning_patterns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pattern_type TEXT NOT NULL,
                        pattern_data TEXT NOT NULL,
                        confidence REAL DEFAULT 0.0,
                        frequency INTEGER DEFAULT 1,
                        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Context sessions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS context_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT UNIQUE NOT NULL,
                        start_time REAL NOT NULL,
                        last_activity REAL NOT NULL,
                        context_data TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                logger.info("Memory database initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing memory database: {e}")
            raise
    
    def store_conversation(self, user_input: str, assistant_response: str, 
                          context: Optional[Dict] = None, session_id: Optional[str] = None) -> int:
        """Store a conversation exchange in memory"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO conversations (timestamp, user_input, assistant_response, context, session_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (time.time(), user_input, assistant_response, 
                      json.dumps(context) if context else None, session_id))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error storing conversation: {e}")
            return -1
    
    def get_recent_conversations(self, limit: int = 10, session_id: Optional[str] = None) -> List[Dict]:
        """Get recent conversations for context"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if session_id:
                    cursor.execute("""
                        SELECT user_input, assistant_response, context, timestamp
                        FROM conversations 
                        WHERE session_id = ?
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (session_id, limit))
                else:
                    cursor.execute("""
                        SELECT user_input, assistant_response, context, timestamp
                        FROM conversations 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (limit,))
                
                conversations = []
                for row in cursor.fetchall():
                    conversations.append({
                        "user_input": row[0],
                        "assistant_response": row[1],
                        "context": json.loads(row[2]) if row[2] else None,
                        "timestamp": row[3]
                    })
                return conversations
        except Exception as e:
            logger.error(f"Error retrieving conversations: {e}")
            return []
    
    def store_user_preference(self, key: str, value: Any) -> bool:
        """Store or update a user preference"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO user_preferences (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, json.dumps(value)))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error storing user preference: {e}")
            return False
    
    def get_user_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM user_preferences WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return default
        except Exception as e:
            logger.error(f"Error retrieving user preference: {e}")
            return default
    
    def store_device_state(self, device_id: str, state: str, context: Optional[Dict] = None) -> bool:
        """Store device state change"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO device_states (device_id, state, timestamp, context)
                    VALUES (?, ?, ?, ?)
                """, (device_id, state, time.time(), 
                      json.dumps(context) if context else None))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error storing device state: {e}")
            return False
    
    def get_device_history(self, device_id: str, hours: int = 24) -> List[Dict]:
        """Get device state history"""
        try:
            cutoff_time = time.time() - (hours * 3600)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT state, timestamp, context
                    FROM device_states 
                    WHERE device_id = ? AND timestamp > ?
                    ORDER BY timestamp DESC
                """, (device_id, cutoff_time))
                
                history = []
                for row in cursor.fetchall():
                    history.append({
                        "state": row[0],
                        "timestamp": row[1],
                        "context": json.loads(row[2]) if row[2] else None
                    })
                return history
        except Exception as e:
            logger.error(f"Error retrieving device history: {e}")
            return []
    
    def learn_pattern(self, pattern_type: str, pattern_data: Dict, confidence: float = 1.0) -> bool:
        """Learn and store a pattern for future reference"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if pattern already exists
                cursor.execute("""
                    SELECT id, frequency FROM learning_patterns 
                    WHERE pattern_type = ? AND pattern_data = ?
                """, (pattern_type, json.dumps(pattern_data)))
                
                row = cursor.fetchone()
                if row:
                    # Update existing pattern
                    pattern_id, frequency = row
                    new_confidence = (confidence + (row[2] * frequency)) / (frequency + 1)
                    cursor.execute("""
                        UPDATE learning_patterns 
                        SET confidence = ?, frequency = frequency + 1, last_seen = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (new_confidence, pattern_id))
                else:
                    # Insert new pattern
                    cursor.execute("""
                        INSERT INTO learning_patterns (pattern_type, pattern_data, confidence)
                        VALUES (?, ?, ?)
                    """, (pattern_type, json.dumps(pattern_data), confidence))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error learning pattern: {e}")
            return False
    
    def get_learned_patterns(self, pattern_type: Optional[str] = None, 
                           min_confidence: float = 0.5) -> List[Dict]:
        """Get learned patterns"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if pattern_type:
                    cursor.execute("""
                        SELECT pattern_type, pattern_data, confidence, frequency, last_seen
                        FROM learning_patterns 
                        WHERE pattern_type = ? AND confidence >= ?
                        ORDER BY confidence DESC, frequency DESC
                    """, (pattern_type, min_confidence))
                else:
                    cursor.execute("""
                        SELECT pattern_type, pattern_data, confidence, frequency, last_seen
                        FROM learning_patterns 
                        WHERE confidence >= ?
                        ORDER BY confidence DESC, frequency DESC
                    """, (min_confidence,))
                
                patterns = []
                for row in cursor.fetchall():
                    patterns.append({
                        "pattern_type": row[0],
                        "pattern_data": json.loads(row[1]),
                        "confidence": row[2],
                        "frequency": row[3],
                        "last_seen": row[4]
                    })
                return patterns
        except Exception as e:
            logger.error(f"Error retrieving learned patterns: {e}")
            return []
    
    def create_session(self, session_id: str, context_data: Optional[Dict] = None) -> bool:
        """Create a new context session"""
        try:
            current_time = time.time()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO context_sessions 
                    (session_id, start_time, last_activity, context_data, is_active)
                    VALUES (?, ?, ?, ?, 1)
                """, (session_id, current_time, current_time, 
                      json.dumps(context_data) if context_data else None))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return False
    
    def update_session(self, session_id: str, context_data: Optional[Dict] = None) -> bool:
        """Update session activity and context"""
        try:
            current_time = time.time()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE context_sessions 
                    SET last_activity = ?, context_data = ?
                    WHERE session_id = ?
                """, (current_time, json.dumps(context_data) if context_data else None, session_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return False
    
    def get_session_context(self, session_id: str) -> Optional[Dict]:
        """Get context for a session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT context_data FROM context_sessions 
                    WHERE session_id = ? AND is_active = 1
                """, (session_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
                return None
        except Exception as e:
            logger.error(f"Error retrieving session context: {e}")
            return None
    
    def cleanup_old_data(self, days: int = 30) -> bool:
        """Clean up old data to prevent database bloat"""
        try:
            cutoff_time = time.time() - (days * 24 * 3600)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clean old conversations
                cursor.execute("DELETE FROM conversations WHERE timestamp < ?", (cutoff_time,))
                
                # Clean old device states
                cursor.execute("DELETE FROM device_states WHERE timestamp < ?", (cutoff_time,))
                
                # Clean inactive sessions
                cursor.execute("""
                    UPDATE context_sessions 
                    SET is_active = 0 
                    WHERE last_activity < ? AND is_active = 1
                """, (cutoff_time,))
                
                conn.commit()
                logger.info(f"Cleaned up data older than {days} days")
                return True
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            return False
