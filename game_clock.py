"""
Game Clock for Historical Stock Market Simulator
Manages time progression and broadcasting
"""

import threading
import time
import calendar
from datetime import datetime, timedelta
from typing import Dict, Callable, Optional
from data_engine import data_engine


class GameClock:
    """Manages the game clock and time progression"""
    
    # Dynamic Time Dilation
    BASE_SPEED = 1.0  # Normal mode interval
    MONTHS_PER_TICK = 3
    NORMAL_SECONDS_PER_TICK = BASE_SPEED  # 1.0 seconds in normal mode
    DOWN_MARKET_SECONDS_PER_TICK = 1.35
    
    def __init__(self, room_code: str):
        self.room_code = room_code
        self.current_date: str = '1920-01-01'
        self.game_state: str = 'paused'
        self._timer: Optional[threading.Thread] = None
        self._running: bool = False
        self._broadcast_callback: Optional[Callable] = None
        self._sp500_notified: bool = False
        self.panic_mode: bool = False
        self._current_tick_interval: float = self.NORMAL_SECONDS_PER_TICK
        self._last_dow_price: Optional[float] = None
    
    def set_broadcast_callback(self, callback: Callable):
        """Set the callback function for broadcasting updates"""
        self._broadcast_callback = callback
    
    def start(self):
        """Start the game clock"""
        if self._running:
            return
        
        self._running = True
        self._timer = threading.Thread(target=self._run_clock, daemon=True)
        self._timer.start()
    
    def stop(self):
        """Stop the game clock"""
        self._running = False
        if self._timer:
            self._timer.join(timeout=2)
    
    def _run_clock(self):
        """Main clock loop - runs in separate thread"""
        while self._running:
            tick_started_at = time.monotonic()
            try:
                if self.game_state == 'playing':
                    previous_date = self.current_date
                    previous_price = data_engine.get_price('^DJI', self.current_date)
                    self._advance_time()
                    current_price = data_engine.get_price('^DJI', self.current_date)
                    self._update_panic_mode(previous_price, current_price)

                    # Check for S&P 500 launch notification
                    if not self._sp500_notified and self.current_date >= '1957-03-01':
                        self._sp500_notified = True
                        # Import socketio here to avoid circular import
                        from app import socketio
                        socketio.emit('market_event', {
                            'type': 'sp500_launch',
                            'message': 'S&P 500 Launched!',
                            'date': self.current_date
                        }, room=self.room_code)

                    # Broadcast game state updates for the room
                    if self._broadcast_callback:
                        self._broadcast_callback(self.room_code)
                        # Throttle emissions to reduce stutter
                        from app import socketio
                        socketio.sleep(0.5)
            except Exception as e:
                # Keep clock thread alive if a broadcast or emit fails transiently.
                print(f"Clock loop error in room {self.room_code}: {e}")

            elapsed = time.monotonic() - tick_started_at
            time.sleep(max(0, self._current_tick_interval - elapsed))
    
    def _advance_time(self):
        """Advance time by approximately three calendar months."""
        current = datetime.strptime(self.current_date, '%Y-%m-%d')

        # Move ahead by fixed month increments (presentation compression mode).
        month_index = (current.month - 1) + self.MONTHS_PER_TICK
        year = current.year + (month_index // 12)
        month = (month_index % 12) + 1
        day = min(current.day, calendar.monthrange(year, month)[1])
        next_day = current.replace(year=year, month=month, day=day)

        # Skip weekends (Saturday=5, Sunday=6)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        
        # Check if we have data for this date
        max_date = data_engine.get_date_range()[1]
        next_date_str = next_day.strftime('%Y-%m-%d')

        # Allow game to continue indefinitely - remove hard end date check
        self.current_date = next_date_str

    def _update_panic_mode(self, previous_price: Optional[float], current_price: Optional[float]):
        if previous_price is None or current_price is None or previous_price <= 0:
            return

        change = (current_price - previous_price) / previous_price
        self.panic_mode = change < 0
        self._current_tick_interval = self.DOWN_MARKET_SECONDS_PER_TICK if change < 0 else self.NORMAL_SECONDS_PER_TICK


    def set_date(self, date: str):
        """Set the current game date"""
        # Validate date is within bounds
        min_date, max_date = data_engine.get_date_range()
        
        if date < min_date:
            date = min_date
        elif date > max_date:
            date = max_date
        
        self.current_date = date
    
    def set_state(self, state: str):
        """Set the game state (paused/playing)"""
        self.game_state = state
        if state == 'playing':
            self.awaiting_resume = False
        
        if state == 'playing' and not self._running:
            self.start()
        elif state == 'paused' and self._running:
            self.stop()
    
    def get_state(self) -> Dict:
        """Get current clock state"""
        prices = data_engine.get_all_prices(self.current_date)
        return {
            'current_date': self.current_date,
            'game_state': self.game_state,
            'prices': prices
        }
    
    def reset(self, start_date: str):
        """Reset the clock to start date"""
        self.stop()
        self.current_date = start_date
        self.game_state = 'paused'
        self._running = False
        self._sp500_notified = False


# Global clock manager
class ClockManager:
    """Manages multiple game clocks (one per room)"""
    
    def __init__(self):
        self._clocks: Dict[str, GameClock] = {}
    
    def get_clock(self, room_code: str) -> GameClock:
        """Get or create a clock for a room"""
        if room_code not in self._clocks:
            self._clocks[room_code] = GameClock(room_code)
        return self._clocks[room_code]
    
    def remove_clock(self, room_code: str):
        """Remove a clock when room is deleted"""
        if room_code in self._clocks:
            self._clocks[room_code].stop()
            del self._clocks[room_code]


# Global clock manager instance
clock_manager = ClockManager()