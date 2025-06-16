import backtrader as bt
import pandas as pd
from datetime import datetime
import json
import numpy as np
import os
import csv
import matplotlib
matplotlib.use('Agg')

import sys
sys.path.append('/app')
from data_manager import download_data, preprocess_data
from strategy_configurator import load_strategy_config, generate_backtrader_strategy_class
# Import new reporting functions for stats
from reporting import plot_equity_curve, calculate_trade_statistics, generate_text_report

TEMP_EQUITY_FILE = "temp_equity_data.csv"
TEMP_TRADES_FILE = "temp_trades_data.json"

def run_backtest(data_df, strategy_class, strategy_params, initial_cash=100000.0):
    if data_df is None or data_df.empty:
        print("Error: Data for backtesting is empty or None."); return None
    if not isinstance(data_df.index, pd.DatetimeIndex):
        print("Error: Dataframe index must be a DatetimeIndex."); return None

    df_feed = data_df.copy()
    df_feed.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)
    df_feed.index.name = 'datetime'
    if 'openinterest' not in df_feed.columns: df_feed['openinterest'] = 0

    data_feed = bt.feeds.PandasData(dataname=df_feed)
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.adddata(data_feed)

    try:
        cerebro.addstrategy(strategy_class, **strategy_params)
    except Exception as e:
        print(f"Error adding strategy to Cerebro: {e}"); return None

    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=0.001)
    print(f"Starting portfolio value: {cerebro.broker.getvalue():.2f}")

    analysis_results = {
        "initial_cash": initial_cash, "final_portfolio_value": initial_cash, "pnl": 0,
        "daily_equity": [], "trades_log": [],
        "notes": "Backtest did not complete successfully or strategy did not save files."
    }

    try:
        cerebro.run()
        loaded_equity = []
        try:
            with open(TEMP_EQUITY_FILE, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row: loaded_equity.append(float(row[0]))
            analysis_results["daily_equity"] = loaded_equity
            print(f"Successfully loaded equity data from {TEMP_EQUITY_FILE}")
        except FileNotFoundError: print(f"Warning: Equity file {TEMP_EQUITY_FILE} not found.")
        except Exception as e: print(f"Error loading equity data: {e}")

        loaded_trades = []
        try:
            with open(TEMP_TRADES_FILE, 'r') as f: loaded_trades = json.load(f)
            analysis_results["trades_log"] = loaded_trades
            print(f"Successfully loaded trades data from {TEMP_TRADES_FILE}")
        except FileNotFoundError: print(f"Warning: Trades file {TEMP_TRADES_FILE} not found.")
        except Exception as e: print(f"Error loading trades data: {e}")

        analysis_results["final_portfolio_value"] = cerebro.broker.getvalue()
        analysis_results["pnl"] = analysis_results["final_portfolio_value"] - initial_cash
        analysis_results["notes"] = "Backtest completed."

        if analysis_results["daily_equity"]:
            plot_equity_curve(analysis_results["daily_equity"],
                              title="Backtest Equity Curve",
                              filename="reports/backtest_equity_curve.png")
        else: print("Skipping equity plot: no daily equity data.")
    except Exception as e:
        print(f"Critical error during backtest: {e}")
        current_value = cerebro.broker.getvalue() if hasattr(cerebro, 'broker') else initial_cash
        analysis_results["final_portfolio_value"] = current_value
        analysis_results["pnl"] = current_value - initial_cash
        analysis_results["notes"] = f"Backtest failed/interrupted: {e}."
    finally:
        for temp_file in [TEMP_EQUITY_FILE, TEMP_TRADES_FILE]:
            if os.path.exists(temp_file):
                try: os.remove(temp_file); print(f"Cleaned up {temp_file}")
                except Exception as e: print(f"Error deleting {temp_file}: {e}")
    return analysis_results

if __name__ == '__main__':
    print("--- Backtesting Engine with Manual Metrics, Plotting & Stats ---")
    print("\n1. Loading and preprocessing data...")
    raw_data = download_data(symbol='MSFT', start_date='2022-01-01', end_date='2023-01-01', source='yahoo')
    if raw_data is None or raw_data.empty:
        print("Failed to download MSFT data. Using dummy data...")
        idx = pd.date_range(start='2022-01-01', end='2023-01-01', freq='B')
        raw_data = pd.DataFrame({
            ('Price', 'Open'): [150 + i/10 for i in range(len(idx))],
            ('Price', 'High'): [152 + i/10 for i in range(len(idx))],
            ('Price', 'Low'): [148 + i/10 for i in range(len(idx))],
            ('Price', 'Close'): [150 + i/5 + (np.sin(i/20.0) * 20) for i in range(len(idx))],
            ('Price', 'Volume'): [1000000 + i*1000 for i in range(len(idx))]
        }, index=idx); raw_data.index.name = 'Date'
    preprocessed_data = preprocess_data(raw_data)
    if preprocessed_data is None or preprocessed_data.empty: print("Data preprocessing failed."); exit()
    print(f"Data loaded/preprocessed. Shape: {preprocessed_data.shape}")

    print("\n2. Loading RSI strategy configuration...")
    rsi_config = load_strategy_config("test_rsi_backtrader.json")
    if rsi_config is None: print("Failed to load 'test_rsi_backtrader.json'. Run strategy_configurator.py."); exit()

    print("\n3. Generating Backtrader strategy class...")
    BtRSIStrategyClass = generate_backtrader_strategy_class(rsi_config)
    if BtRSIStrategyClass is None: print("Failed to generate Backtrader RSI strategy class."); exit()
    print(f"Strategy class: {BtRSIStrategyClass.__name__}")

    print("\n4. Running backtest...")
    strategy_parameters = rsi_config.get('params', {})
    backtest_summary = run_backtest(
        data_df=preprocessed_data, strategy_class=BtRSIStrategyClass,
        strategy_params=strategy_parameters, initial_cash=100000.0)

    if backtest_summary:
        print("\n--- Backtest Summary (from files) ---")
        print(f"Initial Cash: {backtest_summary['initial_cash']:.2f}")
        print(f"Final Portfolio Value: {backtest_summary['final_portfolio_value']:.2f}")
        print(f"PnL: {backtest_summary['pnl']:.2f}")
        print(f"Notes: {backtest_summary['notes']}")

        # Calculate and generate text report for trade statistics
        trade_stats = calculate_trade_statistics(
            backtest_summary['trades_log'],
            backtest_summary['initial_cash'],
            backtest_summary['final_portfolio_value']
        )
        stats_filename = "reports/backtest_trade_stats.txt"
        generate_text_report(trade_stats, filename=stats_filename)
        print(f"Trade statistics report saved to {stats_filename}")

        print(f"\nNumber of Trades Logged: {len(backtest_summary['trades_log'])}")
        print(f"Number of Daily Equity Points: {len(backtest_summary['daily_equity'])}")
        print("\nFirst 3 Logged Trades (if any):")
        for i, trade in enumerate(backtest_summary['trades_log'][:3]):
            print(f"  Trade {i+1}: {trade}")
        if backtest_summary['daily_equity']:
             print(f"Equity curve plot was generated at reports/backtest_equity_curve.png")
        else: print("No equity data to plot.")
    else:
        print("\nBacktest execution failed or returned no summary.")
    print("\n--- Backtesting Engine Demonstration Finished ---")
