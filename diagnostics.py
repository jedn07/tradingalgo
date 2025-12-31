"""
Backtest Reality Check Diagnostics
Identifies common issues that cause unrealistic returns
"""
import pandas as pd
from backtest import BacktestEngine
from strategy import Strategy
from data_pipeline import DataPipeline


def run_diagnostics():
    """Run comprehensive diagnostics on backtest"""
    
    print("="*70)
    print("BACKTEST REALITY CHECK - DIAGNOSTICS")
    print("="*70)
    
    # Load data
    pipeline = DataPipeline()
    pipeline.load_data_local()
    data = pipeline.data
    
    print(f"\n1. DATA VALIDATION")
    print("-"*70)
    print(f"Total bars: {len(data)}")
    print(f"Date range: {data.index[0]} to {data.index[-1]}")
    print(f"Price range: {data['close'].min():.5f} to {data['close'].max():.5f}")
    print(f"Average price: {data['close'].mean():.5f}")
    
    # Check for data issues
    price_jumps = data['close'].pct_change().abs()
    large_moves = price_jumps[price_jumps > 0.05]  # >5% moves
    if len(large_moves) > 0:
        print(f"\n⚠️  WARNING: Found {len(large_moves)} bars with >5% price moves")
        print("This could indicate data quality issues or gaps")
        print("Sample dates:", large_moves.head().index.tolist())
    
    # Check ATR values
    print(f"\nATR Statistics:")
    print(f"  Average ATR: {data['atr_14'].mean():.5f}")
    print(f"  Min ATR: {data['atr_14'].min():.5f}")
    print(f"  Max ATR: {data['atr_14'].max():.5f}")
    
    # Run backtest
    print(f"\n2. RUNNING BACKTEST")
    print("-"*70)
    
    strat = Strategy()
    eng = BacktestEngine(strategy=strat, initial_capital=100000)
    eng.run_backtest()
    
    if not eng.trades:
        print("No trades executed - cannot diagnose")
        return
    
    trades_df = pd.DataFrame(eng.trades)
    
    # Detailed trade analysis
    print(f"\n3. TRADE ANALYSIS")
    print("-"*70)
    
    print(f"\nTotal trades: {len(trades_df)}")
    print(f"Trades per month: {len(trades_df) / 12:.1f}")
    
    # Check for suspiciously high wins
    winners = trades_df[trades_df['pnl'] > 0]
    losers = trades_df[trades_df['pnl'] <= 0]
    
    print(f"\nWinners: {len(winners)} ({len(winners)/len(trades_df)*100:.1f}%)")
    print(f"Losers: {len(losers)} ({len(losers)/len(trades_df)*100:.1f}%)")
    
    if len(winners) > 0:
        print(f"\nWinning trades:")
        print(f"  Average: ${winners['pnl'].mean():,.2f}")
        print(f"  Median: ${winners['pnl'].median():,.2f}")
        print(f"  Largest: ${winners['pnl'].max():,.2f}")
        print(f"  Smallest: ${winners['pnl'].min():,.2f}")
    
    if len(losers) > 0:
        print(f"\nLosing trades:")
        print(f"  Average: ${losers['pnl'].mean():,.2f}")
        print(f"  Median: ${losers['pnl'].median():,.2f}")
        print(f"  Largest loss: ${losers['pnl'].min():,.2f}")
    
    # Check win/loss ratio
    if len(winners) > 0 and len(losers) > 0:
        avg_win_loss_ratio = abs(winners['pnl'].mean() / losers['pnl'].mean())
        print(f"\nAverage Win/Loss Ratio: {avg_win_loss_ratio:.2f}x")
        if avg_win_loss_ratio > 5:
            print("⚠️  WARNING: Win/loss ratio > 5x is suspicious")
    
    # Check position sizes
    print(f"\n4. POSITION SIZE ANALYSIS")
    print("-"*70)
    print(f"Average position size: {trades_df['position_size'].mean():.2f} contracts")
    print(f"Min position size: {trades_df['position_size'].min()}")
    print(f"Max position size: {trades_df['position_size'].max()}")
    
    if trades_df['position_size'].max() > 100:
        print("⚠️  WARNING: Position sizes > 100 contracts seems very high")
        print("Check if point_value is correct for your instrument")
    
    # Check for look-ahead bias
    print(f"\n5. LOOK-AHEAD BIAS CHECK")
    print("-"*70)
    
    # Sample a few trades and verify entry/exit logic
    sample_trades = trades_df.head(5)
    print("Checking first 5 trades for potential issues...")
    
    for idx, trade in sample_trades.iterrows():
        entry_time = trade['entry_time']
        exit_time = trade['exit_time']
        
        # Find the bars
        entry_bar = data[data.index == entry_time].iloc[0]
        exit_bar = data[data.index == exit_time].iloc[0]
        
        # Check if exit price is within the bar's range
        if trade['exit_reason'] == 'stop_loss':
            if trade['exit_price'] > exit_bar['high'] or trade['exit_price'] < exit_bar['low']:
                print(f"⚠️  Trade {idx}: Stop loss price {trade['exit_price']:.5f} outside bar range [{exit_bar['low']:.5f}, {exit_bar['high']:.5f}]")
        
        if trade['exit_reason'] == 'take_profit':
            if trade['exit_price'] > exit_bar['high'] or trade['exit_price'] < exit_bar['low']:
                print(f"⚠️  Trade {idx}: Take profit price {trade['exit_price']:.5f} outside bar range [{exit_bar['low']:.5f}, {exit_bar['high']:.5f}]")
    
    # Check point value calculation
    print(f"\n6. POINT VALUE VERIFICATION")
    print("-"*70)
    
    from strategy import symbol_specs
    point_value = symbol_specs[strat.symbol]['point_value']
    print(f"Symbol: {strat.symbol}")
    print(f"Point value: {point_value}")
    
    # Calculate what a 1-point move should be worth
    sample_trade = trades_df.iloc[0]
    price_change = sample_trade['exit_price'] - sample_trade['entry_price']
    calculated_pnl = price_change * sample_trade['position_size'] * point_value
    actual_pnl = sample_trade['pnl']
    
    print(f"\nSample trade verification:")
    print(f"  Entry: {sample_trade['entry_price']:.5f}")
    print(f"  Exit: {sample_trade['exit_price']:.5f}")
    print(f"  Price change: {price_change:.5f}")
    print(f"  Position size: {sample_trade['position_size']}")
    print(f"  Calculated P&L: ${calculated_pnl:,.2f}")
    print(f"  Actual P&L: ${actual_pnl:,.2f}")
    
    if abs(calculated_pnl - actual_pnl) > 0.01:
        print("⚠️  WARNING: P&L calculation mismatch!")
    
    # For EURUSD specifically
    if strat.symbol == 'EURUSD':
        print(f"\n🔍 EURUSD SPECIFIC CHECK:")
        print(f"  EURUSD typically trades around 1.0000 - 1.2000")
        print(f"  Your data range: {data['close'].min():.5f} to {data['close'].max():.5f}")
        print(f"  Point value {point_value} = $10 per pip for standard lot")
        print(f"  A 0.00001 move (1 pip) should = ${point_value * 0.0001:.2f} per contract")
        
        # Check if using correct pip size
        typical_atr = data['atr_14'].mean()
        print(f"\n  Your average ATR: {typical_atr:.5f}")
        if typical_atr < 0.0001:
            print("  ⚠️  WARNING: ATR seems too small - might be using wrong decimal places")
        elif typical_atr > 0.01:
            print("  ⚠️  WARNING: ATR seems too large - might be using wrong decimal places")
    
    # Calculate realistic expectation
    print(f"\n7. REALITY CHECK")
    print("-"*70)
    
    total_return = ((eng.account_value - eng.initial_capital) / eng.initial_capital) * 100
    print(f"Your return: {total_return:.2f}%")
    
    print(f"\nTypical professional trader returns:")
    print(f"  Excellent year: 20-50%")
    print(f"  Good year: 10-20%")
    print(f"  Acceptable: 5-10%")
    print(f"  World's best (consistently): 20-30% CAGR")
    
    if total_return > 100:
        print(f"\n⚠️  CRITICAL: {total_return:.0f}% is unrealistic!")
        print("Most likely causes:")
        print("  1. Wrong point_value for instrument")
        print("  2. Position sizing bug (sizes too large)")
        print("  3. Data quality issues")
        print("  4. Look-ahead bias in strategy")
        print("  5. Overfitting to this specific dataset")
    
    # Check consecutive wins
    print(f"\n8. CONSISTENCY CHECK")
    print("-"*70)
    
    # Find longest win/loss streaks
    trades_df['is_win'] = trades_df['pnl'] > 0
    streaks = []
    current_streak = 1
    
    for i in range(1, len(trades_df)):
        if trades_df.iloc[i]['is_win'] == trades_df.iloc[i-1]['is_win']:
            current_streak += 1
        else:
            streaks.append(current_streak)
            current_streak = 1
    streaks.append(current_streak)
    
    print(f"Longest winning streak: {max([s for i, s in enumerate(streaks) if trades_df.iloc[i]['is_win']])} trades")
    print(f"Longest losing streak: {max([s for i, s in enumerate(streaks) if not trades_df.iloc[i]['is_win']])} trades")
    
    # Exit reason distribution
    print(f"\n9. EXIT REASON ANALYSIS")
    print("-"*70)
    exit_reasons = trades_df['exit_reason'].value_counts()
    print(exit_reasons)
    
    if 'take_profit' in exit_reasons:
        tp_pct = (exit_reasons['take_profit'] / len(trades_df)) * 100
        if tp_pct > 70:
            print(f"\n⚠️  WARNING: {tp_pct:.0f}% of trades hit take profit")
            print("This is suspicious - real trading rarely achieves this")
    
    # Final recommendations
    print(f"\n10. RECOMMENDATIONS")
    print("="*70)
    
    if total_return > 100:
        print("\n🔴 HIGH PRIORITY FIXES NEEDED:")
        print("1. Verify point_value in strategy.py symbol_specs")
        print("2. Check your EURUSD CSV data format and decimal places")
        print("3. Reduce position sizes or risk_per_trade")
        print("4. Run walk-forward test to check for overfitting")
        print("\n5. Try these parameter changes:")
        print("   risk_per_trade = 0.005  # 0.5% instead of 2%")
        print("   atr_stop_multiplier = 3.0  # Wider stops")
        print("   reward_risk_ratio = 1.5  # More realistic targets")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    run_diagnostics()