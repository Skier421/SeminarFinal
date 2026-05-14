"""
SeminarFinal_v2.1 - Stock Market Simulator
Main Flask Application
"""

import os
os.environ['EVENTLET_HUB'] = 'poll'

import eventlet
eventlet.monkey_patch()

import random
import string
import time
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, has_request_context
from flask_socketio import SocketIO, emit, join_room

from models import Room, Player, init_db
from data_engine import data_engine
from game_clock import clock_manager
from headlines_data import HEADLINES_BY_YEAR, get_headline_for_year, get_headline_for_date
import practice_mode

# Constants
DEFAULT_START_DATE = '1928-01-01'
PRACTICE_START_DATE = '1920-01-01'
PRACTICE_TICKER = 'GLOBEX'

# Global mode state
PRACTICE_MODE = False
practice_mode.PRACTICE_MODE = PRACTICE_MODE

# Sync practice mode config

def set_practice_mode(enabled: bool):
    global PRACTICE_MODE
    PRACTICE_MODE = enabled
    practice_mode.PRACTICE_MODE = enabled

    if enabled:
        practice_mode.TICKERS = [PRACTICE_TICKER]
        practice_mode.COMPANY_NAMES = {PRACTICE_TICKER: 'Globex Corporation'}
        practice_mode.IPO_DATES = {PRACTICE_TICKER: PRACTICE_START_DATE}
    else:
        practice_mode.TICKERS = ['^DJI', '^GSPC']
        practice_mode.COMPANY_NAMES = {
            '^DJI': 'Dow Jones Industrial Average',
            '^GSPC': 'S&P 500'
        }
        practice_mode.IPO_DATES = {
            '^DJI': '1900-01-01',
            '^GSPC': '1957-03-01'
        }

set_practice_mode(PRACTICE_MODE)

# Initialize Flask app
app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'seminarfinal-secret-key-v2-1')

# Version for cache invalidation
APP_VERSION = '4.1'

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

# Game state tracking
ROOM_USER_SIDS = {}
SOCKET_ROOM_MAP = {}
SID_USER_MAP = {}
ROOM_HEADLINE_META = {}
ROOM_GAME_OVER_SENT = set()
ROOM_REUBEN_SENT = set()
ROOM_SP500_LAUNCH_SENT = set()
AUDIT_WINDOW_SECONDS = 20
RUMOR_LEAD_TICKS = 10
INSIDER_AUDIT_CHANCE = 0.75
INSIDER_CASH_PENALTY = 0.60

# Insider trigger dates with specific advice (one-shot rule)
INSIDER_TIPS = {
    '1929-10-15': 'Market is a bubble. SELL EVERYTHING now.',
    '1932-06-01': 'The bottom is in. BUY A LOT. Prices will never be this low again.',
    '1973-01-10': 'Oil crisis is starting. SELL EVERYTHING before the 50% crash.',
    '1982-08-01': 'Interest rates are dropping. BUY A LOT. The greatest bull market in history starts now.',
    '1987-10-12': 'Black Monday is coming. SELL EVERYTHING.',
    '2008-01-15': 'Housing market is dead. SELL EVERYTHING.',
    '1928-01-02': 'TEST TIP: This is a test to verify the Noir popup works correctly.'
}

# Initialize database
if not os.path.exists('stock_simulator.db'):
    init_db()

# Clear cache to ensure new MASTER_HISTORY data is used
if os.path.exists('stock_data_cache.json'):
    print("Clearing old cache stock_data_cache.json...")
    os.remove('stock_data_cache.json')


def generate_room_code(length: int = 5) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def broadcast_leaderboard(room_code: str):
    players = Player.get_all_in_room(room_code)
    clock = clock_manager.get_clock(room_code)
    prices = data_engine.get_all_prices(clock.current_date)

    leaderboard = []
    for player in players:
        leaderboard.append(player.to_dict(prices))

    leaderboard.sort(key=lambda x: x['net_worth'], reverse=True)
    for i, entry in enumerate(leaderboard):
        entry['rank'] = i + 1

    socketio.emit('leaderboard_update', {'leaderboard': leaderboard}, room=room_code)


