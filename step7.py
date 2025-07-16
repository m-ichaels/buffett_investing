import pandas as pd
import requests
import time
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np
import os

USER_AGENT = 'Michael maverick575757@gmail.com'  # Replace with your contact info for SEC EDGAR API

def get_cik_mapping():
    """Fetch the mapping of stock tickers to CIK numbers from SEC."""
    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {'User-Agent': USER_AGENT}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch CIK mapping: {response.status_code}")
        return {}
    data = response.json()
    return {item['ticker'].upper(): str(item['cik_str']).zfill(10) for item in data.values()}

def get_company_facts(cik):
    """Fetch company financial facts JSON from SEC EDGAR API."""
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    headers = {'User-Agent': USER_AGENT}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch company facts for CIK {cik}: {response.status_code}")
        return None
    return response.json()

def get_latest_value(facts, concepts, fy):
    """
    Try multiple concept names to find the data.
    Returns the value if found, None otherwise.
    """
    if 'facts' not in facts or 'us-gaap' not in facts['facts']:
        return None
    
    us_gaap_data = facts['facts']['us-gaap']
    
    for concept in concepts:
        if concept not in us_gaap_data:
            continue
        
        concept_data = us_gaap_data[concept]
        if 'units' not in concept_data or 'USD' not in concept_data['units']:
            continue
        
        # Filter for 10-K or 10-K/A filings in the specified fiscal year
        entries = [e for e in concept_data['units']['USD'] 
                  if e.get('form') in ['10-K', '10-K/A'] and e.get('fy') == fy]
        
        if not entries:
            # If no 10-K found, try 10-Q forms for that fiscal year
            entries = [e for e in concept_data['units']['USD'] 
                      if e.get('form') in ['10-Q'] and e.get('fy') == fy and e.get('fp') == 'Q4']
        
        if not entries:
            continue
        
        # Select the latest entry based on filing date
        latest_entry = max(entries, key=lambda x: x['filed'])
        return latest_entry['val']
    
    return None

def get_shares_outstanding(facts, concepts, fy):
    """
    Get shares outstanding for a given fiscal year.
    Returns shares count if found, None otherwise.
    """
    if 'facts' not in facts or 'us-gaap' not in facts['facts']:
        return None
    
    us_gaap_data = facts['facts']['us-gaap']
    
    for concept in concepts:
        if concept not in us_gaap_data:
            continue
        
        concept_data = us_gaap_data[concept]
        if 'units' not in concept_data or 'shares' not in concept_data['units']:
            continue
        
        # Filter for 10-K or 10-K/A filings in the specified fiscal year
        entries = [e for e in concept_data['units']['shares'] 
                  if e.get('form') in ['10-K', '10-K/A'] and e.get('fy') == fy]
        
        if not entries:
            # If no 10-K found, try 10-Q forms for that fiscal year
            entries = [e for e in concept_data['units']['shares'] 
                      if e.get('form') in ['10-Q'] and e.get('fy') == fy and e.get('fp') == 'Q4']
        
        if not entries:
            continue
        
        # Select the latest entry based on filing date
        latest_entry = max(entries, key=lambda x: x['filed'])
        return latest_entry['val']
    
    return None

def get_stock_price_dec_2022(ticker):
    """
    Get stock price at the end of December 2022 using yfinance.
    Returns the closing price on the last trading day of December 2022.
    """
    try:
        # Get stock data for the last few days of December 2022
        stock = yf.Ticker(ticker)
        
        # Get data for the last week of December 2022
        start_date = "2022-12-26"
        end_date = "2023-01-03"
        
        hist = stock.history(start=start_date, end=end_date)
        
        if hist.empty:
            print(f"  No price data found for {ticker} in late December 2022")
            return None
        
        # Get the last available price in December 2022
        # Filter for dates in December 2022
        dec_2022_data = hist[hist.index.strftime('%Y-%m') == '2022-12']
        
        if not dec_2022_data.empty:
            price = dec_2022_data['Close'].iloc[-1]
            date = dec_2022_data.index[-1].strftime('%Y-%m-%d')
            print(f"  Price on {date}: ${price:.2f}")
            return price
        else:
            # If no December data, get the closest available price
            price = hist['Close'].iloc[0]
            date = hist.index[0].strftime('%Y-%m-%d')
            print(f"  Closest price on {date}: ${price:.2f}")
            return price
            
    except Exception as e:
        print(f"  Error fetching price for {ticker}: {e}")
        return None

