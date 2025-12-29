import pandas as pd
import numpy as np

symbol_specs = {
    'NQ': {'tick_size': 0.25, 'point_value': 20, 'name': 'E-mini Nasdaq-100'},
    'ES': {'tick_size': 0.25, 'point_value': 50, 'name': 'E-mini S&P 500'},
    'EURUSD': {'tick_size': 0.000001, 'point_value': 10, 'name': 'EURUSD'}
}

class Strategy:
    """
    Simple Moving Average Trend Following Strategy
    
    This is one of the most reliable strategies - it's been profitable for decades.
    Uses the "Golden Cross" and "Death Cross" concept.
    
    Entry:
    - LONG: When 20 SMA crosses above 50 SMA (golden cross)
    - Price must also be above both SMAs
    - No other filters - keep it simple!
    
    Exit:
    - When 20 SMA crosses back below 50 SMA (death cross)
    - OR fixed stop loss / take profit
    
    This strategy:
    - Has fewer trades (more selective)
    - Holds positions longer (catches big moves)
    - Works in trending markets (which your data seems to be)
    """
    
    # Strategy parameters
    symbol = "EURUSD"
    timeframe = "60m"
    
    # SMA periods (adjustable)
    fast_sma_period = 20
    slow_sma_period = 50
    
    # Risk parameters
    risk_per_trade = 0.015  # 1.5% risk (more conservative)
    atr_stop_multiplier = 3.0  # Wide stops for trend following
    reward_risk_ratio = 4.0  # Big targets for big trends
    
    # Exit options
    exit_on_cross = True  # Exit when 20 SMA crosses back below 50 SMA
    use_stop_loss = True  # Use ATR-based stop
    use_take_profit = False  # Don't use fixed target (let winners run)
    
    def __init__(self):
        self.position = None
    
    def should_enter(self, data, idx):
        """Determine if we should enter a trade"""
        if idx < max(self.fast_sma_period, self.slow_sma_period) + 5:
            return False
        
        current = data.iloc[idx]
        previous = data.iloc[idx - 1]
        
        # Check indicators exist
        if pd.isna(current['sma_20']) or pd.isna(current['sma_50']):
            return False
        
        # === GOLDEN CROSS ===
        # Previous bar: 20 SMA was below 50 SMA
        # Current bar: 20 SMA is now above 50 SMA
        was_below = previous['sma_20'] <= previous['sma_50']
        is_above = current['sma_20'] > current['sma_50']
        golden_cross = was_below and is_above
        
        if not golden_cross:
            return False
        
        # === CONFIRMATION: Price Above Both SMAs ===
        price_above_smas = (current['close'] > current['sma_20'] and 
                           current['close'] > current['sma_50'])
        
        if not price_above_smas:
            return False
        
        return True
    
    def should_exit(self, data, idx, position):
        """Determine if we should exit a trade"""
        current = data.iloc[idx]
        previous = data.iloc[idx - 1]
        
        # === EXIT 1: STOP LOSS ===
        if self.use_stop_loss:
            if current['low'] <= position['stop_loss']:
                return True, 'stop_loss'
        
        # === EXIT 2: TAKE PROFIT ===
        if self.use_take_profit and 'take_profit' in position:
            if current['high'] >= position['take_profit']:
                return True, 'take_profit'
        
        # === EXIT 3: DEATH CROSS ===
        if self.exit_on_cross:
            # 20 SMA crosses back below 50 SMA (trend reversal)
            was_above = previous['sma_20'] >= previous['sma_50']
            is_below = current['sma_20'] < current['sma_50']
            death_cross = was_above and is_below
            
            if death_cross:
                return True, 'death_cross'
        
        # === EXIT 4: PRICE BREAKS BELOW 50 SMA ===
        # Emergency exit if price falls significantly
        price_breakdown = current['close'] < current['sma_50']
        if price_breakdown:
            return True, 'sma_breakdown'
        
        return False, None
    
    def calculate_position_size(self, data, idx, account_value):
        """Calculate position size based on risk"""
        current = data.iloc[idx]
        
        # Calculate stop distance
        stop_distance = current['atr_14'] * self.atr_stop_multiplier
        
        # Risk amount in dollars
        risk_amount = account_value * self.risk_per_trade
        
        # Position size
        point_value = symbol_specs[self.symbol]["point_value"]
        position_size = int(risk_amount / (stop_distance * point_value))
        
        return max(1, position_size)