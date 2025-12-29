"""
Minimal Viable Backtest System
A simple but functional backtesting framework
"""
import pandas as pd
from data_pipeline import DataPipeline
from strategy import Strategy, symbol_specs


class Engine:
    
    def __init__(self, strategy, initial_capital=100000):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.account_value = initial_capital
        
        # Trade tracking
        self.trades = []
        self.equity_curve = []
        self.current_position = None
    
    def run_backtest(self, start_date=None, end_date=None):
        """Run full backtest"""
        print("="*60)
        print("Starting Backtest")
        print("="*60)
        
        # Load data
        pipeline = DataPipeline()
        '''
        pipeline.load_data_yfinance(
            symbol=self.strategy.symbol,
            timeframe=self.strategy.timeframe,
            start_date=start_date,
            end_date=end_date
        ) 
        '''
        pipeline.load_data_local()
        data=pipeline.data
        
        # Run through each bar
        for idx in range(len(data)):
            bar = data.iloc[idx]
            
            # Record equity at each bar
            self.equity_curve.append({
                'timestamp': bar.name,
                'equity': self.account_value,
                'position': 1 if self.current_position else 0
            })
            
            # Check if we should exit existing position
            if self.current_position:
                should_exit, exit_reason = self.strategy.should_exit(data, idx, self.current_position)
                if should_exit:
                    self._exit_trade(data, idx, exit_reason)
            
            # Check if we should enter new position
            elif self.strategy.should_enter(data, idx):
                self._enter_trade(data, idx)
        
        # Close any open position at the end
        if self.current_position:
            self._exit_trade(data, len(data)-1, 'end_of_data')
         
        self._print_results()
        self._save_results()
    
    def _enter_trade(self, data, idx):
        """Enter a new trade"""
        bar = data.iloc[idx]
        
        # Calculate position size
        position_size = self.strategy.calculate_position_size(data, idx, self.account_value)
        
        # Calculate entry price, stop loss, and take profit
        entry_price = bar['close']
        stop_distance = bar['atr_14'] * self.strategy.atr_stop_multiplier
        stop_loss = entry_price - stop_distance
        take_profit = entry_price + (stop_distance * self.strategy.reward_risk_ratio)
        
        self.current_position = {
            'entry_time': bar.name,
            'entry_price': entry_price,
            'position_size': position_size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_equity': self.account_value
        }
        
        #print(f"\n{'LONG':<6} @ {bar.name} | Price: ${entry_price:,.2f} | Size: {position_size} | Stop: ${stop_loss:,.2f}")
    
    def _exit_trade(self, data, idx, reason):
        """Exit current trade"""
        bar = data.iloc[idx]
        pos = self.current_position
        
        # Determine exit price based on reason
        if reason == 'stop_loss':
            exit_price = pos['stop_loss']
        elif reason == 'take_profit':
            exit_price = pos['take_profit']
        else:  # end_of_data
            exit_price = bar['close']
        
        # Calculate P&L
        point_value = symbol_specs[self.strategy.symbol]['point_value']
        price_change = exit_price - pos['entry_price']
        pnl = price_change * pos['position_size'] * point_value
        pnl_pct = (pnl / pos['entry_equity']) * 100
        
        # Update account
        self.account_value += pnl
        
        # Record trade
        trade = {
            'entry_time': pos['entry_time'],
            'exit_time': bar.name,
            'entry_price': pos['entry_price'],
            'exit_price': exit_price,
            'position_size': pos['position_size'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_reason': reason,
            'equity_after': self.account_value
        }
        self.trades.append(trade)
        
        #print(f"EXIT   @ {bar.name} | Price: ${exit_price:,.2f} | P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%) | Reason: {reason}")
        
        self.current_position = None
    
    def _print_results(self):
        """Print backtest results"""
        print("\n" + "="*60)
        print("BACKTEST RESULTS")
        print("="*60)
        
        if not self.trades:
            print("No trades executed")
            return
        
        trades_df = pd.DataFrame(self.trades)
        
        # Calculate metrics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] <= 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        total_pnl = trades_df['pnl'].sum()
        total_return = ((self.account_value - self.initial_capital) / self.initial_capital) * 100
        
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] <= 0]['pnl'].mean() if losing_trades > 0 else 0
        
        print(f"\nInitial Capital:    ${self.initial_capital:,.2f}")
        print(f"Final Capital:      ${self.account_value:,.2f}")
        print(f"Total P&L:          ${total_pnl:,.2f}")
        print(f"Total Return:       {total_return:+.2f}%")
        print(f"\nTotal Trades:       {total_trades}")
        print(f"Winning Trades:     {winning_trades}")
        print(f"Losing Trades:      {losing_trades}")
        print(f"Win Rate:           {win_rate:.1f}%")
        print(f"\nAverage Win:        ${avg_win:,.2f}")
        print(f"Average Loss:       ${avg_loss:,.2f}")
        if avg_loss != 0:
            print(f"Profit Factor:      {abs(avg_win * winning_trades / (avg_loss * losing_trades)):.2f}")
    
    def _save_results(self):
        """Save results to CSV files"""
        try:
            # Save trades
            if self.trades:
                trades_df = pd.DataFrame(self.trades)
                trades_df.to_csv('backtest_trades.csv', index=False)
                print(f"\n✓ Trades saved to 'backtest_trades.csv' ({len(trades_df)} trades)")
            else:
                print(f"\n✗ No trades to save")
            
            # Save equity curve
            if self.equity_curve:
                equity_df = pd.DataFrame(self.equity_curve)
                equity_df.to_csv('backtest_equity_curve.csv', index=False)
                print(f"✓ Equity curve saved to 'backtest_equity_curve.csv' ({len(equity_df)} bars)")
            else:
                print(f"✗ No equity data to save")
                
        except Exception as e:
            print(f"\n✗ Error saving results: {e}")
            import traceback
            traceback.print_exc()



# ============================================================================
# MAIN EXECUTION
# ============================================================================

# Initialize strategy and engine
strat = Strategy()
eng = Engine(strategy=strat, initial_capital=100000)

# Run backtest with real data
eng.run_backtest(
    start_date=None,
    end_date=None
)

print("\n" + "="*60)
print("Backtest complete")
print("="*60)