import json
import os
import re
import pandas as pd
import numpy as np
import backtrader as bt
import csv
from functools import partial # Added back

STRATEGIES_DIR = "strategies"
if not os.path.exists(STRATEGIES_DIR):
    os.makedirs(STRATEGIES_DIR)

# --- Simple Strategy Function Stubs (for simulation or non-Backtrader uses) ---
def run_moving_average_crossover_strategy_stub(data, short_window, long_window):
    print(f"Running Moving Average Crossover STUB with data (shape {data.shape})")
    print(f"Parameters: short_window={short_window}, long_window={long_window}")
    mock_signals = pd.DataFrame(index=data.index)
    mock_signals['signal'] = 0
    if not data.empty and len(data) > long_window:
        # Simplified: buy if short_ma > long_ma, sell if short_ma < long_ma
        # This is just a mock, actual MA calculation would be needed here for real signals
        short_ma = data['Close'].rolling(window=short_window).mean()
        long_ma = data['Close'].rolling(window=long_window).mean()
        if not short_ma.empty and not long_ma.empty:
             # Consider only the latest signal for simulation step
            if short_ma.iloc[-1] > long_ma.iloc[-1] and (len(data) > long_window +1 and short_ma.iloc[-2] < long_ma.iloc[-2]): # Crossover
                mock_signals['signal'].iloc[-1] = 1
            elif short_ma.iloc[-1] < long_ma.iloc[-1] and (len(data) > long_window +1 and short_ma.iloc[-2] > long_ma.iloc[-2]): # Crossover
                mock_signals['signal'].iloc[-1] = -1
    return mock_signals

def run_rsi_strategy_stub(data, rsi_period, overbought_threshold, oversold_threshold):
    print(f"Running RSI Strategy STUB with data (shape {data.shape})")
    print(f"Parameters: rsi_period={rsi_period}, overbought_threshold={overbought_threshold}, oversold_threshold={oversold_threshold}")
    mock_signals = pd.DataFrame(index=data.index)
    mock_signals['signal'] = 0
    if not data.empty and len(data) > rsi_period:
        # Simplified: buy if RSI < oversold, sell if RSI > overbought
        # This is just a mock, actual RSI calculation would be here
        # Example: using a simple random number to simulate RSI for stub
        # For a real stub, you'd calculate RSI on data['Close']
        # For now, let's make it generate some signals based on length to test simulation
        if len(data) % (rsi_period + 7) < rsi_period / 2 : # mock oversold
             mock_signals['signal'].iloc[-1] = 1
        elif len(data) % (rsi_period + 7) > rsi_period : # mock overbought
             mock_signals['signal'].iloc[-1] = -1
    return mock_signals

def run_grid_trading_strategy_stub(data, upper_price, lower_price, grid_levels, investment_per_grid):
    print(f"Running Grid Trading Strategy STUB with data (shape {data.shape})")
    print(f"Parameters: upper_price={upper_price}, lower_price={lower_price}, grid_levels={grid_levels}, investment_per_grid={investment_per_grid}")
    # Grid trading is more complex; this stub returns an empty signal DataFrame.
    # In reality, it would manage orders based on price levels.
    mock_signals = pd.DataFrame(index=data.index)
    mock_signals['signal'] = 0
    return mock_signals

STRATEGY_STUB_FUNCTIONS = {
    "run_moving_average_crossover_strategy_stub": run_moving_average_crossover_strategy_stub,
    "run_rsi_strategy_stub": run_rsi_strategy_stub,
    "run_grid_trading_strategy_stub": run_grid_trading_strategy_stub,
}

def generate_strategy_function(config): # This is the function for simple stubs
    if not isinstance(config, dict) or "strategy_name" not in config or "params" not in config:
        print("Error: Invalid configuration format for stub generation.")
        return None
    strategy_template_key = config["strategy_name"]
    params = config["params"]
    if strategy_template_key not in STRATEGY_TEMPLATES:
        print(f"Error: Strategy template '{strategy_template_key}' not found.")
        return None
    stub_function_name = STRATEGY_TEMPLATES[strategy_template_key].get("stub_function_name")
    if not stub_function_name or stub_function_name not in STRATEGY_STUB_FUNCTIONS:
        print(f"Error: Strategy stub function for '{strategy_template_key}' not defined or mapped.")
        return None
    strategy_function_stub = STRATEGY_STUB_FUNCTIONS[stub_function_name]
    try:
        partial_function = partial(strategy_function_stub, **params)
        return partial_function
    except Exception as e:
        print(f"Error preparing strategy stub function '{stub_function_name}': {e}")
        return None

