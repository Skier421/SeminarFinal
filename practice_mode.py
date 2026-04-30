"""
Practice Mode Configuration for Historical Stock Market Simulator
Controls whether to use fictional GLOBEX data instead of real historical stocks
"""

# PRACTICE MODE FLAG - Set to True to use fictional GLOBEX data instead of real stocks
PRACTICE_MODE = False

# Import practice data if in practice mode
if PRACTICE_MODE:
    from practice_data import PRACTICE_DATA
    # Override with practice data
    TICKERS = PRACTICE_DATA['tickers']
    COMPANY_NAMES = PRACTICE_DATA['company_names']
    IPO_DATES = PRACTICE_DATA['ipo_dates']
else:
    # Stock tickers to fetch
    TICKERS = ['^DJI', '^GSPC']

    # Company names for display
    COMPANY_NAMES = {
        '^DJI': 'Dow Jones Industrial Average',
        '^GSPC': 'S&P 500'
    }

    # IPO dates for each ticker
    IPO_DATES = {
        '^DJI': '1900-01-01',
        '^GSPC': '1957-03-01'
    }