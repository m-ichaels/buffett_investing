import pandas as pd
import requests
import time
import os
from datetime import datetime
import json  # For JSONDecodeError

# Define User-Agent string (replace with your name and email if necessary)
USER_AGENT = 'Michael maverick575757@gmail.com'

def get_cik_mapping():
    """Fetch the mapping of tickers to CIKs from the SEC."""
    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {'User-Agent': USER_AGENT}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch CIK mapping: {response.status_code}")
        print(response.text)
        return {}
    try:
        data = response.json()
    except json.JSONDecodeError:
        print("Failed to parse JSON from response")
        print(response.text)
        return {}
    cik_mapping = {}
    for item in data.values():
        ticker = item['ticker'].upper()
        cik = str(item['cik_str']).zfill(10)  # Zero-pad to 10 digits
        cik_mapping[ticker] = cik
    return cik_mapping

def get_eps_data(tickers, years=range(2013, 2023)):
    """Fetch diluted EPS data for given tickers from SEC EDGAR across specified years."""
    results = []
    total_tickers = len(tickers)
    
    # Fetch CIK mapping once
    cik_mapping = get_cik_mapping()
    
    # Initialize variable to track the last temporary file
    last_temp_file = None
    
    for idx, ticker in enumerate(tickers, 1):
        # Skip invalid tickers (non-strings like nan)
        if not isinstance(ticker, str):
            print(f"Skipping invalid ticker: {ticker}")
            continue
        
        print(f"Processing {ticker} ({idx}/{total_tickers})")
        
        # Initialize result dictionary
        result = {'Ticker': ticker}
        for year in years:
            result[f'EPS_{year}'] = None
        
        # Get CIK for the ticker
        cik = cik_mapping.get(ticker.upper())
        if not cik:
            print(f"No CIK found for {ticker}")
            result['Company_Name'] = ''
            results.append(result)
            continue
        
        try:
            # Fetch company facts JSON from SEC EDGAR
            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            headers = {'User-Agent': USER_AGENT}
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Failed to fetch data for {ticker} (CIK: {cik})")
                result['Company_Name'] = ''
                results.append(result)
                continue
            data = response.json()
            
            # Extract company name
            result['Company_Name'] = data.get('entityName', '')
            
            # Extract EPS data
            if ('facts' in data and 'us-gaap' in data['facts'] and 
                'EarningsPerShareDiluted' in data['facts']['us-gaap']):
                eps_concept = data['facts']['us-gaap']['EarningsPerShareDiluted']
                if 'units' in eps_concept and 'USD/shares' in eps_concept['units']:
                    eps_entries = eps_concept['units']['USD/shares']
                    # Group EPS by fiscal year, keeping the latest filed entry
                    eps_data = {}
                    for entry in eps_entries:
                        if (entry.get('fp') == 'FY' and 'fy' in entry and 
                            entry['fy'] in years):
                            fy = entry['fy']
                            filed_date = entry['filed']
                            val = entry['val']
                            if fy not in eps_data or filed_date > eps_data[fy]['filed']:
                                eps_data[fy] = {'val': val, 'filed': filed_date}
                    # Populate result with EPS values
                    for year in years:
                        if year in eps_data:
                            result[f'EPS_{year}'] = eps_data[year]['val']
            else:
                print(f"No EPS data found for {ticker}")
            
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            result['Company_Name'] = ''
        
        results.append(result)
        
        # Respect SEC API rate limits (10 requests/sec max, using 5/sec)
        time.sleep(0.2)
        
        # Save intermediate results every 50 tickers
        if idx % 50 == 0:
            # Delete the previous temporary file if it exists
            if last_temp_file is not None and os.path.exists(last_temp_file):
                os.remove(last_temp_file)
                print(f"Deleted previous temporary file: {last_temp_file}")
            
            print(f"Processed {idx} tickers, saving intermediate results...")
            temp_df = pd.DataFrame(results)
            temp_filename = f'temp_eps_data_{idx}.csv'
            temp_df.to_csv(temp_filename, index=False)
            last_temp_file = temp_filename  # Update the last temporary file name
    
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
    ticker_sources = {}  # Track exchange source for each ticker
    
    for exchange, path in csv_files.items():
        print(f"Reading {exchange} tickers from {path}")
        df = pd.read_csv(path)
        
        # Find ticker column
        if 'Symbol' in df.columns:
            tickers = df['Symbol'].tolist()
        else:
            possible_columns = ['Ticker', 'symbol', 'ticker', 'SYMBOL']
            ticker_column = next((col for col in possible_columns if col in df.columns), None)
            if ticker_column:
                tickers = df[ticker_column].tolist()
            else:
                print(f"Warning: No ticker column in {path}")
                print(f"Available columns: {df.columns.tolist()}")
                continue
        
        print(f"Found {len(tickers)} tickers from {exchange}")
        
        # Add tickers and track their exchange, skipping nan values
        for ticker in tickers:
            if pd.notna(ticker) and ticker not in ticker_sources:
                all_tickers.append(ticker)
                ticker_sources[ticker] = exchange
    
    print(f"\nTotal unique tickers to process: {len(all_tickers)}")
    
    # Fetch EPS data for 2013-2022
    print("Starting EPS data collection...")
    start_time = datetime.now()
    
    results = get_eps_data(all_tickers, years=range(2013, 2023))
    
    # Add exchange information
    for result in results:
        result['Exchange'] = ticker_sources.get(result['Ticker'], 'Unknown')
    
    # Create DataFrame
    results_df = pd.DataFrame(results)
    columns = ['Ticker', 'Company_Name', 'Exchange'] + [f'EPS_{year}' for year in range(2013, 2023)]
    results_df = results_df[columns]
    
    # Calculate summary statistics
    total_tickers = len(results_df)
    eps_columns = [f'EPS_{year}' for year in range(2013, 2023)]
    tickers_with_gaps = 0
    tickers_with_no_data = 0
    
    for _, row in results_df.iterrows():
        eps_data = row[eps_columns]
        non_null_count = eps_data.notna().sum()
        if non_null_count == 0:
            tickers_with_no_data += 1
        elif non_null_count < len(eps_columns):
            tickers_with_gaps += 1
    
    # Create summary DataFrame
    summary_data = {
        'Metric': ['Total Tickers Processed', 'Tickers with Gaps in Data', 'Tickers with No Data'],
        'Count': [total_tickers, tickers_with_gaps, tickers_with_no_data]
    }
    summary_df = pd.DataFrame(summary_data)
    
    # Save to Excel
    excel_filename = 'US_Stocks_EPS_2013_2022.xlsx'
    with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
        results_df.to_excel(writer, sheet_name='All_Stocks_EPS', index=False)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    end_time = datetime.now()
    processing_time = end_time - start_time
    
    # Print completion details
    print(f"\nEPS data collection complete!")
    print(f"Processing time: {processing_time}")
    print(f"Total tickers processed: {total_tickers}")
    print(f"Tickers with gaps in data: {tickers_with_gaps}")
    print(f"Tickers with no data: {tickers_with_no_data}")
    print(f"Results saved to: {excel_filename}")
    
    # Clean up temporary files
    for file in os.listdir('.'):
        if file.startswith('temp_eps_data_') and file.endswith('.csv'):
            os.remove(file)
            print(f"Removed temporary file: {file}")
    
    # Print data quality summary
    print("\nData Quality Summary:")
    print(f"Tickers with complete data (2013-2022): {total_tickers - tickers_with_gaps - tickers_with_no_data}")
    print(f"Tickers with partial data: {tickers_with_gaps}")
    print(f"Tickers with no EPS data: {tickers_with_no_data}")
    
    # Show yearly data availability
    print("\nYearly Data Availability:")
    for year in range(2013, 2023):
        available_count = len(results_df[results_df[f'EPS_{year}'].notna()])
        print(f"  {year}: {available_count}/{total_tickers} tickers ({available_count/total_tickers*100:.1f}%)")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        print("Please ensure all CSV files are in the 'US stock tickers' folder and contain a ticker column.")