# --- Backtrader Strategy Definitions ---
class RSIStrategy(bt.Strategy): # Backtrader specific strategy
    params = (('rsi_period', 14), ('overbought_threshold', 70), ('oversold_threshold', 30),)
    def __init__(self):
        self.rsi = bt.indicators.RSI(self.datas[0].close, period=self.params.rsi_period)
        self.order = None
        self.daily_portfolio_value = []
        self.trades_log = []
        self.equity_file_path = "temp_equity_data.csv"
        self.trades_file_path = "temp_trades_data.json"
        if os.path.exists(self.equity_file_path): os.remove(self.equity_file_path)
        if os.path.exists(self.trades_file_path): os.remove(self.trades_file_path)
    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')
    def next(self):
        self.daily_portfolio_value.append(self.broker.getvalue())
        if self.order: return
        if not self.position:
            if self.rsi[0] < self.params.oversold_threshold:
                self.log(f'BUY CREATE, RSI: {self.rsi[0]:.2f} < {self.params.oversold_threshold:.2f}')
                self.order = self.buy()
        else:
            if self.rsi[0] > self.params.overbought_threshold:
                self.log(f'SELL CREATE, RSI: {self.rsi[0]:.2f} > {self.params.overbought_threshold:.2f}')
                self.order = self.sell()
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]: return
        if order.status in [order.Completed]:
            trade_info = {'timestamp': self.datas[0].datetime.date(0).isoformat(), 'type': 'buy' if order.isbuy() else 'sell', 'price': order.executed.price, 'size': order.executed.size, 'value': order.executed.value, 'commission': order.executed.comm}
            self.trades_log.append(trade_info)
            if order.isbuy(): self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Value: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            elif order.issell(): self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Value: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: {order.getstatusname()}')
        self.order = None
    def stop(self):
        self.log('Ending Period Portfolio Value: %.2f' % self.broker.getvalue())
        try:
            with open(self.equity_file_path, 'w', newline='') as f:
                writer = csv.writer(f); writer.writerows([[val] for val in self.daily_portfolio_value]) # Corrected to writerows
            print(f"Equity curve data saved to {self.equity_file_path}")
        except Exception as e: print(f"Error saving equity curve data: {e}")
        try:
            with open(self.trades_file_path, 'w') as f: json.dump(self.trades_log, f, indent=4)
            print(f"Trades log data saved to {self.trades_file_path}")
        except Exception as e: print(f"Error saving trades log data: {e}")

STRATEGY_TEMPLATES = {
    "moving_average_crossover": {
        "display_name": "Moving Average Crossover",
        "params": {"short_window": {"type": int, "prompt": "..."}, "long_window": {"type": int, "prompt": "..."}},
        "stub_function_name": "run_moving_average_crossover_strategy_stub", # For simple sim
        "backtrader_strategy_class": None
    },
    "rsi_strategy": {
        "display_name": "RSI Strategy",
        "params": {"rsi_period": {"type": int, "prompt": "..."}, "overbought_threshold": {"type": float, "prompt": "..."}, "oversold_threshold": {"type": float, "prompt": "..."}},
        "stub_function_name": "run_rsi_strategy_stub", # For simple sim
        "backtrader_strategy_class": RSIStrategy
    },
    "grid_trading": {
        "display_name": "Grid Trading",
        "params": {"upper_price": {"type": float, "prompt": "..."}, "lower_price": {"type": float, "prompt": "..."}, "grid_levels": {"type": int, "prompt": "..."}, "investment_per_grid": {"type": float, "prompt": "..."}},
        "stub_function_name": "run_grid_trading_strategy_stub", # For simple sim
        "backtrader_strategy_class": None
    }
}
# Prompts in STRATEGY_TEMPLATES params were shortened for diff brevity

def generate_backtrader_strategy_class(config): # This is for Backtrader classes
    if not isinstance(config, dict) or "strategy_name" not in config:
        print("Error: Invalid configuration format or missing 'strategy_name'.")
        return None
    strategy_template_key = config["strategy_name"]
    if strategy_template_key not in STRATEGY_TEMPLATES:
        print(f"Error: Strategy template '{strategy_template_key}' not found.")
        return None
    strategy_class = STRATEGY_TEMPLATES[strategy_template_key].get("backtrader_strategy_class")
    if strategy_class is None:
        print(f"Warning: Backtrader strategy class not yet defined for '{strategy_template_key}'.")
        return None
    return strategy_class

# ... (rest of the file: _sanitize_filename, save_strategy_config, load_strategy_config, create_strategy_cli)
# ... (The __main__ block needs to be adjusted to potentially save a config for simple stubs if needed by simulated_trading.py)

