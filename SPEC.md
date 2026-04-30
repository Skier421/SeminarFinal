# Historical Stock Market Simulator - Specification

## Project Overview
- **Project Name**: Historical Stock Market Simulator
- **Type**: Real-time multiplayer web application
- **Core Functionality**: A classroom trading simulation where teachers control time progression and students compete to turn $100 into the most money using real historical stock data
- **Target Users**: Teachers (game controllers) and Students (traders)

---

## UI/UX Specification

### Layout Structure

**Landing Page (Join Game)**
- Centered card with room code input and username
- Room code validation (alphanumeric, 4-6 chars)
- "Join Room" button
- "Create Room" button for teachers

**Student Dashboard**
- Header: Room code, current date, teacher controls indicator
- Main grid (3 columns on desktop):
  - Left: Stock list with prices and Buy/Sell buttons
  - Center: S&P 500 chart (Chart.js line chart)
  - Right: Portfolio summary and leaderboard
- Footer: Net worth display

**Admin Dashboard**
- Same layout as student + admin controls panel
- Admin controls: Play/Pause, Reset, Date Picker
- Date picker allows selection from 1927 to present

### Responsive Breakpoints
- Desktop: 1200px+ (3-column grid)
- Tablet: 768px-1199px (2-column grid)
- Mobile: <768px (single column, stacked)

### Visual Design

**Color Palette**
- Background: `#0d1117` (deep dark)
- Card Background: `#161b22`
- Border: `#30363d`
- Primary Text: `#e6edf3`
- Secondary Text: `#8b949e`
- Accent Green (Buy/Profit): `#238636`
- Accent Red (Sell/Loss): `#da3633`
- Accent Blue (Interactive): `#58a6ff`
- Gold (Leaderboard): `#f0b429`

**Typography**
- Font Family: `'JetBrains Mono', 'Fira Code', monospace` for numbers
- Font Family: `'Inter', -apple-system, sans-serif` for UI text
- Headings: 24px (h1), 18px (h2), 14px (h3)
- Body: 14px
- Numbers/Prices: 16px monospace

**Spacing System**
- Base unit: 8px
- Card padding: 24px
- Grid gap: 16px
- Button padding: 12px 24px

**Visual Effects**
- Cards: `box-shadow: 0 4px 12px rgba(0,0,0,0.4)`
- Buttons: Subtle glow on hover (`box-shadow: 0 0 8px`)
- Price changes: Flash green/red briefly on update
- Smooth transitions: 200ms ease-out

### Components

**Stock Card**
- Ticker symbol (bold)
- Company name (small, gray)
- Current price (large, monospace)
- Price change from previous day (colored)
- Buy/Sell buttons (disabled if not IPO'd)
- States: Normal, IPO (enabled), Pre-IPO (disabled, grayed)

**Portfolio Panel**
- Cash balance (large)
- Holdings list: Ticker, shares, current value
- Total net worth (highlighted)

**Leaderboard**
- Rank number (gold/silver/bronze for top 3)
- Username
- Net worth (formatted as currency)
- "You" indicator for current user

**Admin Controls**
- Play/Pause toggle button (icon changes)
- Reset button (with confirmation)
- Date picker (native HTML5 date input)
- Current speed indicator: "1 year = 10 seconds"

---

## Functionality Specification

### Core Features

**1. Data Engine**
- Pre-fetch historical data on startup using yfinance
- Tickers: ^GSPC, AAPL, MSFT, AMZN, KO, DIS, GE, TSLA, BTC-USD
- Store daily 'Close' prices in memory
- Handle "Not Yet IPO'd" - check if game date < first available date
- Cache data to avoid repeated API calls

**2. Server Clock**
- Centralized game state managed by Flask-SocketIO
- Time scaling: 1 year per 10 seconds (25 trading days/second)
- Game states: 'paused', 'playing'
- Broadcast date and prices every tick

**3. Room Management**
- Room codes: 4-6 alphanumeric characters
- Each room has independent game state
- Teacher creates room, gets admin privileges
- Students join with room code

**4. Student Mechanics**
- Starting balance: $100.00
- Buy: Deduct cash, add shares (at current date's price)
- Sell: Add cash, remove shares (at current date's price)
- Cannot buy more than cash allows
- Cannot sell more than owned
- Real-time portfolio updates via SocketIO

**5. Persistence**
- SQLite database for:
  - Rooms (code, created_at, start_date)
  - Players (room_code, username, cash, holdings_json, is_admin)
  - Holdings stored as JSON: {ticker: shares}

**6. Leaderboard**
- Live ranking by total net worth
- Net worth = cash + sum(shares * current_price)
- Updated on every price change

### User Interactions

**Teacher Flow**
1. Click "Create Room" → Get room code
2. Set starting date via date picker
3. Click "Play" → Time begins advancing
4. Monitor students via leaderboard
5. Click "Pause" to halt time
6. Click "Reset" to restart game

**Student Flow**
1. Enter username and room code
2. Join room → See dashboard
3. View current prices and portfolio
4. Click Buy/Sell on stocks
5. Watch net worth change on leaderboard

### Edge Cases
- Attempting to buy pre-IPO stock: Button disabled, tooltip "Not yet IPO'd"
- Attempting to buy more than cash: Show error, button disabled
- Attempting to sell more than owned: Show error, button disabled
- Room doesn't exist: Show error message
- Username already in room: Append number
- Network disconnect: Reconnect and restore state

---

## Technical Architecture

### Backend (Flask + SocketIO)
- `app.py`: Main Flask application
- `models.py`: SQLite database models
- `data_engine.py`: yfinance data fetching
- `game_clock.py`: Time progression logic
- `socket_handlers.py`: SocketIO event handlers

### Frontend
- `templates/index.html`: Landing page
- `templates/dashboard.html`: Main game interface
- `static/js/app.js`: Client-side SocketIO and UI logic
- `static/css/style.css`: Dark mode styles

### Database Schema
```sql
CREATE TABLE rooms (
    code TEXT PRIMARY KEY,
    start_date TEXT,
    current_date TEXT,
    game_state TEXT DEFAULT 'paused',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_code TEXT,
    username TEXT,
    cash REAL DEFAULT 100.0,
    holdings TEXT DEFAULT '{}',
    is_admin BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (room_code) REFERENCES rooms(code)
);
```

---

## Acceptance Criteria

### Visual Checkpoints
- [ ] Dark mode dashboard loads correctly
- [ ] Stock cards show prices with proper formatting
- [ ] Chart.js displays S&P 500 line chart
- [ ] Leaderboard updates in real-time
- [ ] Admin controls visible only to room creator

### Functional Checkpoints
- [ ] yfinance fetches historical data on startup
- [ ] Pre-IPO stocks are not tradable
- [ ] Buy/Sell transactions update cash and holdings
- [ ] Game clock advances at 1 year/10 seconds when playing
- [ ] Date picker allows setting start date (1927+)
- [ ] Reset restores all players to $100 and start date
- [ ] SocketIO broadcasts updates to all clients in room
- [ ] SQLite persists player data across refreshes
- [ ] Leaderboard ranks by net worth correctly

### Deployment Readiness
- [ ] Works on Replit/Render with proper requirements.txt
- [ ] No hardcoded local paths
- [ ] Environment variables for production config