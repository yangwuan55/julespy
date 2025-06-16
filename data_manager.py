import pandas as pd
import yfinance as yf
from binance.client import Client
import os
from datetime import datetime
import numpy as np # For creating dummy NaN values in example

# Define DATA_DIR at module level for potential external use (e.g., by GUI tabs)
DATA_DIR = "data"

# Ensure the data directory exists at module load time
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    print(f"Data directory '{DATA_DIR}' created.")

def load_csv(file_path: str) -> pd.DataFrame | None:
    """
    Reads a CSV file into a pandas DataFrame.

    Args:
        file_path (str): The path to the CSV file.

    Returns:
        pandas.DataFrame | None: The DataFrame loaded from the CSV file.
                                 Returns None if an error occurs (e.g., file not found, parsing error).

    Raises:
        Prints error messages to console for common issues.
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

def load_xlsx(file_path: str) -> pd.DataFrame | None:
    """
    Reads an XLSX (Excel) file into a pandas DataFrame.

    Args:
        file_path (str): The path to the XLSX file. Assumes the first sheet is to be read.

    Returns:
        pandas.DataFrame | None: The DataFrame loaded from the XLSX file.
                                 Returns None if an error occurs (e.g., file not found, parsing error).

    Raises:
        Prints error messages to console for common issues.
    """
    try:
        df = pd.read_excel(file_path)
        return df
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except ValueError as ve:
        print(f"Error: Could not read {file_path}. Ensure it is a valid XLSX file. Details: {ve}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while reading {file_path}: {e}")
        return None

def download_data(symbol: str, start_date: str, end_date: str, source: str = 'yahoo') -> pd.DataFrame | None:
    """
    Downloads historical financial data for a given symbol and date range from a specified source.
    Caches the downloaded data to the `data/` directory to avoid re-downloading.
    If cached data is found, it's loaded directly.

    Args:
        symbol (str): The stock/cryptocurrency symbol (e.g., 'AAPL' for Yahoo, 'BTCUSDT' for Binance).
        start_date (str): Start date for the data in 'YYYY-MM-DD' format.
        end_date (str): End date for the data in 'YYYY-MM-DD' format.
        source (str): The data source, either 'yahoo' (Yahoo Finance) or 'binance' (Binance).
                      Defaults to 'yahoo'.

    Returns:
        pandas.DataFrame | None: A DataFrame containing the historical OHLCV (Open, High, Low, Close, Volume) data.
                                 The DataFrame index is set to 'Date' (for Yahoo) or 'timestamp' (for Binance).
                                 Returns None if data download or processing fails.

    Raises:
        Prints error messages to console for common issues like network errors or API problems.
    """
    filename_start_date = start_date.replace('-', '')
    filename_end_date = end_date.replace('-', '')
    # Use DATA_DIR constant for constructing cache path
    cache_filename = os.path.join(DATA_DIR, f"{symbol.upper()}_{source.upper()}_{filename_start_date}_{filename_end_date}.csv")

    if os.path.exists(cache_filename):
        print(f"Loading cached data for {symbol} from {cache_filename}")
        try:
            if source == 'yahoo':
                # Yahoo data saved by yf.download often has a MultiIndex header if group_by='column' (default)
                # or if saved directly. The specific loading here handles that structure.
                data = pd.read_csv(cache_filename, header=[0,1], index_col=0, skiprows=[2])
                data.index = pd.to_datetime(data.index)
                data.index.name = 'Date'
            elif source == 'binance':
                data = pd.read_csv(cache_filename, index_col=0)
                data.index = pd.to_datetime(data.index)
                data.index.name = 'timestamp'
            else: # Should ideally not be reached if source is validated, but as a fallback:
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
            # yfinance data has 'Date' as index by default. Column names might be MultiIndex.
        elif source == 'binance':
            client = Client()
            start_ms = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
            # Binance API end_ms is exclusive for get_historical_klines, so adjust if necessary
            # or ensure end_date is inclusive for user. For daily, it's usually fine.
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
            # Select relevant columns and set timestamp as index
            data = data[['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']].set_index('timestamp')
            # Convert OHLCV columns to numeric, as Binance API might return them as strings
            for col_name in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if col_name in data.columns: # Ensure column exists before conversion
                    data[col_name] = pd.to_numeric(data[col_name], errors='coerce')
        else:
            print(f"Error: Unknown source '{source}'. Choose 'yahoo' or 'binance'.")
            return None

        if data is not None and not data.empty:
            # Save with index (Date or timestamp)
            data.to_csv(cache_filename, index=True)
            print(f"Data for {symbol} saved to {cache_filename}")
        return data
    except Exception as e:
        print(f"Error downloading/processing data for {symbol} from {source}: {e}")
        return None

def preprocess_data(df_input: pd.DataFrame | None) -> pd.DataFrame | None:
    """
    Preprocesses financial market data to a unified format.

    The unified format consists of:
    - Index: 'Timestamp' (pandas.DatetimeIndex)
    - Columns: 'Open', 'High', 'Low', 'Close', 'Volume' (all numeric)

    Preprocessing steps include:
    1.  **Column Unification**:
        - Handles potential MultiIndex columns from sources like Yahoo Finance (cached).
        - Renames common column name variations (e.g., 'Date' to 'Timestamp', 'Adj Close' to 'Close')
          to the standard names.
    2.  **Timestamp Indexing**:
        - Converts the date/time column to a pandas DatetimeIndex and sets it as 'Timestamp'.
        - If already indexed by a date-like field, standardizes its name to 'Timestamp'.
    3.  **Column Selection**: Ensures only 'Open', 'High', 'Low', 'Close', 'Volume' columns are present.
                            Missing columns are added with NaN values before filling.
    4.  **Missing Data Handling**:
        - Forward fills (`ffill()`) missing values to propagate last known values.
        - Fills any remaining NaNs (typically at the beginning of the dataset) with 0.

    Args:
        df_input (pandas.DataFrame | None): Input DataFrame, potentially with:
            - Varied column names (e.g., 'Date', 'Adj Close').
            - MultiIndex columns (common from yfinance cached data).
            - Missing values (NaNs).
            - Date information either as a column or as the index.

    Returns:
        pandas.DataFrame | None: A new DataFrame with the unified structure and handled missing values.
                                 Returns the input DataFrame if it's None or empty.
                                 Returns the DataFrame as is if critical timestamp processing fails.

    Notes:
        The function attempts to be robust to different input structures but assumes
        common conventions for financial timeseries data.
    """
    if df_input is None or df_input.empty:
        print("Input DataFrame is empty or None. No preprocessing done.")
        return df_input

    df = df_input.copy()

    target_columns_ohlcv = ['Open', 'High', 'Low', 'Close', 'Volume'] # For data part

    # 1. Unify K-line format - Column Name Handling (especially for MultiIndex from yfinance cache)
    if isinstance(df.columns, pd.MultiIndex):
        print("Preprocessing MultiIndex columns...")
        # Flatten MultiIndex: typically takes the first level for OHLCV, e.g. ('Price', 'Open') -> 'Open'
        # This simplification assumes the desired value is in the first level name.
        # A more robust approach might inspect both levels.

        # Attempt to pick OHLCV from known structures like ('Price', 'Open') or ('Open', 'TICKER')
        new_cols = {}
        processed_col_names = set()

        for col_tuple in df.columns:
            # Find the relevant part of the tuple, e.g. 'Open' from ('Price', 'Open')
            # Or 'Adj Close' to map to 'Close'
            ohlcv_name = None
            if 'Adj Close' in col_tuple : ohlcv_name = 'Close' # Map Adj Close first
            elif 'Close' in col_tuple and 'Close' not in processed_col_names : ohlcv_name = 'Close'
            elif 'Open' in col_tuple and 'Open' not in processed_col_names : ohlcv_name = 'Open'
            elif 'High' in col_tuple and 'High' not in processed_col_names : ohlcv_name = 'High'
            elif 'Low' in col_tuple and 'Low' not in processed_col_names : ohlcv_name = 'Low'
            elif 'Volume' in col_tuple and 'Volume' not in processed_col_names : ohlcv_name = 'Volume'

            if ohlcv_name and ohlcv_name not in new_cols: # Take first match for each OHLCV type
                new_cols[ohlcv_name] = df[col_tuple]
                processed_col_names.add(ohlcv_name)

        if len(new_cols) >= 4: # Found at least OHLC
            df = pd.DataFrame(new_cols)
            # Preserve original index name if it's date-like
            if df_input.index.name in ['Date', 'timestamp', 'Datetime']:
                df.index.name = df_input.index.name
        else:
            print("Warning: MultiIndex column parsing did not yield expected OHLCV. Attempting basic flattening.")
            # Fallback: simple flattening, may not be ideal for all yfinance structures
            df.columns = df.columns.get_level_values(0)


    # 2. Standardize common column name variations to target names
    rename_map = {}
    for col in df.columns:
        col_str = str(col) # Ensure column name is a string for .lower()
        col_lower = col_str.lower()
        if 'date' == col_lower and 'timestamp' not in rename_map.values(): rename_map[col] = 'Timestamp' # If 'Date' is a column
        elif 'adj close' == col_lower: rename_map[col] = 'Close'
        elif 'open' == col_lower and 'Open' not in rename_map.values(): rename_map[col] = 'Open'
        elif 'high' == col_lower and 'High' not in rename_map.values(): rename_map[col] = 'High'
        elif 'low' == col_lower and 'Low' not in rename_map.values(): rename_map[col] = 'Low'
        elif 'close' == col_lower and 'Close' not in rename_map.values(): rename_map[col] = 'Close'
        elif 'volume' == col_lower and 'Volume' not in rename_map.values(): rename_map[col] = 'Volume'
    df.rename(columns=rename_map, inplace=True)

    # 3. Timestamp Indexing: Ensure a DatetimeIndex named 'Timestamp'
    if 'Timestamp' in df.columns: # If 'Timestamp' (or previously 'Date') was a column
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        df.set_index('Timestamp', inplace=True)
    elif isinstance(df.index, pd.DatetimeIndex): # If index is already DatetimeIndex
        df.index.name = 'Timestamp' # Standardize name
    else: # Attempt to convert current index if it's not DatetimeIndex
        try:
            df.index = pd.to_datetime(df.index)
            df.index.name = 'Timestamp'
            print("Converted existing index to DatetimeIndex and named 'Timestamp'.")
        except Exception as e:
            print(f"Warning: Could not convert DataFrame index to DatetimeIndex: {e}. Index remains as is.")
            # If index conversion fails, it might be problematic for time-series operations.
            # Depending on requirements, could return None or raise error. For now, proceed.

    # 4. Ensure all target OHLCV columns exist, add if missing (will be NaN initially)
    for col_name in target_columns_ohlcv:
        if col_name not in df.columns:
            df[col_name] = np.nan
            print(f"Added missing column: {col_name} (filled with NaN initially)")

    # Select and reorder to standard OHLCV format (plus any other existing columns not specified)
    # Keep other columns if they exist, but ensure OHLCV are present and first.
    other_existing_cols = [col for col in df.columns if col not in target_columns_ohlcv]
    df = df[target_columns_ohlcv + other_existing_cols]


    # 5. Handle missing data in OHLCV columns
    for col_name in target_columns_ohlcv:
        if col_name in df.columns:
            df[col_name].ffill(inplace=True) # Forward fill first
            df[col_name].fillna(0, inplace=True) # Then fill remaining (e.g., at start) with 0
        else:
            # This should not happen if step 4 worked, but as a safeguard:
            print(f"Warning: Column {col_name} still missing after attempting to add it.")


    print("Data preprocessing complete.")
    return df


if __name__ == '__main__':
    print("--- Data Manager Module Demonstrations ---")

    # Setup for dummy files
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR) # Should be created above, but ensure for demo
    dummy_csv_file = os.path.join(DATA_DIR, "demo_data.csv")
    dummy_excel_file = os.path.join(DATA_DIR, "demo_data.xlsx")

    # Create dummy CSV
    pd.DataFrame({
        'Date': ['2023-01-01', '2023-01-02', '2023-01-03'],
        'Open': [100, 101, 102], 'High': [102, 103, 102.5],
        'Low': [99, 100, 100.5], 'Adj Close': [101, 102, 101.5], # Test 'Adj Close' renaming
        'Volume': [1000, 1200, 1100],
        'SomeOtherColumn': ['x', 'y', 'z']
    }).to_csv(dummy_csv_file, index=False)

    # Create dummy Excel
    pd.DataFrame({
        'Timestamp': pd.to_datetime(['2023-02-01', '2023-02-02']),
        'open': [200, 201], 'high': [202, 203], # Test lowercase renaming
        'low': [199, 200], 'close': [201, 202],
        'volume': [2000, 2100],
        'EmptyColWithNaN': [np.nan, 1]
    }).to_excel(dummy_excel_file, index=False)

    print(f"\n1. Testing load_csv with '{dummy_csv_file}':")
    df_csv = load_csv(dummy_csv_file)
    if df_csv is not None: print(df_csv.head())

    print(f"\n2. Testing load_xlsx with '{dummy_excel_file}':")
    df_excel = load_xlsx(dummy_excel_file)
    if df_excel is not None: print(df_excel.head())

    print("\n3. Testing preprocess_data with CSV data:")
    if df_csv is not None:
        df_processed_csv = preprocess_data(df_csv)
        if df_processed_csv is not None:
            print("Processed CSV data:")
            print(df_processed_csv.head())
            print("Info:")
            df_processed_csv.info()

    print("\n4. Testing preprocess_data with Excel data:")
    if df_excel is not None:
        df_processed_excel = preprocess_data(df_excel)
        if df_processed_excel is not None:
            print("Processed Excel data:")
            print(df_processed_excel.head())
            print("Info:")
            df_processed_excel.info()
            print("NaN check after preprocessing (Excel):")
            print(df_processed_excel.isnull().sum())


    print("\n5. Testing download_data (example with AAPL, short period):")
    # This will use cache if already downloaded by other modules' tests
    aapl_data = download_data('AAPL', '2023-01-01', '2023-01-10', source='yahoo')
    if aapl_data is not None:
        print("Downloaded AAPL data (head):")
        print(aapl_data.head())
        print("\nPreprocessing downloaded AAPL data:")
        aapl_processed = preprocess_data(aapl_data)
        if aapl_processed is not None:
            print(aapl_processed.head())
            print("Info for processed AAPL data:")
            aapl_processed.info()
            print("NaN check for processed AAPL data:")
            print(aapl_processed.isnull().sum())

    # Cleanup dummy files
    if os.path.exists(dummy_csv_file): os.remove(dummy_csv_file)
    if os.path.exists(dummy_excel_file): os.remove(dummy_excel_file)
    print(f"\nCleaned up dummy files: {dummy_csv_file}, {dummy_excel_file}")

    print("\n--- Data Manager Demonstrations Finished ---")
