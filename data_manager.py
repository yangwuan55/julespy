import pandas as pd
import yfinance as yf
from binance.client import Client
import os
from datetime import datetime
import numpy as np # For creating dummy NaN values in example

# Ensure the data directory exists
if not os.path.exists('data'):
    os.makedirs('data')

def load_csv(file_path):
    """
    Reads a CSV file into a pandas DataFrame.

    Args:
        file_path (str): The path to the CSV file.

    Returns:
        pandas.DataFrame: The DataFrame loaded from the CSV file, or None if an error occurs.
    """
    try:
        df = pd.read_csv(file_path)
        return df
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except pd.errors.EmptyDataError:
        print(f"Error: No data found in {file_path}")
        return None
    except pd.errors.ParserError:
        print(f"Error: Could not parse {file_path}. Ensure it is a valid CSV.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while reading {file_path}: {e}")
        return None

def load_xlsx(file_path):
    """
    Reads an XLSX file into a pandas DataFrame.

    Args:
        file_path (str): The path to the XLSX file.

    Returns:
        pandas.DataFrame: The DataFrame loaded from the XLSX file, or None if an error occurs.
    """
    try:
        df = pd.read_excel(file_path)
        return df
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except ValueError as ve: # Often raised for bad XLSX files by openpyxl
        print(f"Error: Could not read {file_path}. Ensure it is a valid XLSX file. Details: {ve}")
        return None
    except Exception as e: # General exception for other pandas/excel related errors
        print(f"An unexpected error occurred while reading {file_path}: {e}")
        return None

def download_data(symbol, start_date, end_date, source='yahoo'):
    """
    Downloads historical financial data and caches it.

    Args:
        symbol (str): The stock symbol (e.g., 'AAPL' for Yahoo, 'BTCUSDT' for Binance).
        start_date (str): Start date in 'YYYY-MM-DD' format.
        end_date (str): End date in 'YYYY-MM-DD' format.
        source (str): 'yahoo' or 'binance'.

    Returns:
        pandas.DataFrame: DataFrame with historical data, or None if an error occurs.
    """
    filename_start_date = start_date.replace('-', '')
    filename_end_date = end_date.replace('-', '')
    cache_filename = f"data/{symbol.upper()}_{source.upper()}_{filename_start_date}_{filename_end_date}.csv"

    if os.path.exists(cache_filename):
        print(f"Loading cached data for {symbol} from {cache_filename}")
        try:
            if source == 'yahoo':
                data = pd.read_csv(cache_filename, header=[0,1], index_col=0, skiprows=[2])
                data.index = pd.to_datetime(data.index)
                data.index.name = 'Date'
            elif source == 'binance':
                data = pd.read_csv(cache_filename, index_col=0)
                data.index = pd.to_datetime(data.index)
                data.index.name = 'timestamp'
            else:
                data = pd.read_csv(cache_filename, index_col=0)
            return data
        except Exception as e:
            print(f"Error loading cached data {cache_filename}: {e}. Attempting to download again.")

    print(f"Downloading data for {symbol} from {source} for {start_date} to {end_date}")
    data = None
    try:
        if source == 'yahoo':
            data = yf.download(symbol, start=start_date, end=end_date, auto_adjust=True, group_by='column')
            if data.empty:
                print(f"No data found for {symbol} on Yahoo Finance for the given period.")
                return None
        elif source == 'binance':
            client = Client()
            start_ms = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
            end_ms = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
            klines = client.get_historical_klines(symbol, Client.KLINE_INTERVAL_1DAY, start_ms, end_ms_str=str(end_ms))
            if not klines:
                print(f"No data found for {symbol} on Binance for the given period.")
                return None
            columns = ['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close_time',
                       'Quote_asset_volume', 'Number_of_trades', 'Taker_buy_base_asset_volume',
                       'Taker_buy_quote_asset_volume', 'Ignore']
            data = pd.DataFrame(klines, columns=columns)
            data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
            data = data[['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']].set_index('timestamp')
            for col in data.columns:
                if col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    data[col] = pd.to_numeric(data[col], errors='coerce')
        else:
            print(f"Error: Unknown source '{source}'. Choose 'yahoo' or 'binance'.")
            return None

        if data is not None and not data.empty:
            data.to_csv(cache_filename, index=True)
            print(f"Data for {symbol} saved to {cache_filename}")
        return data
    except Exception as e:
        print(f"Error downloading/processing data for {symbol} from {source}: {e}")
        return None

