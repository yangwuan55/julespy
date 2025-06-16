import unittest
import pandas as pd
import numpy as np
import os
import sys

# Add project root to sys.path to allow importing data_manager
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data_manager import load_csv, preprocess_data, DATA_DIR as DM_DATA_DIR # Assuming DATA_DIR is exposed

# Define a directory for test-specific temporary files, relative to this test file
TEST_TEMP_DATA_DIR = os.path.join(os.path.dirname(__file__), "temp_test_data")

class TestDataManager(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create a temporary directory for test files if it doesn't exist
        if not os.path.exists(TEST_TEMP_DATA_DIR):
            os.makedirs(TEST_TEMP_DATA_DIR)
        # Ensure the main data directory (used by data_manager for cache) also exists
        # This is usually handled by data_manager.py itself, but good for isolated tests.
        if DM_DATA_DIR and not os.path.exists(DM_DATA_DIR):
             os.makedirs(DM_DATA_DIR)


    def test_load_csv_success(self):
        """Test loading a valid CSV file."""
        dummy_csv_path = os.path.join(TEST_TEMP_DATA_DIR, "test_load.csv")
        data = {'col1': [1, 2], 'col2': ['a', 'b']}
        df_orig = pd.DataFrame(data)
        df_orig.to_csv(dummy_csv_path, index=False)

        df_loaded = load_csv(dummy_csv_path)
        self.assertIsNotNone(df_loaded)
        self.assertTrue(isinstance(df_loaded, pd.DataFrame))
        pd.testing.assert_frame_equal(df_loaded, df_orig)
        os.remove(dummy_csv_path)

    def test_load_csv_file_not_found(self):
        """Test loading a non-existent CSV file."""
        df_loaded = load_csv(os.path.join(TEST_TEMP_DATA_DIR, "non_existent.csv"))
        self.assertIsNone(df_loaded) # Expecting None as per current error handling

    def test_preprocess_data_basic(self):
        """Test basic preprocessing: column renaming, timestamp index, NaN handling."""
        raw_data = {
            'Date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04']),
            'Open': [10, 11, np.nan, 13],
            'High': [15, 16, 17, 18],
            'Low': [9, 10, 11, np.nan],
            'Adj Close': [12, 13, 14, 15], # Should be renamed to 'Close'
            'Volume': [1000, np.nan, 1200, 1300]
        }
        df_raw = pd.DataFrame(raw_data)

        # Make a copy as preprocess_data might modify input or parts of it if not careful
        # Current preprocess_data creates a copy internally with df_input.copy()
        df_processed = preprocess_data(df_raw.copy())

        self.assertIsNotNone(df_processed)
        self.assertTrue(isinstance(df_processed.index, pd.DatetimeIndex))
        self.assertEqual(df_processed.index.name, "Timestamp")

        expected_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        self.assertListEqual(list(df_processed.columns), expected_cols)

        # Check NaN handling (ffill then 0 for any remaining at start)
        # Open: 10, 11, 11 (ffill), 13
        # Low: 9, 10, 11, 11 (ffill)
        # Volume: 1000, 1000 (ffill), 1200, 1300
        self.assertEqual(df_processed['Open'].iloc[2], 11.0)
        self.assertEqual(df_processed['Low'].iloc[3], 11.0) # was np.nan, ffilled from 11
        self.assertEqual(df_processed['Volume'].iloc[1], 1000.0)

        # Check if any NaNs remain after ffill and fillna(0)
        self.assertFalse(df_processed.isnull().any().any())

        # Check if a 'Close' column exists (renamed from 'Adj Close')
        self.assertTrue('Close' in df_processed.columns)
        self.assertEqual(df_processed['Close'].iloc[0], 12.0)


    def test_preprocess_data_empty_input(self):
        """Test preprocessing with an empty DataFrame."""
        df_empty = pd.DataFrame()
        df_processed = preprocess_data(df_empty)
        self.assertTrue(df_processed.empty) # Expecting empty back

    def test_preprocess_data_none_input(self):
        """Test preprocessing with None input."""
        df_processed = preprocess_data(None)
        self.assertIsNone(df_processed) # Expecting None back

    def test_preprocess_data_yahoo_multiindex(self):
        """Test preprocessing for typical Yahoo Finance multi-index columns."""
        # Create a DataFrame that mimics yfinance multi-level header structure
        # after being read from a CSV cache by data_manager.download_data
        # This structure is what preprocess_data expects if it comes from yfinance via cache
        header = pd.MultiIndex.from_tuples([
            ('Price', 'Open'), ('Price', 'High'), ('Price', 'Low'),
            ('Price', 'Close'), ('Price', 'Volume'), ('Ticker', 'MSFT')
        ])
        data_values = [
            [150.0, 152.0, 148.0, 151.0, 1000000, 'MSFT'],
            [151.0, 153.0, 149.0, 152.0, 1200000, 'MSFT']
        ]
        dates = pd.to_datetime(['2023-01-01', '2023-01-02'])
        df_yahoo_style = pd.DataFrame(data_values, index=dates, columns=header)
        df_yahoo_style.index.name = 'Date' # download_data would set this from cache

        df_processed = preprocess_data(df_yahoo_style)
        self.assertIsNotNone(df_processed)
        self.assertTrue(isinstance(df_processed.index, pd.DatetimeIndex))
        self.assertEqual(df_processed.index.name, "Timestamp")
        expected_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        self.assertListEqual(list(df_processed.columns), expected_cols)
        self.assertEqual(df_processed['Close'].iloc[0], 151.0)


    @classmethod
    def tearDownClass(cls):
        # Clean up the temporary directory and its contents
        if os.path.exists(TEST_TEMP_DATA_DIR):
            for item in os.listdir(TEST_TEMP_DATA_DIR):
                os.remove(os.path.join(TEST_TEMP_DATA_DIR, item))
            os.rmdir(TEST_TEMP_DATA_DIR)

if __name__ == '__main__':
    # This allows running the tests directly from this file
    # However, typically you'd use `python -m unittest discover tests` or pytest

    # Add a check for DATA_DIR from data_manager.py to ensure it's usable
    # This is a bit of a hack for direct run; test runners handle paths better.
    # We've already appended '..' to sys.path.
    if 'data_manager' in sys.modules:
        print(f"data_manager.DATA_DIR resolved to: {DM_DATA_DIR if DM_DATA_DIR else 'Not defined/accessible'}")
    else:
        print("Warning: data_manager module not loaded as expected for DATA_DIR check.")

    unittest.main()
