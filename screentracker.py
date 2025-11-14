# This script is a "stock screener"
# that searches for high-quality, liquid stocks on the NYSE and LSE.
#
# It combines:
# 1. Fundamental Analysis (P/E, P/B, Dividends)
# 2. Technical Analysis (200-Day Moving Average)
# 3. Liquidity/Safety Filter (Average Volume)
#
# The goal is to find stocks that are "reasonably priced" (P/E < 25),
# "in a long-term uptrend" (technical), and "safe to trade" (volume).

import yfinance as yf
import pandas as pd
import time
import requests
from io import StringIO
from datetime import datetime

# --- 1. Define Filtering Criteria ---
# These are the rules for our screener.
# You can change these values to be more strict or loose.
MAX_PE_RATIO = 25.0  # Max P/E (Price-to-Earnings) Ratio
MAX_PB_RATIO = 1.5  # Max P/B (Price-to-Book) Ratio
MIN_DIV_YIELD = 0.02  # Minimum Dividend Yield (0.02 = 2%)
MIN_AVG_VOLUME = 100000  # Minimum average daily trading volume


# --- 2. Automatic Ticker List Fetching Functions ---

def get_sp500_tickers():
    """
    Fetches the S&P 500 (NYSE proxy) tickers from Wikipedia.
    """
    print("Fetching S&P 500 tickers (NYSE proxy) from Wikipedia...")
    try:
        # The Wikipedia page URL
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'

        # We must send a User-Agent header to pretend we are a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
        response = requests.get(url, headers=headers)

        # We wrap the text in StringIO and specify the table ID to be robust
        tables = pd.read_html(StringIO(response.text), attrs={'id': 'constituents'})

        # The first table (index 0) is the one we want
        sp500_table = tables[0]

        # The ticker column is named 'Symbol'
        # We replace 'BRK.B' with 'BRK-B' for yfinance compatibility
        tickers = sp500_table['Symbol'].str.replace('.', '-', regex=False).tolist()
        print(f"  > Found {len(tickers)} S&P 500 tickers.")
        return tickers
    except Exception as e:
        print(f"[ERROR] Could not fetch S&P 500 tickers: {e}")
        return []


def get_ftse100_tickers():
    """
    Fetches the FTSE 100 (LSE proxy) tickers from Wikipedia.
    """
    print("Fetching FTSE 100 tickers (LSE proxy) from Wikipedia...")
    try:
        # Added the missing '://' in the URL
        url = 'https://en.wikipedia.org/wiki/FTSE_100_Index'

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
        response = requests.get(url, headers=headers)

        # We pass the HTML text to pandas, and also specify the table ID
        tables = pd.read_html(StringIO(response.text), attrs={'id': 'constituents'})

        ftse100_table = tables[0]
        # The ticker column is named 'Ticker'
        # We must add ".L" for yfinance to recognize LSE stocks
        tickers = (ftse100_table['Ticker'] + '.L').tolist()
        print(f"  > Found {len(tickers)} FTSE 100 tickers.")
        return tickers
    except Exception as e:
        print(f"[ERROR] Could not fetch FTSE 100 tickers: {e}")
        return []


def get_stock_tickers():
    """
    Combines the ticker lists from all exchanges.
    """
    print("\n--- Phase 1: Fetching Ticker Lists ---")

    # We will test with a small slice (e.g., 10 from each)
    # To run the full list, remove "[:xx]"
    # WARNING: The full list (600+ stocks) will take over 10 minutes to run!
    sp500 = get_sp500_tickers()[:20]
    ftse100 = get_ftse100_tickers()[:20]

    all_tickers = sp500 + ftse100
    print(f"\nTotal tickers to analyze: {len(all_tickers)}")
    return all_tickers


# --- 3. Data Fetching and Processing Function ---

