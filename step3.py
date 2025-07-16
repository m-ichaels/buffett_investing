import pandas as pd
import requests
import time

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

def main():
    # Load tickers from the previous filter step
    input_file = 'debt_filtered_stocks_2022.csv'
    try:
        df = pd.read_csv(input_file)
        if 'Ticker' not in df.columns:
            raise ValueError("Input CSV must contain a 'Ticker' column")
        tickers = df['Ticker'].tolist()
    except FileNotFoundError:
        print(f"Error: {input_file} not found.")
        return
    except Exception as e:
        print(f"Error reading {input_file}: {e}")
        return

    cik_mapping = get_cik_mapping()
    results = []

    # Alternative concept names for net income and equity
    net_income_concepts = ['NetIncomeLoss', 'ProfitLoss', 'NetIncomeLossAvailableToCommonStockholdersBasic']
    equity_concepts = ['StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest']

    for idx, ticker in enumerate(tickers, 1):
        print(f"Processing {ticker} ({idx}/{len(tickers)})")
        cik = cik_mapping.get(ticker.upper())
        if not cik:
            print(f"No CIK found for {ticker}")
            continue

        facts = get_company_facts(cik)
        if not facts:
            continue

        # Get available fiscal years for this company to determine the range
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

        roes = []
        years_with_data = []
        
        # Use the available fiscal years instead of a fixed range
        for year in available_years:
            net_income = get_latest_value(facts, net_income_concepts, year)
            equity = get_latest_value(facts, equity_concepts, year)
            
            if net_income is not None and equity is not None and equity > 0:
                roe = net_income / equity
                roes.append(roe)
                years_with_data.append(year)
            else:
                print(f"Missing or invalid data for {ticker} in fiscal year {year}")
        
        # Require at least 7 years of data (instead of all 10)
        if len(roes) >= 7:
            avg_roe = sum(roes) / len(roes)
            if avg_roe >= 0.15:
                result = {
                    'Ticker': ticker, 
                    'Average_ROE': avg_roe,
                    'Years_of_Data': len(roes),
                    'Data_Years': ','.join(map(str, years_with_data))
                }
                
                # Add individual year ROE data
                for i, year in enumerate(years_with_data):
                    result[f'ROE_{year}'] = roes[i]
                
                results.append(result)
                print(f"{ticker} qualifies with average ROE {avg_roe:.2%} over {len(roes)} years")
            else:
                print(f"{ticker} has average ROE {avg_roe:.2%} < 15% over {len(roes)} years")
        else:
            print(f"{ticker} has insufficient data ({len(roes)} years, need at least 7)")
        
        time.sleep(0.2)  # Respect SEC EDGAR API rate limit of 10 requests per second

    if results:
        results_df = pd.DataFrame(results)
        
        # Reorder columns to put basic info first
        basic_cols = ['Ticker', 'Average_ROE', 'Years_of_Data', 'Data_Years']
        roe_cols = [col for col in results_df.columns if col.startswith('ROE_')]
        roe_cols.sort()  # Sort ROE columns by year
        
        results_df = results_df[basic_cols + roe_cols]
        
        output_file = 'roe_filtered_stocks.csv'
        results_df.to_csv(output_file, index=False)
        print(f"\nROE filtering complete! {len(results)} stocks meet the criterion.")
        print(f"Results saved to {output_file}")
        
        # Print summary
        print("\nSummary of qualifying stocks:")
        for _, row in results_df.iterrows():
            print(f"{row['Ticker']}: {row['Average_ROE']:.2%} ROE over {row['Years_of_Data']} years")
    else:
        print("No stocks meet the ROE criterion.")

if __name__ == "__main__":
    main()