def _sanitize_filename(filename):
    filename = os.path.basename(filename)
    filename = re.sub(r'[^\w\-\.]', '_', filename)
    if not filename.endswith(".json"):
        filename += ".json"
    return filename

def save_strategy_config(config, filename):
    if not isinstance(config, dict):
        print("Error: Configuration must be a dictionary.")
        return None
    safe_filename = _sanitize_filename(filename)
    filepath = os.path.join(STRATEGIES_DIR, safe_filename)
    try:
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=4)
        print(f"Strategy configuration saved to {filepath}")
        return filepath
    except Exception as e:
        print(f"Error saving strategy: {e}")
        return None

def load_strategy_config(filename):
    base_filename = os.path.basename(filename)
    if not base_filename.endswith(".json"):
        base_filename += ".json"
    filepath = os.path.join(STRATEGIES_DIR, base_filename)
    if not os.path.exists(filepath):
        print(f"Error: Strategy file not found at {filepath}")
        return None
    try:
        with open(filepath, 'r') as f:
            config = json.load(f)
        print(f"Strategy configuration loaded from {filepath}")
        return config
    except Exception as e:
        print(f"Error loading strategy: {e}")
        return None

def create_strategy_cli():
    # This function's content is assumed to be correct from previous steps.
    # For brevity, actual CLI interaction logic is not repeated in this diff.
    print("Available Strategy Templates:")
    templates_list = list(STRATEGY_TEMPLATES.keys())
    for i, template_key in enumerate(templates_list):
        # Accessing 'display_name' which should exist.
        print(f"{i + 1}. {STRATEGY_TEMPLATES[template_key]['display_name']}")

    try:
        choice_str = input("Select a strategy template by number: ")
        if not choice_str.isdigit():
            print("Invalid input. Please enter a number. Exiting.")
            return
        choice = int(choice_str) - 1
        if not 0 <= choice < len(templates_list):
            print("Invalid choice. Exiting.")
            return
    except ValueError: # Should be caught by isdigit or int conversion
        print("Invalid input. Please enter a number. Exiting.")
        return

    selected_template_key = templates_list[choice]
    selected_template = STRATEGY_TEMPLATES[selected_template_key]
    print(f"\nCreating '{selected_template['display_name']}' strategy...")

    strategy_config = {"strategy_name": selected_template_key, "params": {}}

    for param_name, param_details in selected_template["params"].items():
        while True:
            try:
                # Using param_details['prompt'] which should exist.
                user_input_str = input(f"{param_details['prompt']} ")
                param_type = param_details.get("type", str) # Default to string if type not specified

                if param_type == int: value = int(user_input_str)
                elif param_type == float: value = float(user_input_str)
                else: value = user_input_str # Default to string

                strategy_config["params"][param_name] = value
                break
            except ValueError:
                print(f"Invalid input type. Expected {param_type.__name__ if hasattr(param_type, '__name__') else 'string'}. Please try again.")
            except Exception as e:
                print(f"An unexpected error occurred: {e}. Please try again.")

    if selected_template_key == "moving_average_crossover":
        if strategy_config["params"].get("short_window", 0) >= strategy_config["params"].get("long_window", 1):
            print("Warning: Short window should typically be less than long window for MA Crossover.")

    while True:
        config_filename_base = input("Enter a filename for this strategy configuration (e.g., my_ma_strategy): ")
        if not config_filename_base.strip():
            print("Filename cannot be empty. Please try again.")
            continue
        break

    save_strategy_config(strategy_config, config_filename_base + ".json")


if __name__ == '__main__':
    print("--- Strategy Configurator ---")
    # Save config for Backtrader (used by backtesting_engine.py)
    rsi_bt_config_data = {
        "strategy_name": "rsi_strategy",
        "params": {"rsi_period": 14, "overbought_threshold": 70.0, "oversold_threshold": 30.0},
        "description": "RSI strategy for Backtrader."
    }
    save_strategy_config(rsi_bt_config_data, "test_rsi_backtrader.json")

    # Save config for simple stubs (potentially used by simulated_trading.py)
    rsi_stub_config_data = {
        "strategy_name": "rsi_strategy", # This will map to run_rsi_strategy_stub via STRATEGY_TEMPLATES
        "params": {
            "rsi_period": 10, # Different params for stub example
            "overbought_threshold": 80.0,
            "oversold_threshold": 20.0
        },
        "description": "RSI strategy for simple stub simulation."
    }
    # This is the file simulated_trading.py expects
    save_strategy_config(rsi_stub_config_data, "test_rsi_config_functional.json")

    print("\nConfigs for Backtrader (test_rsi_backtrader.json) and simple stubs (test_rsi_config_functional.json) have been saved/updated.")
    print("Skipping interactive CLI in this automated demonstration.")
