import pandas as pd
import numpy as np
from datetime import datetime
import sys
sys.path.append('/app') # Ensure other modules can be imported

from data_manager import download_data, preprocess_data
from strategy_configurator import load_strategy_config, generate_strategy_function
# Import new reporting functions
from reporting import plot_equity_curve, plot_positions_history, calculate_trade_statistics, generate_text_report

class SimulatedAccount:
    def __init__(self, initial_cash=100000.0):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions = {}
        self.trades_history = []
        self.portfolio_value_history = [{'timestamp': None, 'value': initial_cash}]
        print(f"SimulatedAccount initialized with cash: {self.cash:.2f}")

    def update_portfolio_value(self, current_timestamp, current_prices):
        market_value = 0
        for symbol, position_details in self.positions.items():
            current_price = current_prices.get(symbol, position_details['avg_price'])
            market_value += position_details['size'] * current_price
        new_portfolio_value = self.cash + market_value
        self.portfolio_value_history.append({'timestamp': current_timestamp, 'value': new_portfolio_value})
        return new_portfolio_value

    def execute_trade(self, timestamp, symbol, trade_type, quantity, price, commission_rate=0.001):
        if quantity <= 0:
            print(f"Trade execution failed: Quantity must be positive. Got {quantity}"); return False
        commission = quantity * price * commission_rate
        if trade_type == 'buy':
            required_cash = (quantity * price) + commission
            if self.cash < required_cash:
                print(f"BUY {symbol} failed: Insufficient funds. Need {required_cash:.2f}, have {self.cash:.2f}"); return False
            self.cash -= required_cash
            current_size = self.positions.get(symbol, {}).get('size', 0)
            current_value = self.positions.get(symbol, {}).get('avg_price', 0) * current_size
            new_size = current_size + quantity
            new_total_value = current_value + (quantity * price)
            new_avg_price = new_total_value / new_size if new_size > 0 else 0
            self.positions[symbol] = {'size': new_size, 'avg_price': new_avg_price}
            action_taken = "bought"
        elif trade_type == 'sell':
            current_size = self.positions.get(symbol, {}).get('size', 0)
            if quantity > current_size:
                print(f"SELL {symbol} failed: Not enough shares. Have {current_size}, need {quantity}"); return False
            self.cash += (quantity * price) - commission
            if quantity == current_size: del self.positions[symbol]
            else: self.positions[symbol]['size'] = current_size - quantity # type: ignore
            action_taken = "sold"
        else:
            print(f"Trade execution failed: Unknown trade type '{trade_type}'"); return False

        trade_record = {
            'timestamp': timestamp, 'symbol': symbol, 'type': trade_type,
            'quantity': quantity, 'price': price, 'commission': commission,
            'value': quantity * price, # Gross value of transaction before commission
            'cash_after_trade': self.cash,
            'position_size_after_trade': self.get_position_size(symbol)
        }
        self.trades_history.append(trade_record)
        print(f"Trade: {timestamp} - {action_taken} {quantity} {symbol} @ {price:.2f}, Comm: {commission:.2f}, Cash: {self.cash:.2f}")
        return True

    def get_position_size(self, symbol):
        return self.positions.get(symbol, {}).get('size', 0)

    def get_snapshot(self, current_timestamp, current_prices):
        self.update_portfolio_value(current_timestamp, current_prices)
        return {'timestamp': current_timestamp, 'cash': self.cash,
                'positions': self.positions.copy(),
                'portfolio_value': self.portfolio_value_history[-1]['value']}

def run_simulation(data_df, symbol_name, strategy_func, account, fixed_trade_quantity=10):
    if not isinstance(data_df.index, pd.DatetimeIndex):
        print("Error: data_df must have a DatetimeIndex."); return account
    if data_df.empty: print("Error: data_df is empty."); return account
    if len(account.portfolio_value_history) == 1 and account.portfolio_value_history[0]['timestamp'] is None:
        account.portfolio_value_history[0]['timestamp'] = data_df.index[0]

    for i in range(len(data_df)):
        current_timestamp, current_price = data_df.index[i], data_df['Close'].iloc[i]
        execution_price = current_price
        data_slice = data_df.iloc[0:i+1]
        strategy_output_df = strategy_func(data=data_slice)
        signal_to_act = 0
        if strategy_output_df is not None and not strategy_output_df.empty and 'signal' in strategy_output_df.columns:
            latest_signal_value = strategy_output_df['signal'].iloc[-1]
            if latest_signal_value == 1: signal_to_act = 1
            elif latest_signal_value == -1: signal_to_act = -1

        if signal_to_act == 1:
            account.execute_trade(current_timestamp, symbol_name, 'buy', fixed_trade_quantity, execution_price)
        elif signal_to_act == -1:
            account.execute_trade(current_timestamp, symbol_name, 'sell', fixed_trade_quantity, execution_price)
        account.update_portfolio_value(current_timestamp, {symbol_name: current_price})
    print("Simulation finished.")
    return account

