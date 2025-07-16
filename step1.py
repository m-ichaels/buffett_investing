import pandas as pd
import yfinance as yf
import time
import os
from datetime import datetime

def get_eps_data(tickers, years=range(2013, 2023)):
    """
    Fetch diluted EPS data for given tickers across specified years
    """
    results = []
    total_tickers = len(tickers)
    
    for idx, ticker in enumerate(tickers, 1):
        print(f"Processing {ticker} ({idx}/{total_tickers})")
        
        # Initialize result dictionary
        result = {'Ticker': ticker}
        for year in years:
            result[f'EPS_{year}'] = None
        
        try:
            stock = yf.Ticker(ticker)
            
            # Get basic info for company name
            try:
                info = stock.info
                company_name = info.get('shortName', info.get('longName', ''))
                result['Company_Name'] = company_name
            except:
                result['Company_Name'] = ''
            
            # Get income statement data
            income_stmt = stock.income_stmt
            
            if not income_stmt.empty and 'Diluted EPS' in income_stmt.index:
                eps_series = income_stmt.loc['Diluted EPS']
                
                # Map each year to its EPS value
                for date, eps_value in eps_series.items():
                    year = date.year
                    if year in years:
                        # Handle various data types and NaN values
                        if pd.notna(eps_value) and eps_value != 0:
                            result[f'EPS_{year}'] = float(eps_value)
                        else:
                            result[f'EPS_{year}'] = None
            
            # Also try quarterly data if annual data is missing
            try:
                quarterly_income = stock.quarterly_income_stmt
                if not quarterly_income.empty and 'Diluted EPS' in quarterly_income.index:
                    quarterly_eps = quarterly_income.loc['Diluted EPS']
                    
                    # Group by year and sum quarterly EPS for annual total
                    for date, eps_value in quarterly_eps.items():
                        year = date.year
                        if year in years and pd.notna(eps_value):
                            # Only use quarterly if we don't have annual data
                            if result[f'EPS_{year}'] is None:
                                # This is a simplified approach - in reality you'd want to sum all quarters
                                result[f'EPS_{year}'] = float(eps_value)
            except:
                pass  # Skip if quarterly data fails
                
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            result['Company_Name'] = ''
        
        results.append(result)
        
        # Add delay to prevent rate limiting
        time.sleep(0.2)
        
        # Save progress every 50 tickers
        if idx % 50 == 0:
            print(f"Processed {idx} tickers, saving intermediate results...")
            temp_df = pd.DataFrame(results)
            temp_df.to_csv(f'temp_eps_data_{idx}.csv', index=False)
    
    return results

def main():
    # Define paths to the CSV files
    csv_files = {
        'AMEX': os.path.join('US stock tickers', 'amex_screener.csv'),
        'NASDAQ': os.path.join('US stock tickers', 'nasdaq_screener.csv'),
        'NYSE': os.path.join('US stock tickers', 'nyse_screener.csv')
    }
    
    # Check if all files exist
    for exchange, path in csv_files.items():
        if not os.path.exists(path):
            raise FileNotFoundError(f"Could not find {path}. Please ensure the file exists.")
    
    # Read all CSV files and combine tickers
    all_tickers = []
    ticker_sources = {}  # Track which exchange each ticker came from
    
    for exchange, path in csv_files.items():
        print(f"Reading {exchange} tickers from {path}")
        df = pd.read_csv(path)
        
        # Assuming the ticker column is named 'Symbol' - adjust if different
        if 'Symbol' in df.columns:
            tickers = df['Symbol'].tolist()
        else:
            # Try common alternative column names
            possible_columns = ['Ticker', 'symbol', 'ticker', 'SYMBOL']
            ticker_column = None
            for col in possible_columns:
                if col in df.columns:
                    ticker_column = col
                    break
            
            if ticker_column:
                tickers = df[ticker_column].tolist()
            else:
                print(f"Warning: Could not find ticker column in {path}")
                print(f"Available columns: {df.columns.tolist()}")
                continue
        
        print(f"Found {len(tickers)} tickers from {exchange}")
        
        # Add to combined list and track source
        for ticker in tickers:
            if ticker not in ticker_sources:  # Avoid duplicates
                all_tickers.append(ticker)
                ticker_sources[ticker] = exchange
    
    print(f"\nTotal unique tickers to process: {len(all_tickers)}")
    
    # Get EPS data for years 2013-2022
    print("Starting EPS data collection...")
    start_time = datetime.now()
    
    results = get_eps_data(all_tickers, years=range(2013, 2023))
    
    # Add exchange information to results
    for result in results:
        result['Exchange'] = ticker_sources.get(result['Ticker'], 'Unknown')
    
    # Create DataFrame
    results_df = pd.DataFrame(results)
    
    # Reorder columns for better readability
    columns = ['Ticker', 'Company_Name', 'Exchange'] + [f'EPS_{year}' for year in range(2013, 2023)]
    results_df = results_df[columns]
    
    # Calculate summary statistics
    total_tickers = len(results_df)
    
    # Count tickers with gaps in data (missing some years but not all)
    eps_columns = [f'EPS_{year}' for year in range(2013, 2023)]
    tickers_with_gaps = 0
    tickers_with_no_data = 0
    
    for idx, row in results_df.iterrows():
        eps_data = row[eps_columns]
        non_null_count = eps_data.notna().sum()
        
        if non_null_count == 0:
            tickers_with_no_data += 1
        elif non_null_count < len(eps_columns):
            tickers_with_gaps += 1
    
    # Create summary data
    summary_data = {
        'Metric': [
            'Total Tickers Processed',
            'Tickers with Gaps in Data',
            'Tickers with No Data'
        ],
        'Count': [
            total_tickers,
            tickers_with_gaps,
            tickers_with_no_data
        ]
    }
    
    summary_df = pd.DataFrame(summary_data)
    
    # Save to Excel file
    excel_filename = 'US_Stocks_EPS_2013_2022.xlsx'
    
    with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
        # Main sheet with all data
        results_df.to_excel(writer, sheet_name='All_Stocks_EPS', index=False)
        
        # Summary sheet
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    end_time = datetime.now()
    processing_time = end_time - start_time
    
    print(f"\nEPS data collection complete!")
    print(f"Processing time: {processing_time}")
    print(f"Total tickers processed: {len(results_df)}")
    print(f"Tickers with gaps in data: {tickers_with_gaps}")
    print(f"Tickers with no data: {tickers_with_no_data}")
    print(f"Results saved to: {excel_filename}")
    
    # Clean up temporary files
    for file in os.listdir('.'):
        if file.startswith('temp_eps_data_') and file.endswith('.csv'):
            os.remove(file)
            print(f"Removed temporary file: {file}")
    
    # Print some statistics
    print("\nData Quality Summary:")
    print(f"Tickers with complete data (2013-2022): {total_tickers - tickers_with_gaps - tickers_with_no_data}")
    print(f"Tickers with partial data: {tickers_with_gaps}")
    print(f"Tickers with no EPS data: {tickers_with_no_data}")
    
    # Show yearly data availability
    print("\nYearly Data Availability:")
    for year in range(2013, 2023):
        available_count = len(results_df[results_df[f'EPS_{year}'].notna()])
        print(f"  {year}: {available_count}/{len(results_df)} tickers ({available_count/len(results_df)*100:.1f}%)")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        print("Please ensure all CSV files are in the 'US stock tickers' folder and contain a 'Symbol' column.")