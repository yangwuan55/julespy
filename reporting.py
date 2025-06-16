import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd
import os
import json
import numpy as np
from datetime import datetime

REPORTS_DIR = "reports"

def _ensure_reports_dir():
    if not os.path.exists(REPORTS_DIR):
        print(f"Creating directory: {REPORTS_DIR}")
        os.makedirs(REPORTS_DIR)

def plot_equity_curve(equity_data, title="Equity Curve", filename="reports/equity_curve.png"):
    _ensure_reports_dir()
    if not equity_data:
        print("No equity data to plot."); return
    timestamps, values = None, []
    if isinstance(equity_data, pd.Series):
        values = equity_data.tolist()
        timestamps = equity_data.index.tolist() if isinstance(equity_data.index, pd.DatetimeIndex) else list(range(len(values)))
    elif isinstance(equity_data, list):
        if not equity_data: print("No equity data to plot (empty list)."); return
        if isinstance(equity_data[0], dict):
            valid_entries = [entry for entry in equity_data if entry.get('timestamp') is not None]
            if not valid_entries and len(equity_data) == 1 and equity_data[0].get('timestamp') is None:
                if equity_data[0].get('value') is not None: values, timestamps = [equity_data[0]['value']], [0]
                else: print("Single initial equity value without timestamp and value."); return
            else:
                try:
                    timestamps = [pd.to_datetime(entry['timestamp']) for entry in valid_entries]
                    values = [entry['value'] for entry in valid_entries]
                except (TypeError, ValueError) as e:
                    print(f"Error parsing timestamps for equity curve: {e}. Using sequence numbers.")
                    values = [entry['value'] for entry in valid_entries]
                    timestamps = list(range(len(values)))
        elif isinstance(equity_data[0], (int, float)):
            values, timestamps = equity_data, list(range(len(equity_data)))
        else: print("Unsupported equity_data format."); return
    else: print("Unsupported equity_data type."); return
    if not values: print("No valid values to plot for equity curve."); return
    plt.figure(figsize=(12, 7)); plt.plot(timestamps, values, label='Portfolio Value', color='blue')
    plt.title(title); plt.xlabel('Time'); plt.ylabel('Portfolio Value'); plt.legend(); plt.grid(True)
    if timestamps and isinstance(timestamps[0], (pd.Timestamp, datetime)): plt.gcf().autofmt_xdate()
    filepath = os.path.join(REPORTS_DIR, os.path.basename(filename))
    try: plt.savefig(filepath); print(f"Equity curve plot saved to {filepath}")
    except Exception as e: print(f"Error saving plot to {filepath}: {e}")
    plt.close()