def get_10_year_treasury_yield_dec_2022():
    """
    Get the 10-year Treasury yield for end of December 2022.
    Using yfinance to get the yield.
    """
    try:
        # Get 10-year Treasury yield (^TNX)
        treasury = yf.Ticker("^TNX")
        
        # Get data for late December 2022
        start_date = "2022-12-26"
        end_date = "2023-01-03"
        
        hist = treasury.history(start=start_date, end=end_date)
        
        if hist.empty:
            print("Could not fetch 10-year Treasury yield data")
            return None
        
        # Get the last available yield in December 2022
        dec_2022_data = hist[hist.index.strftime('%Y-%m') == '2022-12']
        
        if not dec_2022_data.empty:
            yield_value = dec_2022_data['Close'].iloc[-1] / 100  # Convert percentage to decimal
            date = dec_2022_data.index[-1].strftime('%Y-%m-%d')
            print(f"10-Year Treasury Yield on {date}: {yield_value:.2%}")
            return yield_value
        else:
            # If no December data, get the closest available yield
            yield_value = hist['Close'].iloc[0] / 100  # Convert percentage to decimal
            date = hist.index[0].strftime('%Y-%m-%d')
            print(f"10-Year Treasury Yield (closest) on {date}: {yield_value:.2%}")
            return yield_value
            
    except Exception as e:
        print(f"Error fetching 10-year Treasury yield: {e}")
        # Fallback to approximate yield for end of December 2022
        print("Using approximate 10-year Treasury yield for December 2022: 3.88%")
        return 0.0388

def calculate_earnings_yield(eps, stock_price):
    """
    Calculate earnings yield (EPS / Stock Price).
    Returns the earnings yield as a decimal.
    """
    if eps is None or stock_price is None or stock_price <= 0:
        return None
    
    return eps / stock_price

