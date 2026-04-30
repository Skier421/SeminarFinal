"""
Practice Mode Data for Historical Stock Market Simulator
Simplified fictional stock data for testing game mechanics
"""

from datetime import datetime, timedelta
import random

# Fictional stock ticker
PRACTICE_TICKER = 'GLOBEX'

# Company name
PRACTICE_COMPANY_NAME = 'Globex Corporation'

# IPO date (start of practice data)
PRACTICE_IPO_DATE = '1920-01-01'

# Starting price
START_PRICE = 50.0

# Price history: 100 steps
# Phase 1 (steps 1-25): Rise from $50 to $120
# Phase 2 (steps 26-50): Crash from $120 to $15
# Phase 3 (steps 51-100): Stabilize around $60

def generate_practice_prices():
    """Generate 100-step price history for GLOBEX"""
    prices = {}
    current_price = START_PRICE

    # Start date
    base_date = datetime(1920, 1, 1)

    for step in range(1, 101):
        date = base_date + timedelta(days=step - 1)
        date_str = date.strftime('%Y-%m-%d')

        if step <= 25:
            # Phase 1: Rise to $120
            # Target: from 50 to 120 over 25 steps
            target_price = 50 + (120 - 50) * (step / 25)
            # Add some volatility
            volatility = random.uniform(-0.05, 0.05)
            current_price = target_price * (1 + volatility)

        elif step <= 50:
            # Phase 2: Crash to $15
            # Target: from 120 to 15 over 25 steps (steps 26-50)
            progress = (step - 25) / 25
            target_price = 120 - (120 - 15) * progress
            # Add volatility (more during crash)
            volatility = random.uniform(-0.15, 0.05)
            current_price = target_price * (1 + volatility)

        else:
            # Phase 3: Stabilize around $60
            # Oscillate around 60 with moderate volatility
            target_price = 60.0
            volatility = random.uniform(-0.10, 0.10)
            current_price = target_price * (1 + volatility)

        # Ensure price doesn't go negative
        current_price = max(current_price, 0.01)
        prices[date_str] = round(current_price, 2)

    return prices

# Generate the price data
PRACTICE_PRICES = generate_practice_prices()

# Headlines for GLOBEX
PRACTICE_HEADLINES = {
    1920: "Globex Corporation announces revolutionary new product line, stock surges!",
    1921: "Globex reports record quarterly profits, investors optimistic!",
    1922: "Globex faces supply chain disruptions, shares plummet!",
    1923: "Globex sued for patent infringement, major legal setback!",
    1924: "Globex announces routine maintenance schedule, no major changes expected."
}

# Insider rumors for GLOBEX (to test 60% audit chance and rotation)
PRACTICE_RUMORS = [
    "I heard Globex is losing its biggest contract - this could be bad!",
    "Globex just struck oil in a new field - massive upside potential!",
    "Whispers of Globex management changes - uncertain impact on stock."
]

# Function to get headline for a year (for practice mode)
def get_practice_headline_for_year(year: int) -> str:
    """Get practice headline for a specific year"""
    return PRACTICE_HEADLINES.get(year, "Globex reports steady business operations.")

# Function to get insider rumor (for practice mode)
def get_practice_insider_rumor(date: str) -> str:
    """Get a practice insider rumor based on date"""
    # Simple rotation based on date hash
    index = hash(date) % len(PRACTICE_RUMORS)
    return PRACTICE_RUMORS[index]

# Practice mode data structure (matches data_engine format)
PRACTICE_DATA = {
    'tickers': [PRACTICE_TICKER],
    'company_names': {
        PRACTICE_TICKER: PRACTICE_COMPANY_NAME
    },
    'ipo_dates': {
        PRACTICE_TICKER: PRACTICE_IPO_DATE
    },
    'prices': {
        PRACTICE_TICKER: PRACTICE_PRICES
    },
    'headlines': PRACTICE_HEADLINES,
    'rumors': PRACTICE_RUMORS
}