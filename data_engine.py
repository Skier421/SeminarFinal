"""
Data Engine for Historical Stock Market Simulator
Fetches and manages historical stock data using yfinance
With fallback to sample data if yfinance fails
"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, Optional
import json
import os
import time
import pandas as pd

# Stock tickers to fetch
TICKERS = ['^DJI', '^GSPC']

# Inflation multiplier to adjust prices to 2026 dollars
INFLATION_MULTIPLIER = 18.0

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

# Cache file for storing fetched data
CACHE_FILE = 'stock_data_cache.json'

# Fallback prices for Jan 1, 1928 (historical reference)
# These will be multiplied by INFLATION_MULTIPLIER (18.0) to get 2026 values
FALLBACK_PRICES_1928 = {
    '^DJI': 200.00,  # $200 * 18 = $3,600
    '^GSPC': 17.50   # $17.50 * 18 = $315
}


def generate_sample_data():
    """Generate sample historical data for demonstration"""
    print("Generating sample data...")
    
    base_date = datetime(1920, 1, 1)
    end_date = datetime(2024, 12, 31)
    
    # Fallback prices for Jan 1, 1928 (historical reference)
    FALLBACK_PRICES_1928 = {
        '^DJI': 200.00,
        '^GSPC': 17.50
    }
    
    # Sample price data (simplified historical values)
    initial_prices = {
        '^DJI': 100.0,
        '^GSPC': 10.0
    }
    
    ipo_dates = IPO_DATES.copy()
    
    sample_data = {}
    
    for ticker in TICKERS:
        prices = {}
        ipo = datetime.strptime(ipo_dates[ticker], '%Y-%m-%d')
        price = initial_prices[ticker]
        current_date = base_date
        
        while current_date <= end_date:
            if current_date >= ipo:
                date_str = current_date.strftime('%Y-%m-%d')
                
                # Use fallback price for Jan 1, 1928
                if date_str == '1928-01-01':
                    price = FALLBACK_PRICES_1928[ticker]
                    # Apply inflation multiplier
                    price = price * INFLATION_MULTIPLIER
                    prices[date_str] = round(price, 2)
                elif current_date.weekday() < 5:
                    # Skip weekends for stocks
                    # Add realistic variation
                    year = current_date.year
                    
                    # VOLATILITY BOOST: Higher volatility during crisis years (1929-1932, 2008)
                    if 1929 <= year <= 1932 or year == 2008:
                        # +/- 5% per tick during crisis
                        change = (hash(date_str) % 1000 - 500) / 10000
                    else:
                        # Normal volatility +/- 5%
                        change = (hash(date_str) % 100 - 45) / 1000
                    
                    price = price * (1 + change)
                    # Apply inflation multiplier to all prices
                    price = price * INFLATION_MULTIPLIER
                    if price < 0.01:
                        price = 0.01
                    prices[date_str] = round(price, 2)
            
            current_date += timedelta(days=1)
        
        sample_data[ticker] = {
            'prices': prices,
            'ipo_date': ipo_dates[ticker]
        }
        print(f"  Generated {len(prices)} days for {ticker}")
    
    return sample_data


class DataEngine:
    """Manages historical stock data fetching and retrieval"""
    
    def __init__(self):
        self.stock_data: Dict[str, Dict[str, float]] = {}
        self.ipo_dates: Dict[str, str] = {}
        self._load_or_fetch_data()
    
    def _load_or_fetch_data(self):
        """Load cached data or fetch from yfinance"""
        if os.path.exists(CACHE_FILE):
            print("Loading cached stock data...")
            self._load_cache()
            return
        
        print("Attempting to fetch stock data from yfinance...")
        self._fetch_all_data()
        
        # If no data was fetched, generate sample data
        if not self.stock_data:
            print("yfinance unavailable, generating sample data...")
            self._generate_sample_data()
        
        self._save_cache()
    
    def _load_cache(self):
        """Load data from cache file"""
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                self.stock_data = data.get('stock_data', {})
                self.ipo_dates = data.get('ipo_dates', {})
            print(f"Loaded data for {len(self.stock_data)} tickers")
        except Exception as e:
            print(f"Error loading cache: {e}")
            self.stock_data = {}
            self.ipo_dates = {}
    
    def _save_cache(self):
        """Save data to cache file"""
        try:
            data = {
                'stock_data': self.stock_data,
                'ipo_dates': self.ipo_dates
            }
            with open(CACHE_FILE, 'w') as f:
                json.dump(data, f)
            print("Stock data cached successfully")
        except Exception as e:
            print(f"Error saving cache: {e}")
    
    def _fetch_all_data(self):
        """Fetch historical data for all tickers"""
        for ticker in TICKERS:
            self._fetch_ticker_data(ticker)
            time.sleep(0.5)
    
    def _fetch_ticker_data(self, ticker: str):
        """Fetch historical data for a single ticker"""
        try:
            print(f"Fetching {ticker}...")
            stock = yf.Ticker(ticker)
            hist = stock.history(period="max")
            
            if hist.empty:
                hist = stock.history(start="1920-01-01", end="2024-12-31")
            
            if hist.empty:
                print(f"  No data available for {ticker}")
                return
            
            prices = {}
            for date, row in hist.iterrows():
                if pd.notna(row['Close']):
                    date_str = date.strftime('%Y-%m-%d')
                    
                    # Use fallback price for Jan 1, 1928 (historical reference)
                    if date_str == '1928-01-01' and ticker in FALLBACK_PRICES_1928:
                        # $200 * 18 = $3,600 for Dow Jones
                        price = FALLBACK_PRICES_1928[ticker]
                    else:
                        # Apply inflation multiplier to convert to 2026 dollars
                        price = float(row['Close']) * INFLATION_MULTIPLIER
                    
                    prices[date_str] = round(price, 2)
            
            if prices:
                self.stock_data[ticker] = prices
                
                # Fill in missing dates between 1928 and fetched data range
                # (must be done BEFORE adding 1928-01-01 fallback)
                self._fill_missing_dates(ticker, prices)
                
                # Add fallback price for 1928-01-01 if not in fetched data
                if '1928-01-01' not in prices and ticker in FALLBACK_PRICES_1928:
                    # Apply inflation multiplier: $200 * 18 = $3,600
                    prices['1928-01-01'] = FALLBACK_PRICES_1928[ticker] * INFLATION_MULTIPLIER
                    self.stock_data[ticker] = prices
                
                # Use historical IPO dates, not the fetched data range
                self.ipo_dates[ticker] = IPO_DATES.get(ticker, min(prices.keys()))
                print(f"  {ticker}: {len(prices)} days, IPO: {self.ipo_dates[ticker]}")
                
        except Exception as e:
            print(f"  Error fetching {ticker}: {e}")
    
    def _generate_sample_data(self):
        """Generate sample data when yfinance fails"""
        sample = generate_sample_data()
        
        for ticker, data in sample.items():
            self.stock_data[ticker] = data['prices']
            self.ipo_dates[ticker] = data['ipo_date']
    
    def _fill_missing_dates(self, ticker: str, prices: Dict[str, float]):
        """Fill in missing dates between 1928 and fetched data range with sample data"""
        if not prices:
            return
        
        # Get the date range
        sorted_dates = sorted(prices.keys())
        first_date = sorted_dates[0]
        last_date = sorted_dates[-1]
        
        # Only fill if we have a gap between 1928 and the fetched data
        if first_date > '1928-01-01' and ticker in FALLBACK_PRICES_1928:
            # Start from the fallback price
            current_price = FALLBACK_PRICES_1928[ticker] * INFLATION_MULTIPLIER
            
            # Calculate target price (first fetched price)
            target_price = prices[first_date]
            
            # Generate daily prices from 1928 to first fetched date
            start = datetime.strptime('1928-01-01', '%Y-%m-%d')
            end = datetime.strptime(first_date, '%Y-%m-%d')
            
            total_days = (end - start).days
            if total_days <= 0:
                return
            
            # Calculate daily growth rate to reach target
            daily_growth = (target_price / current_price) ** (1 / total_days) - 1
            
            current = start
            while current < end:
                date_str = current.strftime('%Y-%m-%d')
                
                if date_str not in prices:
                    year = current.year
                    days_from_start = (current - start).days
                    
                    # VOLATILITY BOOST: Higher volatility during crisis years (1929-1932, 2008)
                    if 1929 <= year <= 1932 or year == 2008:
                        # +/- 2% per day during crisis
                        change = (hash(date_str) % 100 - 50) / 2500
                    else:
                        # Normal volatility +/- 0.5%
                        change = (hash(date_str) % 100 - 50) / 10000
                    
                    # Apply growth + volatility
                    current_price = current_price * (1 + daily_growth + change)
                    if current_price < 0.01:
                        current_price = 0.01
                    prices[date_str] = round(current_price, 2)
                
                current += timedelta(days=1)
            
            self.stock_data[ticker] = prices
    
    def get_price(self, ticker: str, date: str) -> Optional[float]:
        # S&P 500 (^GSPC) not available before 1957-03-01
        if ticker == '^GSPC' and date < '1957-03-01':
            return None

        if ticker not in self.stock_data:
            return None

        ipo_date = self.ipo_dates.get(ticker)
        if ipo_date and date < ipo_date:
            return None

        if date in self.stock_data[ticker]:
            return self.stock_data[ticker][date]

        return self._find_closest_price(ticker, date)
    
    def _find_closest_price(self, ticker: str, target_date: str) -> Optional[float]:
        """Find the closest trading day price before or on the target date"""
        prices = self.stock_data.get(ticker, {})
        if not prices:
            return None
        
        target = datetime.strptime(target_date, '%Y-%m-%d')
        
        valid_dates = []
        for date_str in prices.keys():
            date = datetime.strptime(date_str, '%Y-%m-%d')
            if date <= target:
                valid_dates.append(date)
        
        if not valid_dates:
            return None
        
        closest = max(valid_dates)
        return prices[closest.strftime('%Y-%m-%d')]
    
    def is_available(self, ticker: str, date: str) -> bool:
        """Check if a stock is available for trading on a given date"""
        ipo_date = self.ipo_dates.get(ticker)
        if not ipo_date:
            return False
        return date >= ipo_date
    
    def get_ipo_date(self, ticker: str) -> Optional[str]:
        """Get the IPO date for a ticker"""
        return self.ipo_dates.get(ticker)
    
    def get_all_prices(self, date: str) -> Dict[str, float]:
        """Get all stock prices for a given date"""
        prices = {}
        for ticker in TICKERS:
            price = self.get_price(ticker, date)
            if price is not None:
                prices[ticker] = price
        return prices
    
    def get_company_name(self, ticker: str) -> str:
        """Get the company name for a ticker"""
        return COMPANY_NAMES.get(ticker, ticker)
    
    def get_tickers(self) -> list:
        """Get list of all tickers"""
        return TICKERS.copy()
    
    def get_available_tickers(self, date: str) -> list:
        """Get list of tickers available for trading on a given date"""
        available = []
        for ticker in TICKERS:
            if self.is_available(ticker, date):
                available.append(ticker)
        return available
    
    def get_date_range(self) -> tuple:
        """Get the earliest and latest dates available"""
        baseline_start = '1920-01-01'
        all_dates = set()
        for prices in self.stock_data.values():
            all_dates.update(prices.keys())
        
        if not all_dates:
            return (baseline_start, '2024-12-31')
        
        return (baseline_start, max(all_dates))


# Global data engine instance
data_engine = DataEngine()