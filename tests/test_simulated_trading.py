import unittest
import pandas as pd
import numpy as np
from datetime import datetime
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from simulated_trading import SimulatedAccount, run_simulation
# Import the module itself to access module-level constants like STRATEGIES_DIR
import strategy_configurator
from strategy_configurator import generate_strategy_function, STRATEGY_TEMPLATES, STRATEGY_STUB_FUNCTIONS
from strategy_configurator import save_strategy_config, load_strategy_config # To create/load dummy config

# Define a directory for test-specific temporary strategy files if needed by this test module
TEST_TEMP_STRATEGIES_DIR_SIM = os.path.join(os.path.dirname(__file__), "temp_test_strategies_sim")


class TestSimulatedAccount(unittest.TestCase):
    def setUp(self):
        self.initial_cash = 100000.0
        self.account = SimulatedAccount(initial_cash=self.initial_cash)
        self.symbol = 'AAPL'
        self.price = 150.0
        self.quantity = 10
        self.commission_rate = 0.001 # 0.1%

    def test_01_initialization(self):
        self.assertEqual(self.account.initial_cash, self.initial_cash)
        self.assertEqual(self.account.cash, self.initial_cash)
        self.assertEqual(self.account.positions, {})
        self.assertEqual(self.account.trades_history, [])
        self.assertEqual(len(self.account.portfolio_value_history), 1)
        self.assertEqual(self.account.portfolio_value_history[0]['value'], self.initial_cash)
        self.assertIsNone(self.account.portfolio_value_history[0]['timestamp']) # Initial state

    def test_02_execute_buy_trade_sufficient_funds(self):
        timestamp = pd.Timestamp('2023-01-01')
        trade_value = self.quantity * self.price
        commission = trade_value * self.commission_rate

        success = self.account.execute_trade(timestamp, self.symbol, 'buy', self.quantity, self.price, self.commission_rate)

        self.assertTrue(success)
        self.assertEqual(self.account.cash, self.initial_cash - trade_value - commission)
        self.assertEqual(self.account.get_position_size(self.symbol), self.quantity)
        self.assertEqual(self.account.positions[self.symbol]['avg_price'], self.price)
        self.assertEqual(len(self.account.trades_history), 1)
        trade_record = self.account.trades_history[0]
        self.assertEqual(trade_record['symbol'], self.symbol)
        self.assertEqual(trade_record['type'], 'buy')
        self.assertEqual(trade_record['quantity'], self.quantity)
        self.assertEqual(trade_record['price'], self.price)
        self.assertAlmostEqual(trade_record['commission'], commission)

    def test_03_execute_buy_trade_insufficient_funds(self):
        timestamp = pd.Timestamp('2023-01-01')
        success = self.account.execute_trade(timestamp, self.symbol, 'buy', self.quantity, self.price * 2000, self.commission_rate) # Price way too high
        self.assertFalse(success)
        self.assertEqual(self.account.cash, self.initial_cash) # Cash should not change
        self.assertEqual(self.account.get_position_size(self.symbol), 0)
        self.assertEqual(len(self.account.trades_history), 0)

    def test_04_execute_sell_trade_sufficient_shares(self):
        timestamp1 = pd.Timestamp('2023-01-01')
        self.account.execute_trade(timestamp1, self.symbol, 'buy', self.quantity, self.price, self.commission_rate) # Initial buy

        timestamp2 = pd.Timestamp('2023-01-02')
        sell_quantity = 5
        sell_price = 160.0
        trade_value = sell_quantity * sell_price
        commission = trade_value * self.commission_rate

        cash_before_sell = self.account.cash
        success = self.account.execute_trade(timestamp2, self.symbol, 'sell', sell_quantity, sell_price, self.commission_rate)

        self.assertTrue(success)
        self.assertEqual(self.account.cash, cash_before_sell + trade_value - commission)
        self.assertEqual(self.account.get_position_size(self.symbol), self.quantity - sell_quantity)
        self.assertEqual(self.account.positions[self.symbol]['avg_price'], self.price) # Avg price unchanged on partial sell
        self.assertEqual(len(self.account.trades_history), 2) # Buy + Sell
        trade_record = self.account.trades_history[1]
        self.assertEqual(trade_record['type'], 'sell')
        self.assertEqual(trade_record['quantity'], sell_quantity)

    def test_05_execute_sell_trade_full_position(self):
        timestamp1 = pd.Timestamp('2023-01-01')
        self.account.execute_trade(timestamp1, self.symbol, 'buy', self.quantity, self.price, self.commission_rate)

        timestamp2 = pd.Timestamp('2023-01-02')
        sell_price = 160.0
        success = self.account.execute_trade(timestamp2, self.symbol, 'sell', self.quantity, sell_price, self.commission_rate)

        self.assertTrue(success)
        self.assertEqual(self.account.get_position_size(self.symbol), 0) # Position should be gone
        self.assertNotIn(self.symbol, self.account.positions)

    def test_06_execute_sell_trade_insufficient_shares(self):
        timestamp = pd.Timestamp('2023-01-01')
        success = self.account.execute_trade(timestamp, self.symbol, 'sell', self.quantity, self.price, self.commission_rate)
        self.assertFalse(success)
        self.assertEqual(self.account.cash, self.initial_cash)
        self.assertEqual(len(self.account.trades_history), 0)

    def test_07_update_portfolio_value_no_positions(self):
        timestamp = pd.Timestamp('2023-01-01')
        current_prices = {self.symbol: 155.0}
        pv = self.account.update_portfolio_value(timestamp, current_prices)
        self.assertEqual(pv, self.account.cash)
        self.assertEqual(len(self.account.portfolio_value_history), 2) # Initial + this update
        self.assertEqual(self.account.portfolio_value_history[-1]['value'], self.account.cash)
        self.assertEqual(self.account.portfolio_value_history[-1]['timestamp'], timestamp)


    def test_08_update_portfolio_value_with_positions(self):
        ts_buy = pd.Timestamp('2023-01-01')
        self.account.execute_trade(ts_buy, self.symbol, 'buy', self.quantity, self.price, self.commission_rate)

        ts_update = pd.Timestamp('2023-01-02')
        current_market_price = 155.0
        current_prices = {self.symbol: current_market_price}

        expected_position_value = self.quantity * current_market_price
        expected_pv = self.account.cash + expected_position_value

        pv = self.account.update_portfolio_value(ts_update, current_prices)
        self.assertAlmostEqual(pv, expected_pv)
        # Initial entry + 1 from this update. execute_trade does not add to portfolio_value_history.
        self.assertEqual(len(self.account.portfolio_value_history), 2)
        self.assertAlmostEqual(self.account.portfolio_value_history[-1]['value'], expected_pv)

    def test_09_get_position_size(self):
        self.assertEqual(self.account.get_position_size(self.symbol), 0)
        ts_buy = pd.Timestamp('2023-01-01')
        self.account.execute_trade(ts_buy, self.symbol, 'buy', self.quantity, self.price, self.commission_rate)
        self.assertEqual(self.account.get_position_size(self.symbol), self.quantity)
        self.assertEqual(self.account.get_position_size("UNKNOWN_SYMBOL"), 0)

    def test_10_get_snapshot(self):
        ts_buy = pd.Timestamp('2023-01-01')
        self.account.execute_trade(ts_buy, self.symbol, 'buy', self.quantity, self.price, self.commission_rate)

        ts_snapshot = pd.Timestamp('2023-01-02')
        current_market_price = 155.0
        current_prices = {self.symbol: current_market_price}

        snapshot = self.account.get_snapshot(ts_snapshot, current_prices)

        self.assertEqual(snapshot['timestamp'], ts_snapshot)
        self.assertEqual(snapshot['cash'], self.account.cash)
        self.assertEqual(snapshot['positions'][self.symbol]['size'], self.quantity)
        expected_pv = self.account.cash + (self.quantity * current_market_price)
        self.assertAlmostEqual(snapshot['portfolio_value'], expected_pv)


