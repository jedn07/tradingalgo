from datetime import datetime, timedelta
import yfinance as yf
import numpy as np
import pandas as pd

class DataPipeline:
    """Handles data loading and preparation"""
    
    def __init__(self):
        self.data = None
    
    def load_data_yfinance(self, symbol, timeframe, start_date=None, end_date=None):
        """Download real data from Yahoo Finance"""
        # Map our symbols to Yahoo Finance tickers
        ticker_map = {
            'NQ': 'NQ=F',  # E-mini Nasdaq-100 futures
            'ES': 'ES=F',  # E-mini S&P 500 futures
            'YM': 'YM=F',  # E-mini Dow futures
            'RTY': 'RTY=F', # E-mini Russell 2000 futures
            'EURUSD': 'EURUSD=X'
        }
        
        ticker = ticker_map.get(symbol)
        interval = timeframe
        
        # Set default dates if not provided
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            # Yahoo Finance limits intraday data to ~60 days
            if interval == '1m':
                start_date = end_date - timedelta(days=7)
            elif interval in ['2m', '5m', '15m', '30m', '60m', '90m', '1h', '4h']:
                start_date = end_date - timedelta(days=59)
            else:
                start_date = end_date - timedelta(days=365)
        
        print(f"Downloading {ticker} data from Yahoo Finance...")
        print(f"Period: {start_date.date()} to {end_date.date()}")
        
        try:
            # Download data from Yahoo Finance
            self.data = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                interval=interval,
                progress=False,
                multi_level_index=False
            )
            
            if self.data.empty:
                print("WARNING: No data returned from Yahoo Finance")
            
            # Rename columns to lowercase for consistency
            self.data.columns = [col.lower() for col in self.data.columns]
            
            # Remove any rows with NaN values
            self.data = self.data.dropna()
            
            print(f"Successfully downloaded {len(self.data)} bars")
            # Add indicators
            self._add_indicators()
        
            print(f"Data loaded: {len(self.data)} bars from {self.data.index[0]} to {self.data.index[-1]}")
            print(self.data)
        except Exception as e:
            print(f"Error downloading data: {e}")
        
    def load_data_local(self):
        self.data=pd.read_csv("EURUSD5.csv", sep="\t", index_col=0, header=None)
        self.data.columns=["close", "high", "low", "open", "volume"]
        print(self.data)


        self._add_indicators()

        print(f"Data loaded: {len(self.data)} bars from {self.data.index[0]} to {self.data.index[-1]}")


    

    def _add_indicators(self):
            """Add technical indicators to the data"""
            # ATR (Average True Range) - for volatility-based stops
            self.data['high_low'] = self.data['high'] - self.data['low']
            self.data['high_close'] = np.abs(self.data['high'] - self.data['close'].shift(1))
            self.data['low_close'] = np.abs(self.data['low'] - self.data['close'].shift(1))
            self.data['true_range'] = self.data[['high_low', 'high_close', 'low_close']].max(axis=1)
            self.data['atr_14'] = self.data['true_range'].rolling(window=14).mean()

            # ATR average for volatility filter
            self.data['atr_avg'] = self.data['atr_14'].rolling(window=50).mean()

            # Exponential Moving Averages (EMAs) for 9/21 crossover strategy
            self.data['ema_9'] = self.data['close'].ewm(span=9, adjust=False).mean()
            self.data['ema_21'] = self.data['close'].ewm(span=21, adjust=False).mean()

            # Simple Moving Averages
            self.data['sma_20'] = self.data['close'].rolling(window=20).mean()
            self.data['sma_50'] = self.data['close'].rolling(window=50).mean()

            # RSI (Relative Strength Index)
            delta = self.data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            self.data['rsi'] = 100 - (100 / (1 + rs))        

            # Price momentum
            self.data['momentum_10'] = self.data['close'] - self.data['close'].shift(10)

            # Clean up temporary columns
            self.data.drop(['high_low', 'high_close', 'low_close', 'true_range'], axis=1, inplace=True)

            print(f"\n✓ Indicators added: EMA 9, EMA 21, ATR 14, ATR Avg, SMA 20, SMA 50, Momentum 10")        