if __name__ == '__main__':
    print("--- Simulated Trading Demonstration with Plotting & Stats ---")
    sim_account = SimulatedAccount(initial_cash=100000.0)
    print("\nLoading data for MSFT...")
    raw_data = download_data(symbol='MSFT', start_date='2022-01-01', end_date='2022-06-01', source='yahoo')
    if raw_data is None or raw_data.empty:
        print("Failed to download MSFT data. Using dummy data for demo.")
        idx = pd.date_range(start='2022-01-01', end='2022-06-01', freq='B')
        raw_data = pd.DataFrame({
            ('Price', 'Open'): [150 + i/10 + np.sin(i/5.0)*5 for i in range(len(idx))],
            ('Price', 'High'): [152 + i/10 + np.sin(i/5.0)*5 for i in range(len(idx))],
            ('Price', 'Low'): [148 + i/10 + np.sin(i/5.0)*5 for i in range(len(idx))],
            ('Price', 'Close'): [150 + i/5 + np.sin(i/5.0)*5 for i in range(len(idx))],
            ('Price', 'Volume'): [1000000 + i*1000 for i in range(len(idx))]
        }, index=idx); raw_data.index.name = 'Date'
    preprocessed_data = preprocess_data(raw_data)
    if preprocessed_data is None or preprocessed_data.empty: print("Data preprocessing failed."); exit()
    print(f"Data loaded. Shape: {preprocessed_data.shape}")

    print("\nLoading RSI strategy configuration...")
    rsi_config = load_strategy_config("test_rsi_config_functional.json")
    if rsi_config is None: print("Failed to load 'test_rsi_config_functional.json'."); exit()
    rsi_strategy_function_partial = generate_strategy_function(rsi_config)
    if rsi_strategy_function_partial is None: print("Failed to generate RSI strategy function (stub)."); exit()
    print("RSI strategy function (stub) generated.")

    print("\nRunning simulation...")
    symbol_to_trade = 'MSFT'
    sim_account = run_simulation(
        data_df=preprocessed_data, symbol_name=symbol_to_trade,
        strategy_func=rsi_strategy_function_partial, account=sim_account, fixed_trade_quantity=5)

    print("\n--- Simulation Results ---")
    final_ts = preprocessed_data.index[-1] if not preprocessed_data.empty else datetime.now()
    current_close = preprocessed_data['Close'].iloc[-1] if not preprocessed_data.empty else 0
    final_snapshot = sim_account.get_snapshot(final_ts, {symbol_to_trade: current_close})
    print(f"Final Portfolio Value: {final_snapshot['portfolio_value']:.2f}")
    print(f"Final Cash: {final_snapshot['cash']:.2f}")
    print(f"Final Positions: {final_snapshot['positions']}")
    print(f"Total Trades Made: {len(sim_account.trades_history)}")

    # Calculate and generate text report for trade statistics
    trade_stats = calculate_trade_statistics(
        sim_account.trades_history,
        sim_account.initial_cash,
        final_snapshot['portfolio_value']
    )
    report_filename = "reports/simulated_trade_stats.txt"
    generate_text_report(trade_stats, filename=report_filename)
    print(f"Trade statistics report saved to {report_filename}")

    print("\nLast 5 Trades:")
    for trade in sim_account.trades_history[-5:]:
        trade_to_print = trade.copy()
        if isinstance(trade_to_print['timestamp'], pd.Timestamp):
            trade_to_print['timestamp'] = trade_to_print['timestamp'].isoformat()
        print(trade_to_print)
    print("\nLast 5 Portfolio Value Updates:")
    for pv_entry in sim_account.portfolio_value_history[-5:]:
        ts_str = pv_entry['timestamp'].isoformat() if isinstance(pv_entry['timestamp'], pd.Timestamp) else str(pv_entry['timestamp'])
        print(f"Timestamp: {ts_str}, Value: {pv_entry['value']:.2f}")

    plot_equity_curve(sim_account.portfolio_value_history,
                      title="Simulated Equity Curve", filename="reports/simulated_equity_curve.png")
    plot_positions_history(sim_account.trades_history,
                           initial_cash=sim_account.initial_cash,
                           data_daterange=preprocessed_data.index,
                           title=f"Simulated Positions for {symbol_to_trade}",
                           filename="reports/simulated_positions.png")
    print("\n--- Simulation Demonstration Finished ---")
