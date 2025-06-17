import unittest
import os
import pandas as pd
import json
import sys
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import reporting # The module to test
from reporting import (
    calculate_trade_statistics, generate_text_report,
    plot_equity_curve, plot_positions_history
)

# Define a directory for test-specific temporary report files
TEST_TEMP_REPORTS_DIR = os.path.join(os.path.dirname(__file__), "temp_test_reports")

class TestReporting(unittest.TestCase):

    original_reports_dir = None

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(TEST_TEMP_REPORTS_DIR):
            os.makedirs(TEST_TEMP_REPORTS_DIR)

        # Store original REPORTS_DIR and redirect for tests
        cls.original_reports_dir = reporting.REPORTS_DIR
        reporting.REPORTS_DIR = TEST_TEMP_REPORTS_DIR

    @classmethod
    def tearDownClass(cls):
        # Restore original REPORTS_DIR
        reporting.REPORTS_DIR = cls.original_reports_dir

        # Clean up the temporary directory and its contents
        if os.path.exists(TEST_TEMP_REPORTS_DIR):
            for item in os.listdir(TEST_TEMP_REPORTS_DIR):
                try:
                    os.remove(os.path.join(TEST_TEMP_REPORTS_DIR, item))
                except Exception as e:
                    print(f"Error removing test file {item}: {e}")
            try:
                os.rmdir(TEST_TEMP_REPORTS_DIR)
            except Exception as e:
                print(f"Error removing test directory {TEST_TEMP_REPORTS_DIR}: {e}")


    def test_01_calculate_trade_statistics_no_trades(self):
        stats = calculate_trade_statistics([], 100000.0, 100000.0)
        self.assertEqual(stats["total_net_profit"], 0)
        self.assertEqual(stats["total_transactions"], 0)
        self.assertEqual(stats["buy_transactions"], 0)
        self.assertEqual(stats["sell_transactions"], 0)
        self.assertEqual(stats["total_traded_volume_value"], 0.0)

    def test_02_calculate_trade_statistics_with_trades(self):
        trades = [
            {'type': 'buy', 'quantity': 10, 'price': 100, 'value': 1000}, # Value is quantity * price
            {'type': 'sell', 'quantity': 10, 'price': 110, 'value': 1100},
            {'type': 'buy', 'quantity': 5, 'price': 90, 'value': 450},
        ]
        stats = calculate_trade_statistics(trades, 10000.0, 10050.0) # Net profit = 50
        self.assertEqual(stats["total_net_profit"], 50.0)
        self.assertEqual(stats["total_transactions"], 3)
        self.assertEqual(stats["buy_transactions"], 2)
        self.assertEqual(stats["sell_transactions"], 1)
        self.assertEqual(stats["total_traded_volume_value"], 1000 + 1100 + 450)

    def test_03_generate_text_report(self):
        stats = {
            "total_net_profit": 50.0, "total_transactions": 3,
            "buy_transactions": 2, "sell_transactions": 1,
            "total_traded_volume_value": 2550.0,
            "notes": "Test run."
        }
        filename = "test_stats_report.txt"
        generate_text_report(stats, filename=filename) # filename is basename, will be put in TEST_TEMP_REPORTS_DIR

        expected_path = os.path.join(TEST_TEMP_REPORTS_DIR, filename)
        self.assertTrue(os.path.exists(expected_path))

        with open(expected_path, 'r') as f:
            content = f.read()
            self.assertIn("Total Net Profit: 50.00", content)
            self.assertIn("Total Transactions: 3", content)
            self.assertIn("Notes: Test run.", content)

    def test_04_plot_equity_curve_list_of_values(self):
        equity_values = [100000.0, 100100.0, 100050.0, 100200.0]
        filename = "test_equity_curve_values.png"
        plot_equity_curve(equity_values, filename=filename)
        expected_path = os.path.join(TEST_TEMP_REPORTS_DIR, filename)
        self.assertTrue(os.path.exists(expected_path))

    def test_05_plot_equity_curve_list_of_dicts(self):
        equity_data = [
            {'timestamp': pd.Timestamp('2023-01-01'), 'value': 100000},
            {'timestamp': pd.Timestamp('2023-01-02'), 'value': 100500},
        ]
        filename = "test_equity_curve_dicts.png"
        plot_equity_curve(equity_data, filename=filename)
        expected_path = os.path.join(TEST_TEMP_REPORTS_DIR, filename)
        self.assertTrue(os.path.exists(expected_path))

    def test_06_plot_equity_curve_empty_data(self):
        filename = "test_equity_curve_empty.png"
        plot_equity_curve([], filename=filename) # Should not create a file, but run without error
        expected_path = os.path.join(TEST_TEMP_REPORTS_DIR, filename)
        # The function prints "No equity data to plot." and returns.
        # So, the file should NOT exist if the logic is to not plot empty data.
        self.assertFalse(os.path.exists(expected_path),
                         "Plot file was created for empty data, but shouldn't have been.")


    def test_07_plot_positions_history(self):
        trades = [
            {'timestamp': datetime(2023,1,1,10,0,0).isoformat(), 'symbol': 'AAPL', 'type': 'buy', 'quantity': 10, 'price': 150.0, 'value': 1500.0},
            {'timestamp': datetime(2023,1,3,10,0,0).isoformat(), 'symbol': 'AAPL', 'type': 'sell', 'quantity': 5, 'price': 155.0, 'value': 775.0},
            {'timestamp': datetime(2023,1,4,10,0,0).isoformat(), 'symbol': 'MSFT', 'type': 'buy', 'quantity': 20, 'price': 250.0, 'value': 5000.0},
        ]
        # Using ISO format strings for timestamps as that's what RSIStrategy saves.
        data_daterange = pd.date_range(start='2023-01-01', end='2023-01-05', freq='B')
        filename = "test_positions_history.png"

        plot_positions_history(trades, initial_cash=100000.0, data_daterange=data_daterange, filename=filename)
        expected_path = os.path.join(TEST_TEMP_REPORTS_DIR, filename)
        self.assertTrue(os.path.exists(expected_path))

    def test_08_plot_positions_history_no_trades(self):
        data_daterange = pd.date_range(start='2023-01-01', end='2023-01-05', freq='B')
        filename = "test_positions_history_no_trades.png"
        plot_positions_history([], initial_cash=100000.0, data_daterange=data_daterange, filename=filename)
        expected_path = os.path.join(TEST_TEMP_REPORTS_DIR, filename)
        self.assertTrue(os.path.exists(expected_path)) # Should still create a plot indicating no trades


if __name__ == '__main__':
    unittest.main()