def main():
    # Load tickers from the RORE filtered results in the Excel file
    file_path = os.path.join('Results', '2022.xlsx')
    try:
        df = pd.read_excel(file_path, sheet_name='RORE_Filtered_Stocks')
        if 'Ticker' not in df.columns:
            raise ValueError("RORE_Filtered_Stocks worksheet must contain a 'Ticker' column")
        tickers = df['Ticker'].tolist()
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        return
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return

    # Get 10-year Treasury yield for December 2022
    treasury_yield = get_10_year_treasury_yield_dec_2022()
    if treasury_yield is None:
        print("Could not fetch Treasury yield. Exiting.")
        return

    cik_mapping = get_cik_mapping()
    results = []

    # Alternative concept names for financial metrics
    net_income_concepts = [
        'NetIncomeLoss',
        'NetIncomeLossAvailableToCommonStockholdersBasic',
        'NetIncomeLossAttributableToParent',
        'NetIncome'
    ]
    
    shares_outstanding_concepts = [
        'CommonStockSharesOutstanding',
        'CommonStockSharesIssued',
        'WeightedAverageNumberOfSharesOutstandingBasic',
        'WeightedAverageNumberOfDilutedSharesOutstanding'
    ]

    for idx, ticker in enumerate(tickers, 1):
        print(f"Processing {ticker} ({idx}/{len(tickers)})")
        cik = cik_mapping.get(ticker.upper())
        if not cik:
            print(f"No CIK found for {ticker}")
            continue

        facts = get_company_facts(cik)
        if not facts:
            continue

        # Get 2022 financial data
        fiscal_year = 2022
        
        # Get net income for 2022
        net_income = get_latest_value(facts, net_income_concepts, fiscal_year)
        
        # Get shares outstanding for 2022
        shares_outstanding = get_shares_outstanding(facts, shares_outstanding_concepts, fiscal_year)
        
        # Get stock price for end of December 2022
        stock_price = get_stock_price_dec_2022(ticker)
        
        if net_income is None:
            print(f"  Could not find net income for {ticker} in 2022")
            continue
            
        if shares_outstanding is None:
            print(f"  Could not find shares outstanding for {ticker} in 2022")
            continue
            
        if stock_price is None:
            print(f"  Could not find stock price for {ticker} in December 2022")
            continue
        
        # Calculate EPS
        eps = net_income / shares_outstanding
        
        # Calculate earnings yield
        earnings_yield = calculate_earnings_yield(eps, stock_price)
        
        if earnings_yield is None:
            print(f"  Could not calculate earnings yield for {ticker}")
            continue
        
        # Check if earnings yield is higher than Treasury yield
        beats_treasury = earnings_yield > treasury_yield
        
        print(f"  Net Income: ${net_income:,.0f}")
        print(f"  Shares Outstanding: {shares_outstanding:,.0f}")
        print(f"  EPS: ${eps:.2f}")
        print(f"  Earnings Yield: {earnings_yield:.2%}")
        print(f"  Beats Treasury ({treasury_yield:.2%}): {beats_treasury}")
        
        if beats_treasury:
            result = {
                'Ticker': ticker,
                'Net_Income_2022': net_income,
                'Shares_Outstanding_2022': shares_outstanding,
                'EPS_2022': eps,
                'Stock_Price_Dec_2022': stock_price,
                'Earnings_Yield': earnings_yield,
                'Treasury_Yield_Dec_2022': treasury_yield,
                'Beats_Treasury': beats_treasury,
                'Yield_Advantage': earnings_yield - treasury_yield
            }
            
            results.append(result)
            print(f"  ✓ {ticker} qualifies with {earnings_yield:.2%} earnings yield vs {treasury_yield:.2%} Treasury")
        else:
            print(f"  ✗ {ticker} does not qualify - earnings yield {earnings_yield:.2%} < Treasury {treasury_yield:.2%}")
        
        time.sleep(0.1)  # Small delay to avoid overwhelming APIs

    if results:
        results_df = pd.DataFrame(results)
        
        # Sort by earnings yield (highest first)
        results_df = results_df.sort_values('Earnings_Yield', ascending=False)
        
        # Save to Excel file as new worksheet
        with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            results_df.to_excel(writer, sheet_name='Earnings_Yield_Filtered_Stocks', index=False)
        
        print(f"\nEarnings yield filtering complete! {len(results)} stocks beat the Treasury yield.")
        print(f"Results saved to '{file_path}' in 'Earnings_Yield_Filtered_Stocks' worksheet")
        
        # Print summary
        print("\nSummary of qualifying stocks (sorted by earnings yield):")
        for _, row in results_df.iterrows():
            advantage = row['Yield_Advantage']
            print(f"{row['Ticker']}: {row['Earnings_Yield']:.2%} earnings yield "
                  f"(+{advantage:.2%} vs Treasury), EPS: ${row['EPS_2022']:.2f}, "
                  f"Price: ${row['Stock_Price_Dec_2022']:.2f}")
        
        # Print additional insights
        avg_earnings_yield = results_df['Earnings_Yield'].mean()
        max_earnings_yield = results_df['Earnings_Yield'].max()
        min_earnings_yield = results_df['Earnings_Yield'].min()
        avg_advantage = results_df['Yield_Advantage'].mean()
        
        print(f"\nAdditional insights:")
        print(f"- Average earnings yield: {avg_earnings_yield:.2%}")
        print(f"- Earnings yield range: {min_earnings_yield:.2%} to {max_earnings_yield:.2%}")
        print(f"- Average advantage over Treasury: {avg_advantage:.2%}")
        print(f"- 10-Year Treasury yield (Dec 2022): {treasury_yield:.2%}")
        
        # Show top performers
        top_3 = results_df.head(3)
        print(f"\nTop 3 performers by earnings yield:")
        for i, (_, row) in enumerate(top_3.iterrows(), 1):
            print(f"{i}. {row['Ticker']}: {row['Earnings_Yield']:.2%}")
        
    else:
        print("No stocks beat the 10-year Treasury yield.")

if __name__ == "__main__":
    main()