def plot_positions_history(trades_log, initial_cash=100000.0, data_daterange=None,
                           title="Portfolio Value and Position History",
                           filename="reports/positions_history.png"):
    _ensure_reports_dir()
    filepath = os.path.join(REPORTS_DIR, os.path.basename(filename))

    if not trades_log:
        print("No trades to plot for positions history.")
        fig, axes = plt.subplots(2, 1, sharex=True, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
        fig.suptitle(title, fontsize=16)
        if data_daterange is not None:
            axes[0].plot(data_daterange, [initial_cash] * len(data_daterange), label='Portfolio Value (Cash)', color='blue')
        else:
             axes[0].axhline(y=initial_cash, color='blue', linestyle='-', label='Portfolio Value (Cash)')
        axes[0].set_ylabel('Portfolio Value'); axes[0].legend(); axes[0].grid(True)
        axes[1].set_xlabel('Date'); axes[1].set_ylabel('Position Size'); axes[1].grid(True)
        axes[1].text(0.5, 0.5, 'No positions held.', ha='center', va='center', transform=axes[1].transAxes)
        if data_daterange is not None and isinstance(data_daterange, pd.DatetimeIndex): fig.autofmt_xdate()
        try: plt.savefig(filepath); print(f"Positions history plot (no trades) saved to {filepath}")
        except Exception as e: print(f"Error saving plot: {e}")
        plt.close(fig); return

    trades_df = pd.DataFrame(trades_log)
    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
    trades_df.sort_values(by='timestamp', inplace=True)

    if data_daterange is None:
        data_daterange = pd.date_range(start=trades_df['timestamp'].min(), end=trades_df['timestamp'].max(), freq='D')
        if data_daterange.empty: data_daterange = pd.DatetimeIndex([trades_df['timestamp'].min()])

    all_dates = sorted(list(set(data_daterange.to_list() + trades_df['timestamp'].to_list())))
    # Ensure all_dates are unique and sorted pd.Timestamps
    all_dates = pd.DatetimeIndex(sorted(list(set(all_dates))))


    cash_over_time = pd.Series(index=all_dates, dtype=float)
    portfolio_value_over_time = pd.Series(index=all_dates, dtype=float)
    symbols = trades_df['symbol'].unique()
    positions_over_time = {sym: pd.Series(index=all_dates, dtype=float) for sym in symbols}

    current_cash = initial_cash
    current_positions = {sym: 0.0 for sym in symbols}
    # For portfolio value approximation, we need last price for each symbol
    # This is a simplification; ideally, we'd have daily close prices for all held symbols.
    last_known_prices = {sym: 0.0 for sym in symbols}

    # Set initial values at the very first date
    first_date = all_dates[0]
    cash_over_time[first_date] = initial_cash
    for sym in symbols: positions_over_time[sym][first_date] = 0
    portfolio_value_over_time[first_date] = initial_cash

    trade_idx = 0
    for i, date in enumerate(all_dates):
        if i > 0: # Carry forward previous day's values first
            cash_over_time[date] = cash_over_time[all_dates[i-1]]
            for sym in symbols:
                positions_over_time[sym][date] = positions_over_time[sym][all_dates[i-1]]
                last_known_prices[sym] = last_known_prices.get(sym, 0) # Persist last known price

        while trade_idx < len(trades_df) and trades_df['timestamp'].iloc[trade_idx] == date:
            trade = trades_df.iloc[trade_idx]
            symbol, trade_type, quantity, price = trade['symbol'], trade['type'], trade['quantity'], trade['price']
            commission = trade.get('commission', 0)
            last_known_prices[symbol] = price # Update last known price on trade

            if trade_type == 'buy':
                current_cash -= (quantity * price) + commission
                current_positions[symbol] += quantity
            elif trade_type == 'sell':
                current_cash += (quantity * price) - commission
                current_positions[symbol] -= quantity

            cash_over_time[date] = current_cash
            for sym_loop in symbols: # Update all symbol positions for this specific trade date
                 positions_over_time[sym_loop][date] = current_positions[sym_loop]
            trade_idx += 1

        # Update portfolio value for the current date (after all trades on this date)
        current_market_value_of_positions = 0
        for sym in symbols:
            # If a symbol wasn't traded today, its last_known_price is from previous days.
            # This is an approximation if we don't have daily close data for non-traded symbols.
            # For symbols not in last_known_prices (e.g. new symbol in portfolio), price would be 0.
            current_market_value_of_positions += current_positions[sym] * last_known_prices.get(sym,0)
        portfolio_value_over_time[date] = cash_over_time[date] + current_market_value_of_positions

    # Forward fill values for days without trades
    cash_over_time.ffill(inplace=True)
    portfolio_value_over_time.ffill(inplace=True)
    for sym in symbols: positions_over_time[sym].ffill(inplace=True)

    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
    fig.suptitle(title, fontsize=16)
    axes[0].plot(portfolio_value_over_time.index, portfolio_value_over_time.values, label='Portfolio Value (Approx.)', color='blue')
    axes[0].plot(cash_over_time.index, cash_over_time.values, label='Cash', color='green', linestyle='--')
    axes[0].set_ylabel('Value ($)'); axes[0].legend(); axes[0].grid(True)
    for sym in symbols:
        axes[1].plot(positions_over_time[sym].index, positions_over_time[sym].values, label=f'{sym} Quantity')
    axes[1].set_xlabel('Date'); axes[1].set_ylabel('Position Size'); axes[1].legend(); axes[1].grid(True)
    if isinstance(all_dates, pd.DatetimeIndex): fig.autofmt_xdate()
    try: plt.savefig(filepath); print(f"Positions history plot saved to {filepath}")
    except Exception as e: print(f"Error saving plot: {e}")
    plt.close(fig)

def calculate_trade_statistics(trades_log, initial_cash, final_portfolio_value):
    _ensure_reports_dir()
    stats = {"initial_cash": initial_cash, "final_portfolio_value": final_portfolio_value}
    stats["total_net_profit"] = final_portfolio_value - initial_cash

    if not trades_log:
        stats["total_transactions"] = 0
        stats["buy_transactions"] = 0
        stats["sell_transactions"] = 0
        stats["total_traded_volume_value"] = 0.0
        stats["notes"] = "No trades to analyze."
        return stats

    trades_df = pd.DataFrame(trades_log)
    stats["total_transactions"] = len(trades_df)
    stats["buy_transactions"] = len(trades_df[trades_df['type'] == 'buy'])
    stats["sell_transactions"] = len(trades_df[trades_df['type'] == 'sell'])

    # Calculate total traded volume (sum of value of each transaction)
    # 'value' in trades_log is quantity * price
    stats["total_traded_volume_value"] = trades_df['value'].sum() if 'value' in trades_df else \
                                       (trades_df['quantity'] * trades_df['price']).sum()


    # More advanced stats like win rate, profit factor require pairing buys and sells
    # or PnL per trade, which is not directly available from current basic log.
    # For now, these are placeholders.
    stats["winning_trades"] = "N/A (requires round-trip analysis)"
    stats["losing_trades"] = "N/A (requires round-trip analysis)"
    stats["win_rate"] = "N/A (requires round-trip analysis)"
    stats["profit_factor"] = "N/A (requires round-trip analysis)"
    stats["average_win"] = "N/A (requires round-trip analysis)"
    stats["average_loss"] = "N/A (requires round-trip analysis)"
    stats["notes"] = "Basic transaction stats. Round-trip trade analysis not yet implemented."

    return stats

def generate_text_report(statistics, filename="reports/statistics_report.txt"):
    _ensure_reports_dir()
    filepath = os.path.join(REPORTS_DIR, os.path.basename(filename))
    try:
        with open(filepath, 'w') as f:
            f.write("--- Trade Statistics Report ---\n")
            for key, value in statistics.items():
                if isinstance(value, float):
                    f.write(f"{key.replace('_', ' ').title()}: {value:.2f}\n")
                else:
                    f.write(f"{key.replace('_', ' ').title()}: {value}\n")
        print(f"Statistics report saved to {filepath}")
    except Exception as e:
        print(f"Error saving statistics report to {filepath}: {e}")


if __name__ == '__main__':
    print("--- Reporting Module Demonstration ---")
    _ensure_reports_dir()
    equity_values_dicts = [{'timestamp': pd.Timestamp('2023-01-01'),'value': 100000}, {'timestamp': pd.Timestamp('2023-01-02'),'value': 100500}]
    plot_equity_curve(equity_values_dicts, title="Demo Equity Curve", filename="reports/demo_equity_main.png")

    dummy_trades = [
        {'timestamp': pd.Timestamp('2023-01-02').isoformat(), 'symbol': 'AAPL', 'type': 'buy', 'quantity': 10, 'price': 150.0, 'value': 1500.0, 'commission': 1.5},
        {'timestamp': pd.Timestamp('2023-01-03').isoformat(), 'symbol': 'AAPL', 'type': 'sell', 'quantity': 10, 'price': 155.0, 'value': 1550.0, 'commission': 1.55},
    ]
    date_idx = pd.date_range(start='2023-01-01', end='2023-01-05', freq='B')
    plot_positions_history(dummy_trades, initial_cash=10000, data_daterange=date_idx, filename="reports/demo_positions_main.png")

    stats = calculate_trade_statistics(dummy_trades, 10000, 10000 + (1550.0 - 1.55) - (1500.0 + 1.5))
    generate_text_report(stats, filename="reports/demo_stats_report.txt")
    print("\n--- Reporting Module Demonstration Finished ---")