def build_final_leaderboard(room_code: str, prices: dict):
    players = Player.get_all_in_room(room_code)
    leaderboard = [player.to_dict(prices) for player in players]
    leaderboard.sort(key=lambda x: x['net_worth'], reverse=True)
    for i, entry in enumerate(leaderboard):
        entry['rank'] = i + 1
    return leaderboard


def emit_game_over(room_code: str, current_date: str, prices: dict):
    if room_code in ROOM_GAME_OVER_SENT:
        return

    ROOM_GAME_OVER_SENT.add(room_code)
    leaderboard = build_final_leaderboard(room_code, prices)
    socketio.emit('leaderboard_update', {'leaderboard': leaderboard}, room=room_code)

    for entry in leaderboard:
        sid = ROOM_USER_SIDS.get(room_code, {}).get(entry['username'])
        if sid:
            socketio.emit('game_over', {
                'current_date': current_date,
                'rank': entry['rank'],
                'total_players': len(leaderboard),
                'net_worth': round(entry['net_worth'], 2),
                'leaderboard': leaderboard
            }, room=sid)


def broadcast_player_portfolio(room_code: str, username: str):
    """Send the current player's portfolio data"""
    player = Player.get(room_code, username)
    if not player:
        print(f"ERROR: Player {username} not found in room {room_code}")
        return

    print(f"DEBUG: Player {username} found with cash={player.cash}")

    clock = clock_manager.get_clock(room_code)
    prices = data_engine.get_all_prices(clock.current_date)

    # Margin call logic for all-in players during 1929
    if '1929-01-01' <= clock.current_date <= '1929-12-31':
        holdings_value = player.get_holdings_value(prices)
        net_worth = player.get_net_worth(prices)
        # Check if player is "all-in" (less than 5% cash relative to net worth)
        if player.cash < (net_worth * 0.05) and holdings_value > 0:
            # Apply margin call: 90-95% loss
            loss_percentage = 0.90 + (random.random() * 0.05)  # 90-95%
            loss_amount = holdings_value * loss_percentage
            # Reduce holdings proportionally
            for ticker in player.holdings:
                player.holdings[ticker] *= (1 - loss_percentage)
            player.save()
            socketio.emit('margin_call', {
                'message': f'MARGIN CALL: Great Depression wipeout! You lost {loss_percentage*100:.1f}% of your holdings.',
                'loss_percentage': loss_percentage * 100
            }, room=room_code)

    holdings_value = player.get_holdings_value(prices)
    net_worth = player.get_net_worth(prices)

    print(f"DEBUG: Broadcasting portfolio - cash={player.cash}, holdings_value={holdings_value}, net_worth={net_worth}")

    emit('portfolio_update', {
        'cash': round(player.cash, 2),
        'holdings': player.holdings,
        'holdings_value': holdings_value,
        'net_worth': round(net_worth, 2)
    })


