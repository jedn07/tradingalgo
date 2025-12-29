import pandas as pd
import numpy as np

symbol_specs = {
    'NQ': {'tick_size': 0.25, 'point_value': 20, 'name': 'E-mini Nasdaq-100'},
    'ES': {'tick_size': 0.25, 'point_value': 50, 'name': 'E-mini S&P 500'},
    'EURUSD': {'tick_size': 0.000001, 'point_value': 10, 'name': 'EURUSD'}
}

class Strategy:
    """
    Mean Reversion Pullback Strategy
    
    This strategy has typically MUCH higher win rates (60-70%) than trend following.
    
    Concept: Buy pullbacks in an uptrend, sell when price bounces back.
    
    Entry:
    - Price is in uptrend (above 50 SMA)
    - Price pulls back to or below 21 EMA (oversold in uptrend)
    - RSI is below 40 (oversold)
    - Then enters when price shows signs of reversal
    
    Exit:
    - Price reaches 9 EMA (quick target)
    - Stop loss if breaks below recent low
    """
    
    # Strategy parameters
    symbol = "EURUSD"
    timeframe = "60m"
    
    # Risk parameters
    risk_per_trade = 0.02
    atr_stop_multiplier = 2.0
    
    # Mean reversion parameters
    use_mean_reversion = True
    rsi_oversold = 40  # Entry when RSI < this
    rsi_period = 14
    
    # Profit target
    use_ema_target = True  # Exit at 9 EMA
    use_fixed_target = False  # Alternative: fixed R:R
    reward_risk_ratio = 2.0  # If using fixed target
    
    def __init__(self):
        self.position = None
    
    def should_enter(self, data, idx):
        """Determine if we should enter a trade"""
        if idx < 60:
            return False
        
        current = data.iloc[idx]
        previous = data.iloc[idx - 1]
        
        # Check required indicators
        required = ['ema_9', 'ema_21', 'sma_50', 'atr_14', 'rsi']
        if any(pd.isna(current[ind]) for ind in required):
            return False
        
        # === PRIMARY FILTER: UPTREND ===
        in_uptrend = current['close'] > current['sma_50']
        if not in_uptrend:
            return False
        
        # === PULLBACK CONDITION ===
        # Price should be at or below 21 EMA (pullback from uptrend)
        at_or_below_ema21 = current['close'] <= current['ema_21']
        
        # But NOT too far below (avoid falling knives)
        not_too_far = current['close'] > current['ema_21'] - (2 * current['atr_14'])
        
        if not (at_or_below_ema21 and not_too_far):
            return False
        
        # === RSI OVERSOLD ===
        is_oversold = current['rsi'] < self.rsi_oversold
        if not is_oversold:
            return False
        
        # === REVERSAL SIGNAL ===
        # Look for bullish reversal: current bar closes higher than previous
        bullish_close = current['close'] > previous['close']
        
        # Or: bullish candlestick pattern (close in upper half of range)
        candle_range = current['high'] - current['low']
        close_position = (current['close'] - current['low']) / candle_range if candle_range > 0 else 0
        bullish_candle = close_position > 0.6  # Close in upper 40% of range
        
        reversal_signal = bullish_close or bullish_candle
        
        if not reversal_signal:
            return False
        
        return True
    
    def should_exit(self, data, idx, position):
        """Determine if we should exit a trade"""
        current = data.iloc[idx]
        
        # === EXIT 1: STOP LOSS ===
        if current['low'] <= position['stop_loss']:
            return True, 'stop_loss'
        
        # === EXIT 2: TARGET - PRICE REACHES 9 EMA ===
        if self.use_ema_target:
            # Exit when price reaches 9 EMA (mean reversion complete)
            if current['high'] >= current['ema_9']:
                return True, 'ema_target'
        
        # === EXIT 3: FIXED R:R TARGET ===
        if self.use_fixed_target and 'take_profit' in position:
            if current['high'] >= position['take_profit']:
                return True, 'take_profit'
        
        # === EXIT 4: RSI OVERBOUGHT ===
        # Exit if RSI gets overbought (>70) - momentum exhausted
        if current['rsi'] > 70:
            return True, 'overbought'
        
        # === EXIT 5: BREAKDOWN ===
        # Exit if price breaks below 21 EMA significantly
        breakdown = current['close'] < current['ema_21'] - current['atr_14']
        if breakdown:
            return True, 'breakdown'
        
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