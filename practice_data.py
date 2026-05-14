"""
Practice Mode Data for Historical Stock Market Simulator
Simplified fictional stock data for testing game mechanics
"""

from datetime import datetime
import random

# Fictional stock ticker
PRACTICE_TICKER = 'GLOBEX'

# Company name
PRACTICE_COMPANY_NAME = 'Globex Corporation'

# IPO date (start of practice data)
PRACTICE_IPO_DATE = '1920-01-01'

# Starting price
START_PRICE = 50.0

def generate_practice_prices():
    """Generate multi-year fictional price history for GLOBEX"""
    prices = {}
    rng = random.Random(421)
    current_price = START_PRICE
    base_date = datetime(1920, 1, 1)

    for step in range(0, 81):
        month_index = step * 3
        year = base_date.year + month_index // 12
        month = (base_date.month - 1 + month_index) % 12 + 1
        date = datetime(year, month, 1)
        date_str = date.strftime('%Y-%m-%d')

        if step < 16:
            drift = 0.055
            shock = rng.uniform(-0.08, 0.10)
        elif step < 28:
            drift = -0.11
            shock = rng.uniform(-0.18, 0.07)
        elif step < 44:
            drift = 0.075
            shock = rng.uniform(-0.10, 0.13)
        elif step < 58:
            drift = -0.035
            shock = rng.uniform(-0.16, 0.11)
        else:
            drift = 0.035
            shock = rng.uniform(-0.12, 0.12)

        if step in {10, 27, 41, 56, 70}:
            shock += rng.choice([-0.28, 0.24, -0.20, 0.18])

        current_price = current_price * (1 + drift + shock)
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