def broadcast_game_state(room_code: str, *_args):
    clock = clock_manager.get_clock(room_code)
    room = Room.get(room_code)
    if not room:
        return

    state = clock.get_state()
    if room.current_date != clock.current_date:
        socketio.start_background_task(room.update_date, clock.current_date)

    # Firm game end date at 2026-12-31
    if clock.current_date >= '2026-12-31' and clock.game_state == 'playing':
        clock.set_state('paused')
        room.set_state('paused')
        state = clock.get_state()
        # Emit game over event for Game Summary screen
        if room_code not in ROOM_GAME_OVER_SENT:
            socketio.emit('game_over', {
                'message': 'Game ended on 2026-12-31. Thank you for playing!'
            }, room=room_code)
            ROOM_GAME_OVER_SENT.add(room_code)

    state['display_date'] = 'Day 1' if PRACTICE_MODE else clock.current_date
    state['practice_mode'] = PRACTICE_MODE
    state['start_date'] = room.start_date
    state['tickers'] = data_engine.get_tickers()
    state['company_names'] = {ticker: data_engine.get_company_name(ticker) for ticker in state['tickers']}
    state['available_tickers'] = data_engine.get_available_tickers(clock.current_date)

    available_tickers = data_engine.get_tickers()
    if PRACTICE_MODE and available_tickers:
        active_index_ticker = available_tickers[0]
    else:
        active_index_ticker = '^GSPC' if clock.current_date >= '1957-03-01' else '^DJI'

    state['active_index'] = {
        'ticker': active_index_ticker,
        'name': data_engine.get_company_name(active_index_ticker),
        'value': state['prices'].get(active_index_ticker)
    }

    # Add historical price data for charts
    state['historical_prices'] = {
        '^DJI': data_engine.get_historical_prices('^DJI', room.start_date, clock.current_date, num_points=200),
        '^GSPC': data_engine.get_historical_prices('^GSPC', room.start_date, clock.current_date, num_points=200)
    }

    state['panic_mode'] = getattr(clock, 'panic_mode', False)
    # Check for date-specific headline first, then fall back to year-based
    headline_text = get_headline_for_date(clock.current_date) or get_headline_for_year(int(clock.current_date[:4]))
    state['headline'] = headline_text

    current_year = int(clock.current_date[:4])
    if not PRACTICE_MODE and clock.current_date >= '1980-01-01' and room_code not in ROOM_REUBEN_SENT:
        ROOM_REUBEN_SENT.add(room_code)
        state['market_event'] = {
            'type': 'reuben_born',
            'message': 'Reuben Seidl is born! 🍺🍺🍺',
            'date': clock.current_date
        }
        socketio.emit('market_event', state['market_event'], room=room_code)

    if not PRACTICE_MODE and clock.current_date >= '1957-03-04' and room_code not in ROOM_SP500_LAUNCH_SENT:
        ROOM_SP500_LAUNCH_SENT.add(room_code)
        state['market_event'] = {
            'type': 'sp500_launch',
            'message': 'FINANCIAL MILESTONE: Standard & Poor\'s launches the 500 Stock Index.',
            'date': clock.current_date
        }
        socketio.emit('market_event', state['market_event'], room=room_code)

    last_meta = ROOM_HEADLINE_META.get(room_code, {})
    if last_meta.get('year') != current_year:
        ROOM_HEADLINE_META[room_code] = {
            'year': current_year,
            'released_at': time.time()
        }

    # Check for insider tip trigger dates (one-shot rule)
    if clock.current_date in INSIDER_TIPS:
        for username, sid in ROOM_USER_SIDS.get(room_code, {}).items():
            player = Player.get(room_code, username)
            if player and not player.has_used_insider_tip:
                player.has_used_insider_tip = True
                player.save()
                socketio.emit('insider_tip', {
                    'tip': INSIDER_TIPS[clock.current_date],
                    'message': 'CLASSIFIED INFORMATION: You only get one tip per game. Use it wisely.'
                }, room=sid)

    insider_rumor = get_insider_rumor(clock.current_date)
    socketio.start_background_task(send_insider_opportunity, room_code, insider_rumor)
    if has_request_context():
        username = session.get('username')
        player = Player.get(room_code, username) if username else None
        if player:
            state['insider_opportunity'] = {
                'available': bool(insider_rumor),
                'message': 'Insider rumor available. Viewing it carries a 75% SEC audit risk.'
            }

    socketio.emit('game_state_update', state, room=room_code)
    socketio.start_background_task(broadcast_leaderboard, room_code)


def get_next_headline_year(current_year: int) -> int:
    years = sorted(HEADLINES_BY_YEAR.keys())
    for year in years:
        if year > current_year:
            return year
    return None


