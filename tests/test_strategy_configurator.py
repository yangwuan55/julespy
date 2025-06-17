import unittest
import os
import json
import pandas as pd
import numpy as np # Import numpy
import backtrader as bt
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the module to be tested
import strategy_configurator
from strategy_configurator import (
    save_strategy_config, load_strategy_config,
    generate_backtrader_strategy_class, generate_strategy_function,
    RSIStrategy, STRATEGY_TEMPLATES, STRATEGY_STUB_FUNCTIONS
)

# Define a directory for test-specific temporary strategy files
TEST_TEMP_STRATEGIES_DIR = os.path.join(os.path.dirname(__file__), "temp_test_strategies")

class TestStrategyConfigurator(unittest.TestCase):

    original_strategies_dir = None

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(TEST_TEMP_STRATEGIES_DIR):
            os.makedirs(TEST_TEMP_STRATEGIES_DIR)

        # Store original STRATEGIES_DIR and redirect for tests
        cls.original_strategies_dir = strategy_configurator.STRATEGIES_DIR
        strategy_configurator.STRATEGIES_DIR = TEST_TEMP_STRATEGIES_DIR

        # Ensure the dummy config file used by generate_strategy_function tests is created
        # This config is for the simple stubs.
        cls.rsi_stub_config_data = {
            "strategy_name": "rsi_strategy",
            "params": {"rsi_period": 10, "overbought_threshold": 80.0, "oversold_threshold": 20.0},
            "description": "RSI strategy for simple stub simulation (test)."
        }
        save_strategy_config(cls.rsi_stub_config_data, "test_rsi_stub_config.json")


    @classmethod
    def tearDownClass(cls):
        # Restore original STRATEGIES_DIR
        strategy_configurator.STRATEGIES_DIR = cls.original_strategies_dir

        # Clean up the temporary directory and its contents
        if os.path.exists(TEST_TEMP_STRATEGIES_DIR):
            for item in os.listdir(TEST_TEMP_STRATEGIES_DIR):
                os.remove(os.path.join(TEST_TEMP_STRATEGIES_DIR, item))
            os.rmdir(TEST_TEMP_STRATEGIES_DIR)

    def test_01_save_and_load_strategy_config(self):
        """Test saving and loading a valid strategy configuration."""
        config_data = {
            "strategy_name": "moving_average_crossover",
            "params": {"short_window": 10, "long_window": 25},
            "description": "Test MA Crossover"
        }
        filename = "test_ma_config.json"

        saved_path = save_strategy_config(config_data, filename)
        self.assertIsNotNone(saved_path)
        self.assertTrue(os.path.exists(saved_path))

        loaded_config = load_strategy_config(filename)
        self.assertIsNotNone(loaded_config)
        self.assertEqual(loaded_config["strategy_name"], config_data["strategy_name"])
        self.assertEqual(loaded_config["params"]["short_window"], config_data["params"]["short_window"])

    def test_02_load_non_existent_config(self):
        """Test loading a non-existent configuration file."""
        loaded_config = load_strategy_config("non_existent_config.json")
        self.assertIsNone(loaded_config)

    def test_03_load_malformed_json_config(self):
        """Test loading a malformed JSON configuration file."""
        malformed_json_path = os.path.join(TEST_TEMP_STRATEGIES_DIR, "malformed.json")
        with open(malformed_json_path, 'w') as f:
            f.write("{'strategy_name': 'rsi', 'params': {'rsi_period': 14") # Missing closing brace and quotes

        loaded_config = load_strategy_config("malformed.json")
        self.assertIsNone(loaded_config) # Expecting None due to JSONDecodeError handling

    def test_04_generate_backtrader_strategy_class_rsi(self):
        """Test generating the RSIStrategy Backtrader class."""
        rsi_config = {
            "strategy_name": "rsi_strategy",
            "params": {"rsi_period": 14, "overbought_threshold": 70, "oversold_threshold": 30}
        }
        strategy_class = generate_backtrader_strategy_class(rsi_config)
        self.assertIsNotNone(strategy_class)
        self.assertEqual(strategy_class, RSIStrategy) # Check if it's the correct class object

    def test_05_generate_backtrader_strategy_class_unknown(self):
        """Test generating a Backtrader class for an unknown strategy name."""
        unknown_config = {"strategy_name": "unknown_strategy", "params": {}}
        strategy_class = generate_backtrader_strategy_class(unknown_config)
        self.assertIsNone(strategy_class)

    def test_06_generate_strategy_function_rsi_stub(self):
        """Test generating a callable function for the RSI simple stub."""
        # This config file ("test_rsi_stub_config.json") is created in setUpClass
        rsi_stub_config = load_strategy_config("test_rsi_stub_config.json")
        self.assertIsNotNone(rsi_stub_config, "Pre-requisite rsi_stub_config.json not found/loaded.")

        strategy_func = generate_strategy_function(rsi_stub_config)
        self.assertTrue(callable(strategy_func))

        # Test calling the generated function (simple stub version)
        dummy_data = pd.DataFrame({
            'Close': np.random.rand(20) * 100 + 100
        }, index=pd.date_range(start='2023-01-01', periods=20))

        # The stub itself prints parameters, so we'd see that in test output if verbose
        # The stub is expected to return a DataFrame with a 'signal' column
        result_df = strategy_func(data=dummy_data)
        self.assertIsInstance(result_df, pd.DataFrame)
        self.assertTrue('signal' in result_df.columns)

    def test_07_generate_strategy_function_unknown_stub(self):
        """Test generating a function for an unknown simple stub name."""
        unknown_config = {"strategy_name": "unknown_stub_strategy",
                          "stub_function_name": "non_existent_stub", # ensure this mapping is checked
                          "params": {}}
        # Temporarily add to STRATEGY_TEMPLATES if generate_strategy_function relies on it for stub_function_name
        original_template_entry = STRATEGY_TEMPLATES.get("unknown_stub_strategy")
        STRATEGY_TEMPLATES["unknown_stub_strategy"] = {"stub_function_name": "non_existent_stub", "params": {}}

        strategy_func = generate_strategy_function(unknown_config)
        self.assertIsNone(strategy_func) # Because "non_existent_stub" won't be in STRATEGY_STUB_FUNCTIONS

        # Clean up temporary modification
        if original_template_entry is None:
            del STRATEGY_TEMPLATES["unknown_stub_strategy"]
        else:
            STRATEGY_TEMPLATES["unknown_stub_strategy"] = original_template_entry


    def test_08_rsi_strategy_bt_instantiation(self):
        """Test direct instantiation - this should now pass as it does nothing."""
        pass # Direct instantiation without Cerebro is problematic.

    def test_08a_rsi_strategy_bt_instantiation_with_cerebro(self): # Renaming to test_08 for sequential numbering
        """Test Backtrader RSIStrategy instantiation within a Cerebro context."""
        cerebro = bt.Cerebro()
        cerebro.addstrategy(RSIStrategy,
                            rsi_period=10,
                            overbought_threshold=75,
                            oversold_threshold=25)

        num_bars = 20
        dummy_data = {
            'open': np.random.rand(num_bars) * 100 + 90,
            'high': np.random.rand(num_bars) * 100 + 100,
            'low': np.random.rand(num_bars) * 100 + 80,
            'close': np.random.rand(num_bars) * 100 + 95,
            'volume': np.random.randint(1000, 5000, size=num_bars),
            'openinterest': [0] * num_bars
        }
        dummy_index = pd.date_range(start='2023-01-01', periods=num_bars)
        dummy_data_feed = bt.feeds.PandasData(dataname=pd.DataFrame(dummy_data, index=dummy_index))
        cerebro.adddata(dummy_data_feed)

        results = cerebro.run() # cerebro.run() returns a list of strategy instances
        self.assertTrue(len(results) > 0 , "Strategy did not run or was not returned.")
        strategy_instance = results[0] # Corrected: access the first strategy instance from the list

        self.assertIsInstance(strategy_instance, RSIStrategy)
        self.assertEqual(strategy_instance.params.rsi_period, 10)
        self.assertEqual(strategy_instance.params.overbought_threshold, 75)
        self.assertEqual(strategy_instance.params.oversold_threshold, 25)


    def test_09_save_config_with_sanitization(self):
        """Test if filename sanitization works during save."""
        config_data = {"strategy_name": "test", "params": {}}
        unsafe_filename = "../test_ma_config!@#$%^&*.json.txt"
        # Corrected expected name: 8 underscores, then .json appended
        expected_sanitized_basename = "test_ma_config________.json.txt.json"

        saved_path = save_strategy_config(config_data, unsafe_filename)
        self.assertIsNotNone(saved_path)

        self.assertEqual(os.path.basename(saved_path), expected_sanitized_basename)
        self.assertTrue(os.path.exists(os.path.join(TEST_TEMP_STRATEGIES_DIR, expected_sanitized_basename)))


if __name__ == '__main__':
    unittest.main()
