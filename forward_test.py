"""
Forward Testing Engine
Implements walk-forward analysis to validate strategy robustness
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data_pipeline import DataPipeline
from strategy import Strategy
from backtest import BacktestEngine
import json


class ForwardTestEngine(BacktestEngine):
    """
    Walk-Forward Testing Engine
    
    Splits data into multiple windows:
    - In-Sample (IS): Used for optimization
    - Out-of-Sample (OOS): Used for validation
    
    Process:
    1. Train on IS period → Find best parameters
    2. Test on OOS period → Validate performance
    3. Roll window forward → Repeat
    """
    
    def __init__(self, strategy, initial_capital=100000):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.account_value = initial_capital
        
        # Walk-forward parameters
        self.in_sample_bars = 10000  # Bars to optimize on
        self.out_sample_bars = 5000  # Bars to test on
        self.step_size = 2500  # How many bars to roll forward
        
        # Results tracking
        self.all_windows = []
        self.combined_trades = []
        self.oos_trades = []  # Only out-of-sample trades
        self.current_position = None
        self.trades=[]

        
    def run_walk_forward(self, param_grid=None):
        """
        Run walk-forward analysis
        
        Args:
            data: Full dataset
            param_grid: Dictionary of parameters to optimize
                       e.g., {'risk_per_trade': [0.01, 0.02, 0.03],
                              'atr_stop_multiplier': [1.5, 2.0, 2.5]}
        """
        print("\n" + "="*70)
        print("WALK-FORWARD ANALYSIS")
        print("="*70)
        # Load data
        pipeline = DataPipeline()
        pipeline.load_data_local()
        data = pipeline.data
    
        print(f"\nTotal data: {len(data)} bars")
        print(f"Period: {data.index[0]} to {data.index[-1]}")

        if param_grid is None:
            # Default parameters to test
            param_grid = {
                'risk_per_trade': [0.015, 0.02, 0.025],
                'atr_stop_multiplier': [2.0, 2.5, 3.0],
                'reward_risk_ratio': [3.0, 4.0, 5.0]
            }
        
        # Calculate number of windows
        total_bars = len(data)
        window_start = 0
        window_num = 1
        
        while window_start + self.in_sample_bars + self.out_sample_bars <= total_bars:
            print(f"\n{'='*70}")
            print(f"WINDOW {window_num}")
            print(f"{'='*70}")
            
            # Define window boundaries
            is_start = window_start
            is_end = window_start + self.in_sample_bars
            oos_start = is_end
            oos_end = oos_start + self.out_sample_bars
            
            is_data = data.iloc[is_start:is_end]
            oos_data = data.iloc[oos_start:oos_end]
            
            print(f"\nIn-Sample Period: {is_data.index[0]} to {is_data.index[-1]}")
            print(f"  Bars: {len(is_data)}")
            print(f"\nOut-of-Sample Period: {oos_data.index[0]} to {oos_data.index[-1]}")
            print(f"  Bars: {len(oos_data)}")
            
            # Step 1: Optimize on in-sample data
            print(f"\nStep 1: Optimizing parameters on in-sample data...")
            best_params, best_score = self._optimize_parameters(is_data, param_grid)
            
            print(f"\nBest Parameters Found:")
            for param, value in best_params.items():
                print(f"  {param}: {value}")
            print(f"  In-Sample Score: {best_score:.2f}")
            
            # Step 2: Test on out-of-sample data with best parameters
            print(f"\nStep 2: Testing on out-of-sample data...")
            oos_results = self._run_single_backtest(oos_data, best_params)
            
            print(f"\nOut-of-Sample Results:")
            print(f"  Trades: {oos_results['total_trades']}")
            print(f"  Win Rate: {oos_results['win_rate']:.1f}%")
            print(f"  Total P&L: ${oos_results['total_pnl']:,.2f}")
            print(f"  Profit Factor: {oos_results['profit_factor']:.2f}")
            
            # Store window results
            self.all_windows.append({
                'window': window_num,
                'is_start': is_data.index[0],
                'is_end': is_data.index[-1],
                'oos_start': oos_data.index[0],
                'oos_end': oos_data.index[-1],
                'best_params': best_params,
                'is_score': best_score,
                'oos_results': oos_results
            })
            
            # Store OOS trades
            self.oos_trades.extend(oos_results['trades'])
            
            # Roll window forward
            window_start += self.step_size
            window_num += 1
        
        print(f"\n{'='*70}")
        print(f"WALK-FORWARD ANALYSIS COMPLETE")
        print(f"{'='*70}")
        print(f"\nTotal Windows: {len(self.all_windows)}")
        
        # Print summary
        self._print_summary()
        self._save_results()
        
    def _optimize_parameters(self, data, param_grid):
        """
        Grid search optimization
        Tests all parameter combinations and returns best
        """
        # Generate all parameter combinations
        param_combinations = self._generate_param_combinations(param_grid)
        
        print(f"  Testing {len(param_combinations)} parameter combinations...")
        
        best_score = -float('inf')
        best_params = None
        
        for i, params in enumerate(param_combinations):
            # Run backtest with these parameters
            results = self._run_single_backtest(data, params)
            
            # Calculate score (you can customize this)
            score = self._calculate_fitness_score(results)
            
            if score > best_score:
                best_score = score
                best_params = params
            
            # Progress indicator
            if (i + 1) % 10 == 0:
                print(f"    Tested {i + 1}/{len(param_combinations)} combinations...")
        
        return best_params, best_score
    
    def _generate_param_combinations(self, param_grid):
        """Generate all combinations of parameters"""
        import itertools
        
        keys = param_grid.keys()
        values = param_grid.values()
        combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
        
        return combinations
    
    def _run_single_backtest(self, data, params):
        """Run a single backtest with given parameters"""
        # Create strategy with custom parameters
        
        # Set parameters
        for param, value in params.items():
            if hasattr(self.strategy, param):
                setattr(self.strategy, param, value)
        
        # Run backtest
        trades = []
        
        for idx in range(len(data)):
            if idx%1000==0:
                print(f'{idx}/{len(data)}')
            bar = data.iloc[idx]
            
            # Check exits
            if self.current_position:
                should_exit, exit_reason = self.strategy.should_exit(data, idx, self.current_position)
                if should_exit:
                    trades.append(self._exit_trade(data, idx, exit_reason))
            # Check entries
            elif self.strategy.should_enter(data, idx):
                self._enter_trade(data, idx)
        
        # Calculate metrics
        if trades:
            trades_df = pd.DataFrame(trades)
            winners = trades_df[trades_df['pnl'] > 0]
            losers = trades_df[trades_df['pnl'] <= 0]
            
            total_pnl = trades_df['pnl'].sum()
            win_rate = (len(winners) / len(trades_df)) * 100 if len(trades_df) > 0 else 0
            
            avg_win = winners['pnl'].mean() if len(winners) > 0 else 0
            avg_loss = losers['pnl'].mean() if len(losers) > 0 else 0
            profit_factor = abs(avg_win * len(winners) / (avg_loss * len(losers))) if avg_loss != 0 and len(losers) > 0 else 0
        else:
            total_pnl = 0
            win_rate = 0
            profit_factor = 0
        
        return {
            'total_trades': len(trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'profit_factor': profit_factor,
            'final_capital': self.account_value,
            'trades': trades
        }
    
    def _calculate_fitness_score(self, results):
        """
        Calculate fitness score for optimization
        
        You can customize this based on what's important to you:
        - Total P&L
        - Sharpe ratio
        - Win rate
        - Profit factor
        - etc.
        """
        # Weighted score
        score = (
            results['total_pnl'] * 0.4 +  # 40% weight on profit
            results['profit_factor'] * 1000 * 0.3 +  # 30% weight on profit factor
            results['win_rate'] * 10 * 0.2 +  # 20% weight on win rate
            results['total_trades'] * 0.1  # 10% weight on trade frequency
        )
        
        return score
    
    def _print_summary(self):
        """Print summary of all windows"""
        print("\n" + "="*70)
        print("SUMMARY OF ALL WINDOWS")
        print("="*70)
        
        total_oos_pnl = sum(w['oos_results']['total_pnl'] for w in self.all_windows)
        avg_oos_win_rate = np.mean([w['oos_results']['win_rate'] for w in self.all_windows])
        total_oos_trades = sum(w['oos_results']['total_trades'] for w in self.all_windows)
        
        print(f"\nOut-of-Sample Performance (Combined):")
        print(f"  Total P&L: ${total_oos_pnl:,.2f}")
        print(f"  Average Win Rate: {avg_oos_win_rate:.1f}%")
        print(f"  Total Trades: {total_oos_trades}")
        print(f"  Return: {(total_oos_pnl / self.initial_capital) * 100:.2f}%")
        
        print(f"\nPer-Window Results:")
        for window in self.all_windows:
            oos = window['oos_results']
            print(f"\n  Window {window['window']}:")
            print(f"    Period: {window['oos_start']} to {window['oos_end']}")
            print(f"    Trades: {oos['total_trades']}")
            print(f"    P&L: ${oos['total_pnl']:,.2f}")
            print(f"    Win Rate: {oos['win_rate']:.1f}%")
    
    def _save_results(self):
        """Save walk-forward results to files"""
        # Save summary
        summary = {
            'total_windows': len(self.all_windows),
            'windows': self.all_windows
        }
        
        with open('walk_forward_summary.json', 'w') as f:
            # Convert datetime objects to strings for JSON
            summary_serializable = json.loads(
                json.dumps(summary, default=str)
            )
            json.dump(summary_serializable, f, indent=2)
        
        print(f"\n✓ Walk-forward summary saved to 'walk_forward_summary.json'")
        
        # Save OOS trades to CSV
        if self.oos_trades:
            oos_df = pd.DataFrame(self.oos_trades)
            oos_df.to_csv('walk_forward_oos_trades.csv', index=False)
            print(f"✓ Out-of-sample trades saved to 'walk_forward_oos_trades.csv'")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":

    print("="*70)
    print("WALK-FORWARD TESTING")
    print("="*70)
    
    strat=Strategy()
    
    # Initialize walk-forward engine
    wf_engine = ForwardTestEngine(
        strategy=strat,
        initial_capital=100000
    )
    
    # Define parameter grid to optimize
    '''
    param_grid = {
        'risk_per_trade': [0.01, 0.015, 0.02],
        'atr_stop_multiplier': [2.0, 2.5, 3.0, 3.5],
        'reward_risk_ratio': [3.0, 4.0, 5.0]
    }
    '''
    param_grid = {
        'risk_per_trade': [0.01, 0.02],
        'atr_stop_multiplier': [1.5, 3.5],
        'reward_risk_ratio': [2.0, 5.0]
    }    
    # Run walk-forward analysis
    wf_engine.run_walk_forward(param_grid)
    
    print("\n" + "="*70)
    print("WALK-FORWARD TESTING COMPLETE")
    print("="*70)