def preprocess_data(df_input):
    """
    Preprocesses financial data to a unified K-line format and handles missing values.

    Args:
        df_input (pandas.DataFrame): Input DataFrame with financial data.

    Returns:
        pandas.DataFrame: Preprocessed DataFrame.
    """
    if df_input is None or df_input.empty:
        print("Input DataFrame is empty or None. No preprocessing done.")
        return df_input

    df = df_input.copy()

    # 1. Unify K-line format
    # Standard column names
    target_columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']

    # Handle Yahoo Finance specific column structure (MultiIndex)
    if isinstance(df.columns, pd.MultiIndex):
        # Example: [('Price', 'Close'), ('Price', 'High'), ..., ('Ticker', 'AAPL')]
        # We want to simplify to single level columns like 'Close', 'High', etc.
        # And use the 'Price' part. If 'Ticker' level exists, we can drop it for data columns.

        # First, try to get columns that might be like ('Price', 'Open') or ('Open', 'AAPL')
        simple_cols = {}
        for col_tuple in df.columns:
            # col_tuple could be ('Price', 'Open') or ('Open', 'AAPL') or just 'Open'
            # We look for OHLCV keywords in the tuple elements
            if 'Open' in col_tuple: simple_cols['Open'] = df[col_tuple]
            elif 'High' in col_tuple: simple_cols['High'] = df[col_tuple]
            elif 'Low' in col_tuple: simple_cols['Low'] = df[col_tuple]
            # Yahoo 'Close' is often 'Adj Close' if auto_adjust=False, but with auto_adjust=True it's 'Close'
            # and represents adjusted.
            elif 'Close' in col_tuple: simple_cols['Close'] = df[col_tuple]
            elif 'Volume' in col_tuple: simple_cols['Volume'] = df[col_tuple]

        if len(simple_cols) >= 4: # Check if we found OHLC and maybe V
             df_new = pd.DataFrame(simple_cols)
             # If original df index is 'Date', copy it
             if df.index.name == 'Date' or df.index.name == 'timestamp':
                 df_new.index = df.index
             df = df_new
        else: # Fallback if tuple parsing is not as expected
            print("Warning: Could not reliably parse MultiIndex columns for Yahoo. Attempting basic flattening.")
            # Basic flattening: take the first level of MultiIndex if it's like ('Price', 'Open')
            # or the second if it's like ('Open', 'Symbol')
            if any('Price' in c for c in df.columns.get_level_values(0)):
                 df.columns = df.columns.get_level_values(0) # e.g. Price_Open -> Open
            elif len(df.columns.levels) > 1: # e.g. ('Open', 'AAPL')
                 df.columns = df.columns.get_level_values(0)


    # Rename columns:
    rename_map = {}
    for col in df.columns:
        col_lower = str(col).lower()
        if 'date' in col_lower and 'timestamp' not in col_lower : # e.g. 'Date' from Yahoo
            rename_map[col] = 'Timestamp'
        elif 'adj close' in col_lower:
            rename_map[col] = 'Close'
        elif 'open' in col_lower: rename_map[col] = 'Open'
        elif 'high' in col_lower: rename_map[col] = 'High'
        elif 'low' in col_lower: rename_map[col] = 'Low'
        elif 'close' in col_lower and 'adj close' not in col_lower : # ensure 'Close' is not overwritten by 'Adj Close' logic if both present
             if 'Close' not in rename_map.values(): rename_map[col] = 'Close'
        elif 'volume' in col_lower: rename_map[col] = 'Volume'

    df.rename(columns=rename_map, inplace=True)

    # If 'Timestamp' is a column (after potential rename from 'Date'), convert and set as index
    if 'Timestamp' in df.columns:
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        df.set_index('Timestamp', inplace=True)
    elif df.index.name is not None and ('date' in str(df.index.name).lower() or 'timestamp' in str(df.index.name).lower()):
        # If index is already date-like (e.g., 'Date' from Yahoo, 'timestamp' from Binance)
        df.index = pd.to_datetime(df.index)
        df.index.name = 'Timestamp' # Standardize index name
    else:
        print("Warning: No clear 'Date' or 'Timestamp' column/index found for setting as Timestamp index.")
        # Attempt to convert the current index if it's not already datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
                df.index.name = 'Timestamp'
                print("Converted existing index to DatetimeIndex and named 'Timestamp'.")
            except Exception as e:
                print(f"Error: Could not convert existing index to DatetimeIndex: {e}")
                return df # Return df as is if timestamping fails critically

    # Ensure all target columns exist, add if missing (will be NaN initially)
    for col in target_columns:
        if col not in df.columns and col != 'Timestamp': # Timestamp is index
            df[col] = np.nan
            print(f"Added missing column: {col}")

    # Select and reorder to standard format
    # Filter out columns not in target_columns (if Timestamp is index)
    final_cols = [tc for tc in target_columns if tc != 'Timestamp']
    df = df[final_cols]


    # 2. Handle missing data
    # Forward fill
    df.ffill(inplace=True)
    # Fill remaining NaNs (e.g., at the beginning) with 0
    df.fillna(0, inplace=True)

    print("Data preprocessing complete.")
    return df