class TestRunSimulation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Ensure temp strategies dir for dummy config
        if not os.path.exists(TEST_TEMP_STRATEGIES_DIR_SIM):
            os.makedirs(TEST_TEMP_STRATEGIES_DIR_SIM)

        cls.original_strategies_dir = strategy_configurator.STRATEGIES_DIR
        strategy_configurator.STRATEGIES_DIR = TEST_TEMP_STRATEGIES_DIR_SIM

        # Create a dummy RSI config for the simple stub, as run_simulation needs it
        cls.rsi_stub_config_data = {
            "strategy_name": "rsi_strategy", # This will map to run_rsi_strategy_stub
            "stub_function_name": "run_rsi_strategy_stub", # Explicitly for clarity
            "params": {"rsi_period": 3, "overbought_threshold": 70.0, "oversold_threshold": 30.0},
            "description": "Test RSI stub config for simulation."
        }
        save_strategy_config(cls.rsi_stub_config_data, "test_sim_rsi_stub_config.json")


    @classmethod
    def tearDownClass(cls):
        strategy_configurator.STRATEGIES_DIR = cls.original_strategies_dir
        if os.path.exists(TEST_TEMP_STRATEGIES_DIR_SIM):
            for item in os.listdir(TEST_TEMP_STRATEGIES_DIR_SIM):
                os.remove(os.path.join(TEST_TEMP_STRATEGIES_DIR_SIM, item))
            os.rmdir(TEST_TEMP_STRATEGIES_DIR_SIM)

    def test_01_run_simulation_basic_flow(self):
        """Test basic workflow of run_simulation with a simple strategy stub."""
        # Create dummy data
        num_days = 20
        data = {
            'Open': np.arange(100, 100 + num_days) + np.random.rand(num_days) * 2 - 1,
            'High': np.arange(101, 101 + num_days) + np.random.rand(num_days) * 2 - 1,
            'Low': np.arange(99, 99 + num_days) + np.random.rand(num_days) * 2 - 1,
            'Close': np.arange(100, 100 + num_days) + np.random.rand(num_days) * 2 - 1, # Price generally increasing
            'Volume': np.random.randint(1000, 2000, size=num_days)
        }
        index = pd.date_range(start='2023-01-01', periods=num_days)
        data_df = pd.DataFrame(data, index=index)
        data_df.index.name = 'Timestamp' # Preprocess_data output format

        # Load the dummy RSI stub config
        config = load_strategy_config("test_sim_rsi_stub_config.json")
        self.assertIsNotNone(config)

        strategy_func = generate_strategy_function(config) # Gets the simple stub partial
        self.assertTrue(callable(strategy_func))

        account = SimulatedAccount(initial_cash=10000.0)
        symbol_name = 'DUMMY_STOCK'

        # The run_rsi_strategy_stub has mock logic that might not always trade.
        # For this test, we primarily want to see it run without error and interact.
        # The stub's logic: buy if len(data) % (period+7) < period/2, sell if > period
        # With period=3: len(data) % 10 < 1.5 (buy), len(data) % 10 > 3 (sell)
        # This means it will buy on day 1 (len=1), day 11 (len=11)
        # It will sell on days 4,5,6,7,8,9,10 (len=4 to 10) etc.

        final_account = run_simulation(data_df, symbol_name, strategy_func, account, fixed_trade_quantity=1)

        self.assertIsInstance(final_account, SimulatedAccount)
        # Check if portfolio history was updated beyond initial state
        self.assertTrue(len(final_account.portfolio_value_history) > 1)
        # Check if some trades were made (highly likely with the stub's logic)
        self.assertTrue(len(final_account.trades_history) > 0,
                        "Expected some trades based on simple RSI stub logic, but none were made.")

        # Check if the last portfolio update corresponds to the last data timestamp
        if not data_df.empty:
             self.assertEqual(final_account.portfolio_value_history[-1]['timestamp'], data_df.index[-1])


if __name__ == '__main__':
    unittest.main()
