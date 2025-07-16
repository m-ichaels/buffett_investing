import pandas as pd
import requests
import time
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
    # Access the nested facts structure
    if 'facts' not in facts or 'us-gaap' not in facts['facts']:
        return None
    
    us_gaap_data = facts['facts']['us-gaap']
    
    for concept in concepts:
        # Check if the concept exists in the us-gaap taxonomy
        if concept not in us_gaap_data:
            continue
        
        concept_data = us_gaap_data[concept]
        if 'units' not in concept_data or 'USD' not in concept_data['units']:
            continue
        
        # Filter for 10-K or 10-K/A filings in the specified fiscal year
        # Also include 10-Q forms as a fallback
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

def calculate_rotc(net_income, total_debt, equity):
    """
    Calculate Return on Total Capital (ROTC)
    ROTC = Net Income / (Total Debt + Stockholders' Equity)
    """
    if total_debt is None or equity is None or net_income is None:
        return None
    
    total_capital = total_debt + equity
    if total_capital <= 0:
        return None
    
    return net_income / total_capital

def main():
    # Load tickers from the ROE filtered results in the Excel file
    file_path = os.path.join('Results', '2022.xlsx')
    try:
        df = pd.read_excel(file_path, sheet_name='ROE_Filtered_Stocks')
        if 'Ticker' not in df.columns:
            raise ValueError("ROE_Filtered_Stocks worksheet must contain a 'Ticker' column")
        tickers = df['Ticker'].tolist()
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        return
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return

    cik_mapping = get_cik_mapping()
    results = []

    # Alternative concept names for financial metrics
    net_income_concepts = ['NetIncomeLoss', 'ProfitLoss', 'NetIncomeLossAvailableToCommonStockholdersBasic']
    equity_concepts = ['StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest']
    
    # Total debt concepts - trying multiple variations
    total_debt_concepts = [
        'DebtCurrent',
        'DebtNoncurrent', 
        'LongTermDebt',
        'ShortTermBorrowings',
        'LongTermDebtCurrent',
        'LongTermDebtNoncurrent',
        'DebtAndCapitalLeaseObligations',
        'DebtAndCapitalLeaseObligationsCurrent',
        'DebtAndCapitalLeaseObligationsNoncurrent'
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

        # Get available fiscal years for this company
        if 'facts' not in facts or 'us-gaap' not in facts['facts']:
            print(f"No us-gaap data found for {ticker}")
            continue
            
        us_gaap_data = facts['facts']['us-gaap']
        
        # Find available fiscal years from NetIncomeLoss data
        available_years = set()
        if 'NetIncomeLoss' in us_gaap_data and 'units' in us_gaap_data['NetIncomeLoss'] and 'USD' in us_gaap_data['NetIncomeLoss']['units']:
            for entry in us_gaap_data['NetIncomeLoss']['units']['USD']:
                if entry.get('form') in ['10-K', '10-K/A']:
                    available_years.add(entry.get('fy'))
        
        available_years = sorted([year for year in available_years if year and 2013 <= year <= 2022])
        print(f"Available fiscal years for {ticker}: {available_years}")
        
        if len(available_years) < 7:
            print(f"{ticker} has insufficient fiscal years available ({len(available_years)} years, need at least 7)")
            continue

        rotcs = []
        years_with_data = []
        
        # Calculate ROTC for each available year
        for year in available_years:
            net_income = get_latest_value(facts, net_income_concepts, year)
            equity = get_latest_value(facts, equity_concepts, year)
            
            # Calculate total debt by summing available debt components
            total_debt = 0
            debt_found = False
            
            for debt_concept in total_debt_concepts:
                debt_value = get_latest_value(facts, [debt_concept], year)
                if debt_value is not None:
                    total_debt += debt_value
                    debt_found = True
            
            # If no debt components found, assume zero debt
            if not debt_found:
                total_debt = 0
            
            # Calculate ROTC
            rotc = calculate_rotc(net_income, total_debt, equity)
            
            if rotc is not None:
                rotcs.append(rotc)
                years_with_data.append(year)
                print(f"  {year}: ROTC = {rotc:.2%}")
            else:
                print(f"  {year}: Missing or invalid data for ROTC calculation")
        
        # Require at least 7 years of data (same as ROE filter)
        if len(rotcs) >= 7:
            avg_rotc = sum(rotcs) / len(rotcs)
            if avg_rotc >= 0.12:  # 12% threshold
                result = {
                    'Ticker': ticker, 
                    'Average_ROTC': avg_rotc,
                    'Years_of_Data': len(rotcs),
                    'Data_Years': ','.join(map(str, years_with_data))
                }
                
                # Add individual year ROTC data
                for i, year in enumerate(years_with_data):
                    result[f'ROTC_{year}'] = rotcs[i]
                
                results.append(result)
                print(f"{ticker} qualifies with average ROTC {avg_rotc:.2%} over {len(rotcs)} years")
            else:
                print(f"{ticker} has average ROTC {avg_rotc:.2%} < 12% over {len(rotcs)} years")
        else:
            print(f"{ticker} has insufficient data ({len(rotcs)} years, need at least 7)")
        
        time.sleep(0.2)  # Respect SEC EDGAR API rate limit of 10 requests per second

    if results:
        results_df = pd.DataFrame(results)
        
        # Reorder columns to put basic info first
        basic_cols = ['Ticker', 'Average_ROTC', 'Years_of_Data', 'Data_Years']
        rotc_cols = [col for col in results_df.columns if col.startswith('ROTC_')]
        rotc_cols.sort()  # Sort ROTC columns by year
        
        results_df = results_df[basic_cols + rotc_cols]
        
        # Save to Excel file as new worksheet
        with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            results_df.to_excel(writer, sheet_name='ROTC_Filtered_Stocks', index=False)
        
        print(f"\nROTC filtering complete! {len(results)} stocks meet the criterion.")
        print(f"Results saved to '{file_path}' in 'ROTC_Filtered_Stocks' worksheet")
        
        # Print summary
        print("\nSummary of qualifying stocks:")
        for _, row in results_df.iterrows():
            print(f"{row['Ticker']}: {row['Average_ROTC']:.2%} ROTC over {row['Years_of_Data']} years")
    else:
        print("No stocks meet the ROTC criterion.")

if __name__ == "__main__":
    main()