def get_insider_rumor(current_date: str):
    try:
        from practice_mode import PRACTICE_MODE as pmode
        if pmode:
            from practice_data import get_practice_insider_rumor
            return get_practice_insider_rumor(current_date)
    except ImportError:
        pass

    current_year = int(current_date[:4])
    current_month = int(current_date[5:7])
    next_year = get_next_headline_year(current_year)
    if not next_year:
        prices = data_engine.get_all_prices(current_date)
        active_ticker = '^GSPC' if current_date >= '1957-03-01' else '^DJI'
        current_price = prices.get(active_ticker)
        if current_price:
            return f"Insider chatter: the market is nearing the present day with {active_ticker} around ${current_price:,.2f}."
        return "Insider chatter: the market is nearing the present day."

    months_until = (next_year - current_year) * 12 - (current_month - 1)
    ticks_until = max(0, (months_until + 2) // 3)
    if ticks_until <= RUMOR_LEAD_TICKS:
        return get_headline_for_year(next_year)
    return f"Insider chatter points toward a major market headline in {next_year}: {get_headline_for_year(next_year)}"


def send_insider_rumor(room_code: str, rumor_text: str):
    if not rumor_text:
        return

    for username, sid in ROOM_USER_SIDS.get(room_code, {}).items():
        player = Player.get(room_code, username)
        if player and player.is_insider:
            socketio.emit('insider_rumor', {
                'headline': rumor_text,
                'message': 'Insider rumor coming soon'
            }, room=sid)


def send_insider_opportunity(room_code: str, rumor_text: str):
    for username, sid in ROOM_USER_SIDS.get(room_code, {}).items():
        player = Player.get(room_code, username)
        if not player:
            continue
        available = bool(rumor_text)
        message = 'Insider rumor available. Viewing it carries a 75% SEC audit risk.' if available else 'No rumor available right now.'
        socketio.emit('insider_opportunity', {
            'available': available,
            'message': message
        }, room=sid)


@socketio.on('request_insider_rumor')
def handle_request_insider_rumor():
    room_code = session.get('room_code')
    username = session.get('username')
    if not room_code or not username:
        emit('error', {'message': 'Not in a room'})
        return

    player = Player.get(room_code, username)
    if not player:
        emit('error', {'message': 'Player not found'})
        return

    clock = clock_manager.get_clock(room_code)
    rumor_text = get_insider_rumor(clock.current_date)
    if not rumor_text:
        emit('insider_opportunity', {
            'available': False,
            'message': 'No insider rumor is available right now.'
        })
        return

    player.is_insider = False
    player.save()

    emit('insider_rumor', {
        'headline': rumor_text,
        'message': 'Insider rumor'
    })

    if random.random() < INSIDER_AUDIT_CHANCE:
        penalty = round(player.cash * INSIDER_CASH_PENALTY, 2)
        player.cash = round(player.cash - penalty, 2)
        player.save()
        prices = data_engine.get_all_prices(clock.current_date)
        holdings_value = player.get_holdings_value(prices)
        net_worth = player.get_net_worth(prices)
        emit('sec_penalty', {
            'message': 'SEC ENFORCEMENT: You were audited after viewing insider information. 60% of your cash was seized.',
            'penalty': penalty,
            'cash_remaining': player.cash
        })
        emit('portfolio_update', {
            'cash': round(player.cash, 2),
            'holdings': player.holdings,
            'holdings_value': holdings_value,
            'net_worth': round(net_worth, 2)
        })
        broadcast_leaderboard(room_code)
    else:
        emit('info', {'message': 'You avoided an SEC audit this time.'})

    emit('insider_opportunity', {
        'available': True,
        'message': 'Another insider rumor will be available as the market updates.'
    })


def maybe_audit_insider(player: Player, room_code: str) -> float:
    if not player or not player.is_insider:
        return 0.0

    room_meta = ROOM_HEADLINE_META.get(room_code)
    if not room_meta:
        return 0.0

    if time.time() - room_meta.get('released_at', 0) > AUDIT_WINDOW_SECONDS:
        return 0.0

    if random.random() >= INSIDER_AUDIT_CHANCE:
        return 0.0

    penalty = round(player.cash * INSIDER_CASH_PENALTY, 2)
    player.cash = round(player.cash - penalty, 2)
    player.save()
    return penalty


def rotate_insider(room_code: str):
    return


@socketio.on('join_room')
def handle_join_room(data):
    try:
        room_code = data.get('room_code', '').upper()
        username = data.get('username', '').strip()
        print(f"DEBUG: Join room request - room_code={room_code}, username={username}")
        if not room_code or not username:
            emit('error', {'message': 'Room code and username required'})
            return

        if not Room.exists(room_code):
            emit('error', {'message': 'Room not found'})
            return

        player = Player.get(room_code, username)
        if not player:
            print(f"DEBUG: Player {username} not found, creating new player")
            player = Player.create(room_code, username)
            print(f"DEBUG: Player created with cash={player.cash}")
        else:
            print(f"DEBUG: Player {username} found with cash={player.cash}")

        join_room(room_code)
        ROOM_USER_SIDS.setdefault(room_code, {})[player.username] = request.sid
        SOCKET_ROOM_MAP[request.sid] = room_code
        SID_USER_MAP[request.sid] = player.username

        session['room_code'] = room_code
        session['username'] = player.username

        clock = clock_manager.get_clock(room_code)
        room = Room.get(room_code)
        if not clock._broadcast_callback:
            clock.set_broadcast_callback(broadcast_game_state)

        if room:
            clock.set_date(room.current_date)
            clock.set_state(room.game_state)

        emit('joined_room', {
            'room_code': room_code,
            'username': player.username,
            'is_admin': player.is_admin,
            'is_insider': player.is_insider,
            'practice_mode': PRACTICE_MODE,
            'tickers': data_engine.get_tickers()
        })

        broadcast_game_state(room_code)
        broadcast_leaderboard(room_code)
        broadcast_player_portfolio(room_code, username)
        rumor_text = get_insider_rumor(clock.current_date)
        if rumor_text:
            emit('insider_opportunity', {
                'available': True,
                'message': 'Insider rumor available. Viewing it carries a 75% SEC audit risk.'
            })
    except Exception as e:
        print(f"ERROR in join_room: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error joining room: {str(e)}'})


@socketio.on('buy_stock')
def handle_buy_stock(data):
    room_code = session.get('room_code')
    username = session.get('username')
    if not room_code or not username:
        emit('error', {'message': 'Not in a room'})
        return

    ticker = data.get('ticker')
    try:
        amount = float(data.get('amount', 0))
    except (TypeError, ValueError):
        emit('error', {'message': 'Invalid amount'})
        return

    if not ticker or amount <= 0:
        emit('error', {'message': 'Invalid ticker or amount'})
        return

    clock = clock_manager.get_clock(room_code)
    price = data_engine.get_price(ticker, clock.current_date)
    if price is None:
        emit('error', {'message': f'{ticker} not available'})
        return

    shares = round(amount / price, 8)
    if shares <= 0:
        emit('error', {'message': 'Amount too small'})
        return

    player = Player.get(room_code, username)
    if player.buy(ticker, shares, price, amount):
        emit('trade_success', {
            'action': 'buy',
            'ticker': ticker,
            'shares': shares,
            'price': price,
            'total': round(amount, 2)
        })
        broadcast_leaderboard(room_code)
        broadcast_player_portfolio(room_code, username)
    else:
        emit('error', {'message': 'Insufficient funds'})
        return

@socketio.on('sell_stock')
def handle_sell_stock(data):
    room_code = session.get('room_code')
    username = session.get('username')
    if not room_code or not username:
        emit('error', {'message': 'Not in a room'})
        return

    ticker = data.get('ticker')
    try:
        shares = float(data.get('shares', 0))
    except (TypeError, ValueError):
        emit('error', {'message': 'Invalid shares'})
        return

    if not ticker or shares <= 0:
        emit('error', {'message': 'Invalid ticker or shares'})
        return

    clock = clock_manager.get_clock(room_code)
    price = data_engine.get_price(ticker, clock.current_date)
    if price is None:
        emit('error', {'message': f'{ticker} not available'})
        return

    player = Player.get(room_code, username)
    if player.sell(ticker, shares, price):
        emit('trade_success', {
            'action': 'sell',
            'ticker': ticker,
            'shares': shares,
            'price': price,
            'total': round(shares * price, 2)
        })
        broadcast_leaderboard(room_code)
        broadcast_player_portfolio(room_code, username)
    else:
        emit('error', {'message': 'Insufficient shares'})
        return

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    room_code = SOCKET_ROOM_MAP.pop(sid, None)
    username = SID_USER_MAP.pop(sid, None)
    if room_code and username and room_code in ROOM_USER_SIDS:
        ROOM_USER_SIDS[room_code].pop(username, None)


@socketio.on('admin_toggle_play')
def handle_toggle_play(data=None):
    room_code = session.get('room_code')
    username = session.get('username')
    if not room_code or not username:
        return

    player = Player.get(room_code, username)
    if not player or not player.is_admin:
        emit('error', {'message': 'Admin only'})
        return

    room = Room.get(room_code)
    if not room:
        return

    clock = clock_manager.get_clock(room_code)
    if not clock._broadcast_callback:
        clock.set_broadcast_callback(broadcast_game_state)

    if PRACTICE_MODE:
        room.update_date(PRACTICE_START_DATE)
        clock.set_date(PRACTICE_START_DATE)

    new_state = 'playing' if room.game_state == 'paused' else 'paused'
    room.set_state(new_state)
    clock.set_state(new_state)

    broadcast_game_state(room_code)


@socketio.on('admin_set_date')
def handle_set_date(data=None):
    room_code = session.get('room_code')
    username = session.get('username')
    if not room_code or not username:
        return

    player = Player.get(room_code, username)
    if not player or not player.is_admin:
        emit('error', {'message': 'Admin only'})
        return

    if PRACTICE_MODE:
        new_date = PRACTICE_START_DATE
    else:
        new_date = (data or {}).get('date')
        if not new_date:
            return

    room = Room.get(room_code)
    if not room:
        return

    room.update_date(new_date)
    clock = clock_manager.get_clock(room_code)
    clock.set_date(new_date)
    ROOM_GAME_OVER_SENT.discard(room_code)
    if new_date < '1980-01-01':
        ROOM_REUBEN_SENT.discard(room_code)

    broadcast_game_state(room_code)
    broadcast_leaderboard(room_code)


@socketio.on('admin_reset')
def handle_reset(data=None):
    room_code = session.get('room_code')
    username = session.get('username')
    if not room_code or not username:
        return

    player = Player.get(room_code, username)
    if not player or not player.is_admin:
        emit('error', {'message': 'Admin only'})
        return

    room = Room.get(room_code)
    if not room:
        return

    start_date = PRACTICE_START_DATE if PRACTICE_MODE else DEFAULT_START_DATE
    room.update_date(start_date)
    room.set_state('paused')

    clock = clock_manager.get_clock(room_code)
    clock.reset(start_date)
    ROOM_GAME_OVER_SENT.discard(room_code)
    ROOM_REUBEN_SENT.discard(room_code)
    ROOM_SP500_LAUNCH_SENT.discard(room_code)
    for room_player in Player.get_all_in_room(room_code):
        room_player.is_insider = False
        room_player.has_used_insider_tip = False
        room_player.save()

    broadcast_game_state(room_code)
    broadcast_leaderboard(room_code)


@socketio.on('admin_set_insider')
def handle_set_insider(data=None):
    room_code = session.get('room_code')
    username = session.get('username')
    if not room_code or not username:
        return

    player = Player.get(room_code, username)
    if not player or not player.is_admin:
        emit('error', {'message': 'Admin only'})
        return

    target_username = (data or {}).get('username', '').strip()
    target_insider = bool((data or {}).get('is_insider', True))
    if not target_username:
        emit('error', {'message': 'Username required'})
        return

    target_player = Player.get(room_code, target_username)
    if not target_player:
        emit('error', {'message': 'Player not found'})
        return

    if target_insider and room_code in ROOM_USER_SIDS and target_username in ROOM_USER_SIDS[room_code]:
        target_sid = ROOM_USER_SIDS[room_code][target_username]
        socketio.emit('insider_status_updated', {
            'message': 'You have been granted insider access.',
            'is_insider': True
        }, room=target_sid)

    target_player.set_insider(target_insider)
    broadcast_game_state(room_code)
    broadcast_leaderboard(room_code)


@socketio.on('toggle_mode')
def handle_toggle_mode(data=None):
    room_code = session.get('room_code')
    username = session.get('username')
    if not room_code or not username:
        emit('error', {'message': 'Not in a room'})
        return

    player = Player.get(room_code, username)
    if not player or not player.is_admin:
        emit('error', {'message': 'Admin only'})
        return

    set_practice_mode(not PRACTICE_MODE)
    data_engine.reload_data()

    room = Room.get(room_code)
    if not room:
        return

    target_date = PRACTICE_START_DATE if PRACTICE_MODE else DEFAULT_START_DATE
    room.update_date(target_date)
    clock = clock_manager.get_clock(room_code)
    clock.set_date(target_date)
    ROOM_GAME_OVER_SENT.discard(room_code)
    ROOM_REUBEN_SENT.discard(room_code)
    ROOM_SP500_LAUNCH_SENT.discard(room_code)

    socketio.emit('mode_toggled', {
        'practice_mode': PRACTICE_MODE,
        'tickers': data_engine.get_tickers(),
        'company_names': {ticker: data_engine.get_company_name(ticker) for ticker in data_engine.get_tickers()}
    }, room=room_code)

    broadcast_game_state(room_code)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/create_room', methods=['POST'])
def create_room():
    username = request.form.get('username', '').strip()
    if not username:
        return render_template('index.html', error='Username required')

    room_code = generate_room_code()
    while Room.exists(room_code):
        room_code = generate_room_code()

    Room.create(room_code, DEFAULT_START_DATE)
    Player.create(room_code, username, is_admin=True)
    clock_manager.get_clock(room_code).set_date(DEFAULT_START_DATE)
    return redirect(url_for('dashboard', room_code=room_code, username=username))


@app.route('/join_room', methods=['POST'])
def join_room_route():
    room_code = request.form.get('room_code', '').upper().strip()
    username = request.form.get('username', '').strip()
    if not room_code or not username:
        return render_template('index.html', error='Room code and username required')
    if not Room.exists(room_code):
        return render_template('index.html', error='Room not found')
    return redirect(url_for('dashboard', room_code=room_code, username=username))


@app.route('/dashboard')
def dashboard():
    room_code = request.args.get('room_code', '').upper()
    username = request.args.get('username', '')
    if not room_code or not username:
        return redirect(url_for('index'))
    if not Room.exists(room_code):
        return redirect(url_for('index'))

    room = Room.get(room_code)
    player = Player.get(room_code, username)
    if not player:
        player = Player.create(room_code, username)

    min_date, max_date = data_engine.get_date_range()
    return render_template(
        'dashboard.html',
        room_code=room_code,
        username=username,
        is_admin=player.is_admin,
        is_insider=player.is_insider,
        practice_mode=PRACTICE_MODE,
        start_date=room.current_date if room else DEFAULT_START_DATE,
        min_date=min_date,
        max_date=max_date,
        tickers=data_engine.get_tickers(),
        company_names={ticker: data_engine.get_company_name(ticker) for ticker in data_engine.get_tickers()}
    )


@app.route('/api/room/<room_code>')
def get_room_info(room_code):
    room = Room.get(room_code.upper())
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    clock = clock_manager.get_clock(room_code)
    prices = data_engine.get_all_prices(clock.current_date)
    return jsonify({
        'room_code': room.code,
        'start_date': room.start_date,
        'current_date': room.current_date,
        'game_state': room.game_state,
        'prices': prices
    })


@app.route('/api/player/<room_code>/<username>')
def get_player_info(room_code, username):
    player = Player.get(room_code.upper(), username)
    if not player:
        return jsonify({'error': 'Player not found'}), 404
    clock = clock_manager.get_clock(room_code)
    prices = data_engine.get_all_prices(clock.current_date)
    return jsonify(player.to_dict(prices))


@app.route('/api/headline/<int:year>')
def get_headline(year):
    min_year = 1900
    max_year = 2100
    if year < min_year or year > max_year:
        return jsonify({'error': f'Year must be between {min_year} and {max_year}'}), 400
    headline_text = get_headline_for_year(year)
    return jsonify({
        'headline': headline_text,
        'pub_date': f'{year}-01-01',
        'url': None,
        'source': 'Historical Archive',
        'error': None
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
