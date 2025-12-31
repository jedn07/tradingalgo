import pandas as pd
import numpy as np

symbol_specs = {
    'NQ': {'tick_size': 0.25, 'point_value': 20, 'name': 'E-mini Nasdaq-100'},
    'ES': {'tick_size': 0.25, 'point_value': 50, 'name': 'E-mini S&P 500'},
    'EURUSD': {'tick_size': 0.00001, 'point_value': 10, 'name': 'EURUSD'}
}

class Strategy:
    """
    Enhanced 9/21 EMA Crossover Strategy with Multiple Filters
    
    Entry: 
    - LONG: When 9 EMA crosses above 21 EMA (bullish crossover)
    - Filter 1: Price must be above 50 SMA (long-term trend filter)
    - Filter 2: ATR must be above average (avoid low volatility/choppy markets)
    - Filter 3: Strong momentum confirmation
    - Filter 4: Both EMAs must be sloping up (not flat)
    
    Exit: 
    - Trailing stop based on ATR
    - Take profit at risk/reward ratio
    - Exit when 9 EMA crosses back below 21 EMA
    """
    
    # Strategy parameters
    symbol = "EURUSD"
    timeframe = "5m"
    
    # EMA parameters
    fast_ema_period = 9
    slow_ema_period = 21
    
    # Risk parameters
    risk_per_trade = 0.005  # Risk 2% of account per trade
    atr_stop_multiplier = 2.5  # Wider stops at 2x ATR (was 1.5)
    reward_risk_ratio = 1.5  # Moderate profit target at 2.5x the risk (was 3.0)
    
    # Filter parameters
    use_trend_filter = True  # Require price > 50 SMA
    use_volatility_filter = True  # Require ATR > average
    use_momentum_filter = True  # Require strong momentum
    use_ema_slope_filter = True  # Require EMAs sloping up
    use_pullback_filter = True  # Wait for pullback before entry (NEW!)
    
    # Minimum ATR multiplier for volatility filter
    min_atr_multiplier = 1.0  # ATR must be >= average (was 0.8)
    
    # Pullback parameters
    pullback_lookback = 3  # Wait for price to pull back within last N bars
    
    # Trailing stop
    use_trailing_stop = True
    trailing_stop_activation = 1.2  # Activate after 1.2x risk in profit (was 1.5)
    trailing_stop_distance = 1.2  # Trail by 1.2x ATR (was 1.0)
    
    def __init__(self):
        self.position = None
        self.highest_profit = 0  # Track highest profit for trailing stop
    
    def should_enter(self, data, idx):
        """Determine if we should enter a trade"""
        if idx < 60:  # Need enough data for all indicators
            return False
        
        current = data.iloc[idx]
        previous = data.iloc[idx - 1]
        
        # Check if we have valid indicators
        required_indicators = ['ema_9', 'ema_21', 'atr_14', 'sma_50', 'atr_avg']
        if any(pd.isna(current[ind]) for ind in required_indicators):
            return False
        
        # === CROSSOVER DETECTION ===
        recent_crossover=False
        # Check if we're in bullish territory 
        if current['ema_9'] > current['ema_21']:
            # Look back to see if there was a crossover recently
            for lookback in range(0, 6):  # Check last 6 bars (including current)
                if idx - lookback < 0:
                    break
                prev = data.iloc[idx - lookback]
                prev_prev = data.iloc[idx - lookback - 1]
                if prev_prev['ema_9'] <= prev_prev['ema_21'] and prev['ema_9'] > prev['ema_21']:
                    recent_crossover = True
                    break
        
        if not recent_crossover:
            return False
        
        # === FILTER 1: LONG-TERM TREND ===
        if self.use_trend_filter:
            long_term_uptrend = current['close'] > current['sma_50']
            # Also check that 21 EMA is above 50 SMA (strong trend)
            ema21_above_sma50 = current['ema_21'] > current['sma_50']
            if not (long_term_uptrend and ema21_above_sma50):
                return False
        
        # === FILTER 2: VOLATILITY ===
        if self.use_volatility_filter:
            # Only trade when volatility is sufficient (not choppy/ranging)
            sufficient_volatility = current['atr_14'] >= (current['atr_avg'] * self.min_atr_multiplier)
            if not sufficient_volatility:
                return False
        
        # === FILTER 3: MOMENTUM ===
        if self.use_momentum_filter:
            # Require strong positive momentum
            strong_momentum = current['momentum_10'] > 0
            # Also check momentum is accelerating
            momentum_increasing = current['momentum_10'] > previous['momentum_10']
            if not (strong_momentum and momentum_increasing):
                return False
        
        # === FILTER 4: EMA SLOPE ===
        if self.use_ema_slope_filter:
            # Both EMAs should be trending up (not flat)
            ema9_slope_positive = current['ema_9'] > previous['ema_9']
            ema21_slope_positive = current['ema_21'] > previous['ema_21']
            if not (ema9_slope_positive and ema21_slope_positive):
                return False
        
        # === FILTER 5: PULLBACK (NEW!) ===
        if self.use_pullback_filter:
            # Don't chase - wait for a small pullback/consolidation
            # Check if price pulled back at least once in last N bars
            had_pullback = False
            for lookback in range(1, self.pullback_lookback + 1):
                if idx - lookback < 0:
                    break
                past_bar = data.iloc[idx - lookback]
                # Pullback = price went below 9 EMA or closed lower
                if past_bar['low'] < past_bar['ema_9'] or past_bar['close'] < data.iloc[idx - lookback - 1]['close']:
                    had_pullback = True
                    break
            
            # Only enter if we had a pullback (not parabolic move)
            if not had_pullback:
                return False
        
        # === ADDITIONAL CONFIRMATION ===
        # Price should be above both EMAs (but not too far - avoid chasing)
        price_above_emas = current['close'] > current['ema_9'] and current['close'] > current['ema_21']
        
        # Don't enter if price is too far from EMAs (overextended)
        distance_from_ema9 = (current['close'] - current['ema_9']) / current['atr_14']
        not_overextended = distance_from_ema9 < 2.0  # Within 2 ATRs of 9 EMA
        
        if not (price_above_emas and not_overextended):
            return False
        
        # === EMA SEPARATION CHECK ===
        # EMAs should have good separation (not too close = weak signal)
        ema_separation = (current['ema_9'] - current['ema_21']) / current['atr_14']
        sufficient_separation = ema_separation > 0.1  # At least 10% of ATR
        
        if not sufficient_separation:
            return False
        
        # All filters passed!
        self.highest_profit = 0  # Reset trailing stop tracker
        return True
    
    def should_exit(self, data, idx, position):
        """Determine if we should exit a trade"""
        current = data.iloc[idx]
        previous = data.iloc[idx - 1]
        
        # Calculate current profit
        current_profit = (current['close'] - position['entry_price']) * position['position_size'] * symbol_specs[self.symbol]['point_value']
        
        # Update highest profit for trailing stop
        if current_profit > self.highest_profit:
            self.highest_profit = current_profit
        
        # === EXIT 1: STOP LOSS ===
        if current['low'] <= position['stop_loss']:
            return True, 'stop_loss'
        
        # === EXIT 2: TAKE PROFIT ===
        if current['high'] >= position['take_profit']:
            return True, 'take_profit'
        
        # === EXIT 3: TRAILING STOP ===
        if self.use_trailing_stop:
            # Activate trailing stop after reaching certain profit
            risk_amount = (position['entry_price'] - position['stop_loss']) * position['position_size'] * symbol_specs[self.symbol]['point_value']
            
            if self.highest_profit > (risk_amount * self.trailing_stop_activation):
                # Calculate trailing stop level
                trailing_stop_distance = current['atr_14'] * self.trailing_stop_distance
                trailing_stop_level = current['close'] - trailing_stop_distance
                
                # If we have a valid trailing stop and price hits it
                if trailing_stop_level > position['stop_loss']:
                    if current['low'] <= trailing_stop_level:
                        return True, 'trailing_stop'
        
        # === EXIT 4: OPPOSITE CROSSOVER ===
        was_above = previous['ema_9'] >= previous['ema_21']
        is_below = current['ema_9'] < current['ema_21']
        bearish_crossover = was_above and is_below
        
        if bearish_crossover:
            return True, 'opposite_crossover'
        
        # === EXIT 5: MOMENTUM REVERSAL ===
        # Exit if strong negative momentum appears
        #if current['momentum_10'] < -current['atr_14']:
        #    return True, 'momentum_reversal'
        
        return False, None
    
    def calculate_position_size(self, data, idx, account_value):
        """Calculate position size based on risk"""
        current = data.iloc[idx]
        
        # Calculate stop distance
        stop_distance = current['atr_14'] * self.atr_stop_multiplier
        
        # Risk amount in dollars
        risk_amount = account_value * self.risk_per_trade
        
        # Position size = Risk Amount / Stop Distance
        point_value = symbol_specs[self.symbol]["point_value"]
        position_size = int(risk_amount / (stop_distance * point_value))
        
        return max(1, position_size)  # At least 1 contract