def get_stock_data(tickers):
    """
    Fetches the financial data for each ticker in the list.
    """
    print("\n--- Phase 2: Fetching Financial Data ---")
    print("This will take some time, please be patient...\n")

    stock_data = []

    for ticker in tickers:
        try:
            # 1. Create the yfinance Ticker object
            stock = yf.Ticker(ticker)

            # 2. Get the main info dictionary
            info = stock.info

            # 3. Get historical data to calculate 200-DMA
            # We fetch 210 days to ensure we have enough data for a 200-day SMA
            history = stock.history(period="210d")

            # 4. Calculate 200-Day Moving Average
            ma_200 = 0
            if len(history) >= 200:
                ma_200 = history['Close'].rolling(window=200).mean().iloc[-1]

            # We use .get() to avoid errors if a key is missing
            data = {
                'Symbol': ticker,
                'Company': info.get('shortName'),
                'Sector': info.get('sector'),
                'P/E': info.get('trailingPE'),
                'P/B': info.get('priceToBook'),
                'AvgVolume': info.get('averageVolume'),  # <-- ADDED VOLUME
                'DivYield': info.get('dividendYield'),
                'Current Price': info.get('currentPrice'),
                '200-DMA': ma_200
            }

            stock_data.append(data)

            # Updated print statement
            print(
                f"  > Fetched: {ticker} (P/E: {data['P/E']:.2f}, Volume: {data['AvgVolume']}, Price: {data['Current Price']})")

            # IMPORTANT: Pause for 1 second to avoid being rate-limited
            time.sleep(1)

        except Exception as e:
            print(f"[ERROR] Could not fetch data for {ticker}: {e}")
            # Still pause, especially for 404-type errors
            time.sleep(1)

    return stock_data


# --- 4. Main Function ---

def run_screener():
    """
    Main function to run the entire screener.
    """
    # Step 1: Get all tickers
    tickers = get_stock_tickers()

    if not tickers:
        print("No tickers found. Exiting.")
        return

    # Step 2: Fetch data for all tickers
    stock_data = get_stock_data(tickers)

    if not stock_data:
        print("No stock data could be fetched. Exiting.")
        return

    # Step 3: Convert to DataFrame (using Pandas)
    df = pd.DataFrame(stock_data)

    # Set the 'Symbol' column as the index for better readability
    df = df.set_index('Symbol')

    # Data Cleaning: Replace 'None' or 'NaN' values with 0
    # This is a simple way to handle missing data so our filters don't crash.
    df = df.fillna(0)

    print("\n--- Raw Data Fetched ---")
    print(df)

    # --- Step 4: Apply Filters ---

    print("\n--- Phase 3: Filtering for Quality Stocks ---")

    # Create the filtering conditions
    # Ensure conversion to numeric type, just in case
    conditie_pe = pd.to_numeric(df['P/E']) < MAX_PE_RATIO  # <-- REPLACED PEG with P/E
    conditie_pb = pd.to_numeric(df['P/B']) < MAX_PB_RATIO
    conditie_div = pd.to_numeric(df['DivYield']) > MIN_DIV_YIELD
    conditie_volum = pd.to_numeric(df['AvgVolume']) > MIN_AVG_VOLUME  # <-- ADDED VOLUME FILTER

    # Our Technical Analysis filter
    conditie_ma = pd.to_numeric(df['Current Price']) > pd.to_numeric(df['200-DMA'])

    # Validity conditions (to filter out 0s from missing data)
    conditie_validitate = (pd.to_numeric(df['P/E']) > 0) & (pd.to_numeric(df['P/B']) > 0)  # Keep P/E > 0 (profitable)
    conditie_ma_validitate = pd.to_numeric(df['200-DMA']) > 0  # Ensure 200-DMA was calculated

    # Combine all conditions
    final_filter = (
            conditie_pe &
            conditie_pb &
            conditie_div &
            conditie_ma &
            conditie_volum & 
            conditie_validitate &
            conditie_ma_validitate
    )

    # --- Step 5: Show Results ---

    final_results = df[final_filter]

    if final_results.empty:
        print("\n--- No stocks passed all the filters. ---")
        print("Try relaxing your criteria (e.g., a higher P/E) or analyzing more stocks.")
    else:
        print(f"\n--- SUCCESS! Found {len(final_results)} Undervalued Stocks ---")

        # Display the final, filtered list
        print(final_results[[
            'Company',
            'Sector',
            'P/E',  # <-- BACK TO P/E
            'P/B',
            'DivYield',
            'AvgVolume',  # <-- ADDED
            'Current Price',
            '200-DMA'
        ]])

        # --- NEW: Save results to CSV ---
        try:
            # Create a unique filename with a timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            filename = f"undervalued_stocks_{timestamp}.csv"

            # Save the DataFrame to a CSV file
            final_results.to_csv(filename)

            print(f"\nSuccessfully saved results to: {filename}")

        except Exception as e:
            print(f"\n[ERROR] Could not save results to CSV: {e}")
        # --- END NEW ---


# --- Run the script ---
if __name__ == "__main__":
    run_screener()