if __name__ == '__main__':
    print("--- Data Loading Examples (CSV/XLSX) ---")
    # ... (previous CSV/XLSX loading examples - kept for brevity) ...
    try:
        with open("dummy.csv", "w") as f:
            f.write("col1,col2\n1,a\n2,b")
        # Create a dummy CSV with some financial-like data and missing values for preprocessing demo
        dummy_financial_data = {
            'Date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05']),
            'Open': [10, 11, np.nan, 13, 14],
            'High': [15, np.nan, 17, 18, 19],
            'Low': [9, 10, 11, 12, np.nan],
            'Adj Close': [12, 13, 14, np.nan, 16],
            'Volume': [1000, 1100, 1200, np.nan, 1400]
        }
        dummy_df = pd.DataFrame(dummy_financial_data)
        dummy_df.to_csv("dummy_financial.csv", index=False)
        print("Dummy financial CSV created for preprocessing demo.")
    except Exception as e:
        print(f"Failed to create dummy financial CSV: {e}")

    print("\n--- Preprocessing Example with Dummy Financial CSV ---")
    raw_dummy_financial_data = load_csv("dummy_financial.csv")
    if raw_dummy_financial_data is not None:
        print("\nRaw Dummy Financial Data:")
        print(raw_dummy_financial_data)
        print("\nMissing values before preprocessing:")
        print(raw_dummy_financial_data.isnull().sum())

        preprocessed_dummy_data = preprocess_data(raw_dummy_financial_data)
        print("\nPreprocessed Dummy Financial Data:")
        print(preprocessed_dummy_data)
        print("\nMissing values after preprocessing:")
        print(preprocessed_dummy_data.isnull().sum())
    print("--- End of Preprocessing Example ---\n")

    print("\n--- Data Downloading and Preprocessing Examples ---")
    # Yahoo Finance Example (AAPL)
    print("\nFetching Apple Inc. (AAPL) data from Yahoo Finance...")
    aapl_data_raw = download_data('AAPL', '2023-01-01', '2023-01-10', source='yahoo')
    if aapl_data_raw is not None:
        print("\nRaw AAPL Data (first 5 rows):")
        print(aapl_data_raw.head())

        print("\nPreprocessing AAPL data...")
        aapl_data_processed = preprocess_data(aapl_data_raw)
        print("\nPreprocessed AAPL Data (first 5 rows):")
        print(aapl_data_processed.head())
        print("\nMissing values in AAPL preprocessed data:")
        print(aapl_data_processed.isnull().sum())

    # Binance Example (BTCUSDT) - will likely use cached if available, or fail if not due to geo-restriction
    # For demonstration, let's create a dummy Binance-like cache file if it doesn't exist
    # to ensure preprocessing gets tested for Binance structure too.
    binance_cache_path = "data/BTCUSDT_BINANCE_20230101_20230110.csv"
    if not os.path.exists(binance_cache_path):
        try:
            print(f"\nCreating dummy Binance cache file: {binance_cache_path} for demo purposes.")
            # Structure: timestamp,Open,High,Low,Close,Volume
            dummy_binance_content = (
                "timestamp,Open,High,Low,Close,Volume\n"
                "1672531200000,16500.0,16600.0,16400.0,16550.0,1000.0\n" # 2023-01-01 00:00:00
                "1672617600000,16550.0,16700.0,,16650.0,1200.0\n"      # 2023-01-02 00:00:00 (Low is NaN)
                "1672704000000,16650.0,16800.0,16600.0,16750.0,1100.0\n" # 2023-01-03 00:00:00
            )
            with open(binance_cache_path, "w") as f:
                f.write(dummy_binance_content)
        except Exception as e:
            print(f"Error creating dummy Binance cache: {e}")

    print("\nFetching BTC/USDT data from Binance (may use dummy cache)...")
    btcusdt_data_raw = download_data('BTCUSDT', '2023-01-01', '2023-01-10', source='binance')
    if btcusdt_data_raw is not None:
        print("\nRaw BTC/USDT Data (first 5 rows):")
        # If loaded from the dummy cache, index might be int. If from real API, it's datetime.
        # The download_data function already converts Binance index to datetime.
        print(btcusdt_data_raw.head())

        print("\nPreprocessing BTC/USDT data...")
        btcusdt_data_processed = preprocess_data(btcusdt_data_raw.copy()) # Pass copy to avoid modifying original
        print("\nPreprocessed BTC/USDT Data (first 5 rows):")
        print(btcusdt_data_processed.head())
        print("\nMissing values in BTC/USDT preprocessed data:")
        print(btcusdt_data_processed.isnull().sum())

    print("\n--- End of Data Downloading and Preprocessing Examples ---")
