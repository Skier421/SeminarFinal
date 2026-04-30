"""
Database models for Historical Stock Market Simulator
SQLite database for persistent storage
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, Optional, List
import os
import time

DATABASE_FILE = 'stock_simulator.db'
DEFAULT_START_DATE = '1928-01-01'

# Starting cash adjusted for inflation (2026 dollars)
# $100 * 18 = $1,800
DEFAULT_STARTING_CASH = 1800.0


def get_db_connection():
    """Get a database connection"""
    conn = sqlite3.connect(DATABASE_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout = 10000')
    return conn


def init_db():
    """Initialize the database with required tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create rooms table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            code TEXT PRIMARY KEY,
            start_date TEXT NOT NULL,
            current_date TEXT NOT NULL,
            game_state TEXT DEFAULT 'paused',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create players table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            username TEXT NOT NULL,
            cash REAL DEFAULT 100.0,
            holdings TEXT DEFAULT '{}',
            is_admin BOOLEAN DEFAULT FALSE,
            is_insider BOOLEAN DEFAULT FALSE,
            has_had_insider_turn BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (room_code) REFERENCES rooms(code),
            UNIQUE(room_code, username)
        )
    ''')

    # Migrate existing players table if the is_insider column is missing
    cursor.execute("PRAGMA table_info(players)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'is_insider' not in columns:
        cursor.execute('ALTER TABLE players ADD COLUMN is_insider BOOLEAN DEFAULT FALSE')
    if 'has_had_insider_turn' not in columns:
        cursor.execute('ALTER TABLE players ADD COLUMN has_had_insider_turn BOOLEAN DEFAULT FALSE')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully")


class Room:
    """Room model for managing game rooms"""
    
    def __init__(self, code: str, start_date: str):
        self.code = code
        self.start_date = start_date
        self.current_date = start_date
        self.game_state = 'paused'
    
    @staticmethod
    def create(code: str, start_date: str) -> 'Room':
        """Create a new room"""
        start_date = start_date or DEFAULT_START_DATE
        current_date = DEFAULT_START_DATE
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO rooms (code, start_date, current_date, game_state)
            VALUES (?, ?, ?, 'paused')
        ''', (code, start_date, current_date))
        
        conn.commit()
        conn.close()
        
        room = Room(code, start_date)
        room.current_date = current_date
        return room
    
    @staticmethod
    def get(code: str) -> Optional['Room']:
        """Get a room by code"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM rooms WHERE code = ?', (code,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            room = Room(row['code'], row['start_date'])
            room.current_date = row['current_date']
            room.game_state = row['game_state']
            return room
        return None
    
    @staticmethod
    def exists(code: str) -> bool:
        """Check if a room exists"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM rooms WHERE code = ?', (code,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def save(self):
        """Save room state to database"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE rooms 
            SET current_date = ?, game_state = ?
            WHERE code = ?
        ''', (self.current_date, self.game_state, self.code))
        
        conn.commit()
        conn.close()
    
    def update_date(self, new_date: str):
        """Update the current game date"""
        self.current_date = new_date
        self.save()
    
    def set_state(self, state: str):
        """Set the game state (paused/playing)"""
        self.game_state = state
        self.save()
    
    def reset(self):
        """Reset the room to initial state"""
        self.current_date = self.start_date
        self.game_state = 'paused'
        self.save()


class Player:
    """Player model for managing students"""
    
    def __init__(self, room_code: str, username: str, cash: float = 100.0, 
                 holdings: Dict[str, float] = None, is_admin: bool = False,
                 is_insider: bool = False, has_had_insider_turn: bool = False):
        self.room_code = room_code
        self.username = username
        self.cash = cash
        self.holdings = holdings or {}
        self.is_admin = is_admin
        self.is_insider = is_insider
        self.has_had_insider_turn = has_had_insider_turn
    
    @staticmethod
    def create(room_code: str, username: str, is_admin: bool = False, is_insider: bool = False) -> 'Player':
        """Create a new player"""
        max_retries = 5
        base_username = username

        for attempt in range(max_retries):
            conn = None
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('BEGIN IMMEDIATE')

                candidate = base_username
                counter = 1

                # Find a unique username while holding a write lock to avoid races.
                while True:
                    cursor.execute('''
                        SELECT 1 FROM players
                        WHERE room_code = ? AND username = ?
                    ''', (room_code, candidate))
                    if not cursor.fetchone():
                        break
                    candidate = f"{base_username}{counter}"
                    counter += 1

                cursor.execute('''
                    INSERT INTO players (room_code, username, cash, holdings, is_admin, is_insider, has_had_insider_turn)
                    VALUES (?, ?, 1800.0, '{}', ?, ?, FALSE)
                ''', (room_code, candidate, is_admin, is_insider))
                conn.commit()
                return Player(room_code, candidate, 1800.0, {}, is_admin, is_insider, False)
            except sqlite3.OperationalError as e:
                if conn:
                    conn.rollback()
                if 'locked' in str(e).lower() and attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
                    continue
                raise
            finally:
                if conn:
                    conn.close()

        raise RuntimeError('Unable to create player after retries')
    
    @staticmethod
    def get(room_code: str, username: str) -> Optional['Player']:
        """Get a player by room and username"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM players 
            WHERE room_code = ? AND username = ?
        ''', (room_code, username))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            player = Player(
                row['room_code'], 
                row['username'], 
                row['cash'],
                json.loads(row['holdings']),
                row['is_admin'],
                bool(row['is_insider']) if 'is_insider' in row.keys() else False,
                bool(row['has_had_insider_turn']) if 'has_had_insider_turn' in row.keys() else False
            )
            player.id = row['id']
            return player
        return None
    
    @staticmethod
    def get_all_in_room(room_code: str) -> List['Player']:
        """Get all players in a room"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM players WHERE room_code = ?
        ''', (room_code,))
        
        rows = cursor.fetchall()
        conn.close()
        
        players = []
        for row in rows:
            player = Player(
                row['room_code'],
                row['username'],
                row['cash'],
                json.loads(row['holdings']),
                row['is_admin'],
                bool(row['is_insider']) if 'is_insider' in row.keys() else False,
                bool(row['has_had_insider_turn']) if 'has_had_insider_turn' in row.keys() else False
            )
            player.id = row['id']
            players.append(player)
        
        return players
    
    def save(self):
        """Save player state to database"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE players 
            SET cash = ?, holdings = ?, is_admin = ?, is_insider = ?, has_had_insider_turn = ?
            WHERE room_code = ? AND username = ?
        ''', (
            self.cash,
            json.dumps(self.holdings),
            self.is_admin,
            self.is_insider,
            self.has_had_insider_turn,
            self.room_code,
            self.username
        ))
        
        conn.commit()
        conn.close()
    
    def buy(self, ticker: str, shares: float, price: float, amount: float = None) -> bool:
        """Buy shares of a stock"""
        cost = float(amount) if amount is not None else shares * price
        if cost - self.cash > 1e-9:
            return False
        
        self.cash -= cost
        self.holdings[ticker] = self.holdings.get(ticker, 0) + shares
        self.save()
        return True
    
    def sell(self, ticker: str, shares: float, price: float) -> bool:
        """Sell shares of a stock"""
        current_shares = self.holdings.get(ticker, 0)
        if shares > current_shares:
            return False
        
        self.cash += shares * price
        self.holdings[ticker] = current_shares - shares
        if self.holdings[ticker] <= 0:
            del self.holdings[ticker]
        self.save()
        return True

    def set_insider(self, value: bool):
        """Mark or unmark the player as an insider."""
        self.is_insider = value
        self.save()
    
    def get_net_worth(self, prices: Dict[str, float]) -> float:
        """Calculate total net worth - fresh calculation each time"""
        # Reset holdings_value to ensure no running total accumulation
        holdings_value = 0.0
        for ticker, shares in self.holdings.items():
            if ticker in prices:
                holdings_value = holdings_value + (shares * prices[ticker])
        return self.cash + holdings_value
    
    def reset(self):
        """Reset player to initial state"""
        self.cash = 1800.0
        self.holdings = {}
        self.is_insider = False
        self.has_had_insider_turn = False
        self.save()
    
    def to_dict(self, prices: Dict[str, float] = None) -> dict:
        """Convert player to dictionary"""
        net_worth = self.get_net_worth(prices) if prices else self.cash
        return {
            'username': self.username,
            'cash': self.cash,
            'holdings': self.holdings,
            'net_worth': net_worth,
            'is_admin': self.is_admin,
            'is_insider': self.is_insider,
            'has_had_insider_turn': self.has_had_insider_turn
        }


# Initialize database on module import
init_db()