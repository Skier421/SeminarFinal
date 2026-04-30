"""
Main Flask Application for Historical Stock Market Simulator
"""


import eventlet
eventlet.monkey_patch()


import os
import random
import string
import time
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room

from models import Room, Player, init_db
from data_engine import data_engine, TICKERS, COMPANY_NAMES
from game_clock import clock_manager
from headlines_data import HEADLINES_BY_YEAR, get_headline_for_year

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'stock-simulator-secret-key')
DEFAULT_START_DATE = '1928-01-01'

# Insider trading controls
ROOM_USER_SIDS = {}
SOCKET_ROOM_MAP = {}
SID_USER_MAP = {}
ROOM_HEADLINE_META = {}
AUDIT_WINDOW_SECONDS = 20
RUMOR_LEAD_TICKS = 10

# Initialize SocketIO with threading for macOS compatibility and CORS support
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Ensure the local SQLite database exists before startup
if not os.path.exists('stock_simulator.db'):
    init_db()


def generate_room_code(length: int = 5) -> str:
    """Generate a random alphanumeric room code"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def broadcast_leaderboard(room_code: str):
    """Broadcast updated leaderboard to all players in a room"""
    players = Player.get_all_in_room(room_code)
    clock = clock_manager.get_clock(room_code)
    prices = data_engine.get_all_prices(clock.current_date)
    
    # Calculate net worth for each player
    leaderboard = []
    for player in players:
        leaderboard.append(player.to_dict(prices))
    
    # Sort by net worth (descending)
    leaderboard.sort(key=lambda x: x['net_worth'], reverse=True)
    
    # Add rank
    for i, entry in enumerate(leaderboard):
        entry['rank'] = i + 1
    
    socketio.emit('leaderboard_update', {'leaderboard': leaderboard}, room=room_code)


def broadcast_game_state(room_code: str, *_args):
    """Broadcast current game state to all players in a room"""
    clock = clock_manager.get_clock(room_code)
    room = Room.get(room_code)
    
    if not room:
        return
    
    state = clock.get_state()
    # Persist clock progress so reconnects do not snap back to stale room dates.
    if room.current_date != clock.current_date:
        room.update_date(clock.current_date)
    state['start_date'] = room.start_date
    state['available_tickers'] = data_engine.get_available_tickers(clock.current_date)
    # Use Dow before S&P 500 launch, then switch to S&P 500 from 1957 onward.
    active_index_ticker = '^GSPC' if clock.current_date >= '1957-03-01' else '^DJI'
    state['active_index'] = {
        'ticker': active_index_ticker,
        'name': COMPANY_NAMES.get(active_index_ticker, active_index_ticker),
        'value': state['prices'].get(active_index_ticker)
    }

    # Include panic mode state in the current game tick.
    state['panic_mode'] = getattr(clock, 'panic_mode', False)

    # Send the headline text for the current game year as a ticker event.
    headline_text = get_headline_for_year(int(clock.current_date[:4]))
    state['headline'] = headline_text

    current_year = int(clock.current_date[:4])
    last_meta = ROOM_HEADLINE_META.get(room_code, {})
    if last_meta.get('year') != current_year:
        ROOM_HEADLINE_META[room_code] = {
            'year': current_year,
            'released_at': time.time()
        }
        # Rotate insider on new year
        rotate_insider(room_code)

    insider_rumor = get_insider_rumor(clock.current_date)
    if insider_rumor:
        send_insider_rumor(room_code, insider_rumor)

    socketio.emit('new_headline', {
        'headline': headline_text,
        'year': clock.current_date[:4]
    }, room=room_code)

    socketio.emit('game_state_update', state, room=room_code)
    # Net worth depends on live prices, so refresh leaderboard on each state tick.
    broadcast_leaderboard(room_code)


def get_next_headline_year(current_year: int) -> int:
    years = sorted(HEADLINES_BY_YEAR.keys())
    for year in years:
        if year > current_year:
            return year
    return None


def get_insider_rumor(current_date: str):
    current_year = int(current_date[:4])
    current_month = int(current_date[5:7])
    next_year = get_next_headline_year(current_year)
    if not next_year:
        return None

    months_until = (next_year - current_year) * 12 - (current_month - 1)
    ticks_until = max(0, (months_until + 2) // 3)

    if ticks_until <= RUMOR_LEAD_TICKS:
        return get_headline_for_year(next_year)
    return None


def send_insider_rumor(room_code: str, rumor_text: str):
    if not rumor_text:
        return
    for username, sid in ROOM_USER_SIDS.get(room_code, {}).items():
        player = Player.get(room_code, username)
        if player and player.is_insider:
            socketio.emit('insider_rumor', {
                'headline': rumor_text,
                'message': 'Insider Rumor: This headline will appear soon on the public ticker.'
            }, room=sid)


def maybe_audit_insider(player: Player, room_code: str) -> float:
    if not player or not player.is_insider:
        return 0.0

    room_meta = ROOM_HEADLINE_META.get(room_code)
    if not room_meta:
        return 0.0

    if time.time() - room_meta.get('released_at', 0) > AUDIT_WINDOW_SECONDS:
        return 0.0

    if random.random() >= 0.6:
        return 0.0

    penalty = round(player.cash * 0.5, 2)
    player.cash = round(player.cash - penalty, 2)
    player.save()
    return penalty


def rotate_insider(room_code: str):
    """Rotate the insider role to a new eligible player"""
    players = Player.get_all_in_room(room_code)
    
    # Find current insider
    current_insider = None
    for p in players:
        if p.is_insider:
            current_insider = p
            break
    
    # Find eligible players: non-admin, has_had_insider_turn == False
    eligible = [p for p in players if not p.is_admin and not p.has_had_insider_turn]
    
    if not eligible:
        # All non-admin players have had a turn, reset has_had_insider_turn for all non-admin
        for p in players:
            if not p.is_admin:
                p.has_had_insider_turn = False
                p.save()
        eligible = [p for p in players if not p.is_admin]
    
    if not eligible:
        return  # No players to rotate to
    
    # Remove insider from current
    if current_insider:
        current_insider.set_insider(False)
        socketio.emit('insider_status_updated', {
            'is_insider': False,
            'message': 'Your insider turn has ended.'
        }, room=current_insider.username)
    
    # Pick new insider randomly
    new_insider = random.choice(eligible)
    new_insider.set_insider(True)
    new_insider.has_had_insider_turn = True
    new_insider.save()
    
    socketio.emit('insider_status_updated', {
        'is_insider': True,
        'message': 'You are now the insider!'
    }, room=new_insider.username)


# SocketIO event handlers
@socketio.on('join_room')
def handle_join_room(data):
    """Handle player joining a room"""
    try:
        room_code = data.get('room_code', '').upper()
        username = data.get('username', '').strip()

        if not room_code or not username:
            emit('error', {'message': 'Room code and username required'})
            return

        # Check if room exists
        if not Room.exists(room_code):
            emit('error', {'message': 'Room not found'})
            return

        # Get or create player
        player = Player.get(room_code, username)
        if not player:
            player = Player.create(room_code, username)

        # Join the socket room
        join_room(room_code)

        ROOM_USER_SIDS.setdefault(room_code, {})[player.username] = request.sid
        SOCKET_ROOM_MAP[request.sid] = room_code
        SID_USER_MAP[request.sid] = player.username

        # Store player info in session
        session['room_code'] = room_code
        session['username'] = player.username

        # Get initial game state
        clock = clock_manager.get_clock(room_code)
        room = Room.get(room_code)

        # Set up broadcast callback if not already set
        if not clock._broadcast_callback:
            clock.set_broadcast_callback(broadcast_game_state)

        if room:
            clock.set_date(room.current_date)
            clock.set_state(room.game_state)

        # Send initial state to player
        emit('joined_room', {
            'room_code': room_code,
            'username': player.username,
            'is_admin': player.is_admin,
            'is_insider': player.is_insider
        })

        # Send current game state
        broadcast_game_state(room_code)

        # Send leaderboard
        broadcast_leaderboard(room_code)

        print(f"Player {player.username} joined room {room_code}")
    except Exception as e:
        emit('error', {'message': f'Unable to join room: {str(e)}'})


@socketio.on('buy_stock')
def handle_buy_stock(data):
    """Handle buy stock request"""
    room_code = session.get('room_code')
    username = session.get('username')
    
    if not room_code or not username:
        emit('error', {'message': 'Not in a room'})
        return
    
    ticker = data.get('ticker')
    try:
        amount = float(data.get('amount', data.get('shares', 0)))
    except (TypeError, ValueError):
        emit('error', {'message': 'Invalid dollar amount'})
        return
    
    if not ticker or amount <= 0:
        emit('error', {'message': 'Invalid ticker or dollar amount'})
        return
    
    # Get current price
    clock = clock_manager.get_clock(room_code)
    price = data_engine.get_price(ticker, clock.current_date)
    
    if price is None:
        emit('error', {'message': f'{ticker} not available yet (not IPO\'d)'})
        return
    
    shares = round(amount / price, 8)
    if shares <= 0:
        emit('error', {'message': 'Dollar amount too small for a fractional share'})
        return
    
    # Execute trade
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
    else:
        emit('error', {'message': 'Insufficient funds'})
        return

    penalty_amount = maybe_audit_insider(player, room_code)
    if penalty_amount:
        emit('sec_penalty', {
            'message': 'SEC ENFORCEMENT: 50% of your cash has been seized for illegal insider trading!',
            'penalty': penalty_amount,
            'cash_remaining': player.cash
        })

    broadcast_leaderboard(room_code)


@socketio.on('sell_stock')
def handle_sell_stock(data):
    """Handle sell stock request"""
    room_code = session.get('room_code')
    username = session.get('username')
    
    if not room_code or not username:
        emit('error', {'message': 'Not in a room'})
        return
    
    ticker = data.get('ticker')
    try:
        shares = float(data.get('shares', 1))
    except (TypeError, ValueError):
        emit('error', {'message': 'Invalid share amount'})
        return
    
    if not ticker or shares <= 0:
        emit('error', {'message': 'Invalid ticker or shares'})
        return
    
    # Get current price
    clock = clock_manager.get_clock(room_code)
    price = data_engine.get_price(ticker, clock.current_date)
    
    if price is None:
        emit('error', {'message': f'{ticker} not available'})
        return
    
    # Execute trade
    player = Player.get(room_code, username)
    if player.sell(ticker, shares, price):
        emit('trade_success', {
            'action': 'sell',
            'ticker': ticker,
            'shares': shares,
            'price': price,
            'total': shares * price
        })
        broadcast_leaderboard(room_code)
    else:
        emit('error', {'message': 'Insufficient shares'})
        return

    penalty_amount = maybe_audit_insider(player, room_code)
    if penalty_amount:
        emit('sec_penalty', {
            'message': 'SEC ENFORCEMENT: 50% of your cash has been seized for illegal insider trading!',
            'penalty': penalty_amount,
            'cash_remaining': player.cash
        })

    broadcast_leaderboard(room_code)


@socketio.on('disconnect')
def handle_disconnect():
    """Handle player disconnect"""
    room_code = session.get('room_code')
    username = session.get('username')
    sid = request.sid

    if sid in SOCKET_ROOM_MAP:
        room = SOCKET_ROOM_MAP.pop(sid)
        if room in ROOM_USER_SIDS and username in ROOM_USER_SIDS[room]:
            ROOM_USER_SIDS[room].pop(username, None)
            if not ROOM_USER_SIDS[room]:
                ROOM_USER_SIDS.pop(room, None)

    SID_USER_MAP.pop(sid, None)

    if room_code and username:
        leave_room(room_code)
        print(f"Player {username} left room {room_code}")


# Admin SocketIO handlers
@socketio.on('admin_toggle_play')
def handle_toggle_play(data=None):
    """Handle play/pause toggle from admin"""
    room_code = session.get('room_code')
    username = session.get('username')
    
    if not room_code or not username:
        return
    
    # Verify admin
    player = Player.get(room_code, username)
    if not player or not player.is_admin:
        emit('error', {'message': 'Admin only'})
        return
    
    room = Room.get(room_code)
    if not room:
        return
    
    # Toggle state
    clock = clock_manager.get_clock(room_code)
    
    # Ensure broadcast callback is set
    if not clock._broadcast_callback:
        clock.set_broadcast_callback(broadcast_game_state)
    
    new_state = 'playing' if room.game_state == 'paused' else 'paused'
    
    room.set_state(new_state)
    clock.set_state(new_state)
    
    broadcast_game_state(room_code)
    print(f"Room {room_code}: Game {new_state}")


@socketio.on('admin_set_insider')
def handle_set_insider(data=None):
    """Handle setting or unsetting an insider from admin controls"""
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
        emit('error', {'message': 'Username required to set insider'})
        return
    
    target_player = Player.get(room_code, target_username)
    if not target_player:
        emit('error', {'message': 'Player not found'})
        return

    if target_insider and room_code in ROOM_USER_SIDS and target_username in ROOM_USER_SIDS[room_code]:
        target_sid = ROOM_USER_SIDS[room_code][target_username]
        # Notify the newly-designated insider immediately if they are online
        socketio.emit('insider_status_updated', {
            'message': 'You have been granted insider access.',
            'is_insider': True
        }, room=target_sid)
    
    target_player.set_insider(target_insider)
    if target_insider:
        emit('info', {'message': f'{target_username} has been marked as an insider.'})
    else:
        emit('info', {'message': f'{target_username} is no longer an insider.'})
    
    broadcast_game_state(room_code)
    broadcast_leaderboard(room_code)


@socketio.on('admin_set_date')
def handle_set_date(data=None):
    """Handle date change from admin"""
    room_code = session.get('room_code')
    username = session.get('username')
    
    if not room_code or not username:
        return
    
    # Verify admin
    player = Player.get(room_code, username)
    if not player or not player.is_admin:
        emit('error', {'message': 'Admin only'})
        return
    
    new_date = (data or {}).get('date')
    if not new_date:
        return
    
    room = Room.get(room_code)
    if not room:
        return
    
    # Update date
    room.update_date(new_date)
    clock = clock_manager.get_clock(room_code)
    clock.set_date(new_date)
    
    broadcast_game_state(room_code)
    broadcast_leaderboard(room_code)
    print(f"Room {room_code}: Date set to {new_date}")


@socketio.on('admin_reset')
def handle_reset(data=None):
    """Handle game reset from admin"""
    room_code = session.get('room_code')
    username = session.get('username')
    
    if not room_code or not username:
        return
    
    # Verify admin
    player = Player.get(room_code, username)
    if not player or not player.is_admin:
        emit('error', {'message': 'Admin only'})
        return
    
    room = Room.get(room_code)
    if not room:
        return
    
    # Reset room
    room.reset()
    
    # Reset all players
    players = Player.get_all_in_room(room_code)
    for p in players:
        p.reset()
    
    # Reset clock
    clock = clock_manager.get_clock(room_code)
    clock.reset(room.start_date)
    
    broadcast_game_state(room_code)
    broadcast_leaderboard(room_code)
    print(f"Room {room_code}: Game reset")


# Web routes
@app.route('/')
def index():
    """Landing page"""
    return render_template('index.html')


@app.route('/create_room', methods=['POST'])
def create_room():
    """Create a new game room"""
    start_date = DEFAULT_START_DATE
    username = request.form.get('username', '').strip()
    
    if not username:
        return render_template('index.html', error='Username required')
    
    # Generate unique room code
    room_code = generate_room_code()
    while Room.exists(room_code):
        room_code = generate_room_code()
    
    # Create room
    room = Room.create(room_code, start_date)
    
    # Create admin player
    player = Player.create(room_code, username, is_admin=True)
    
    # Initialize clock
    clock = clock_manager.get_clock(room_code)
    clock.set_date(start_date)
    
    return redirect(url_for('dashboard', room_code=room_code, username=username))


@app.route('/join_room', methods=['POST'])
def join_room_route():
    """Join an existing game room"""
    room_code = request.form.get('room_code', '').upper().strip()
    username = request.form.get('username', '').strip()
    
    if not room_code or not username:
        return render_template('index.html', error='Room code and username required')
    
    if not Room.exists(room_code):
        return render_template('index.html', error='Room not found')
    
    return redirect(url_for('dashboard', room_code=room_code, username=username))


@app.route('/dashboard')
def dashboard():
    """Game dashboard"""
    room_code = request.args.get('room_code', '').upper()
    username = request.args.get('username', '')
    
    if not room_code or not username:
        return redirect(url_for('index'))
    
    if not Room.exists(room_code):
        return redirect(url_for('index'))
    
    # Get room and player info
    room = Room.get(room_code)
    player = Player.get(room_code, username)
    
    if not player:
        player = Player.create(room_code, username)
    
    # Get available date range
    min_date, max_date = data_engine.get_date_range()
    
    return render_template(
        'dashboard.html',
        room_code=room_code,
        username=username,
        is_admin=player.is_admin,
        is_insider=player.is_insider,
        start_date=room.start_date if room else DEFAULT_START_DATE,
        min_date=min_date,
        max_date=max_date,
        tickers=TICKERS,
        company_names=COMPANY_NAMES
    )


@app.route('/api/room/<room_code>')
def get_room_info(room_code):
    """Get room information"""
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
    """Get player information"""
    player = Player.get(room_code.upper(), username)
    if not player:
        return jsonify({'error': 'Player not found'}), 404
    
    clock = clock_manager.get_clock(room_code)
    prices = data_engine.get_all_prices(clock.current_date)
    
    return jsonify(player.to_dict(prices))


@app.route('/api/headline/<int:year>')
def get_headline(year):
    """Get one local historical headline for a specific year."""
    min_year = 1900
    max_year = 2100
    if year < min_year or year > max_year:
        return jsonify({'error': f'Year must be between {min_year} and {max_year}'}), 400

    headline_text = get_headline_for_year(year)
    data = {
        'headline': headline_text,
        'pub_date': f'{year}-01-01',
        'url': None,
        'source': 'Historical Archive',
        'error': None
    }

    return jsonify(data)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
