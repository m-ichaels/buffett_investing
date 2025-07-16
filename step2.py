import requests
import pandas as pd
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Headers for SEC API requests
headers = {
    'User-Agent': 'Michael maverick575757@gmail.com',  # Replace with your name and email
    'Accept': 'application/json'
}

def get_cik_map():
    """Fetch CIK mapping from SEC."""
    url = 'https://www.sec.gov/files/company_tickers.json'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return {item['ticker'].upper(): str(item['cik_str']).zfill(10) for item in data.values()}

def get_debt_and_earnings(ticker, cik):
    """Fetch long-term debt and net income for fiscal year 2022."""
    url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Extract facts
        facts = data.get('facts', {}).get('us-gaap', {})
        debt_data = facts.get('LongTermDebtNoncurrent', {}).get('units', {}).get('USD', [])
        income_data = facts.get('NetIncomeLoss', {}).get('units', {}).get('USD', [])
        
        # Filter for 2022 fiscal year
        debt_2022 = [entry for entry in debt_data if entry.get('fy') == 2022 and entry.get('fp') == 'FY']
        income_2022 = [entry for entry in income_data if entry.get('fy') == 2022 and entry.get('fp') == 'FY']
        
        if not debt_2022 or not income_2022:
            logging.warning(f"No 2022 data for {ticker}")
            return None, None
        
        # Get latest filed entry for 2022
        debt_entry = max(debt_2022, key=lambda x: x.get('filed'))
        income_entry = max(income_2022, key=lambda x: x.get('filed'))
        
        debt = debt_entry.get('val')
        income = income_entry.get('val')
        
        if income <= 0:
            logging.warning(f"Net income zero or negative for {ticker} in 2022: {income}")
            return None, None
            
        return debt, income
    
    except requests.RequestException as e:
        logging.error(f"Error fetching data for {ticker}: {e}")
        return None, None

def main():
    # Load tickers
    df = pd.read_csv('qualifying_stocks.csv')
    tickers = df['Ticker'].str.upper().tolist()
    
    # Get CIK mapping
    cik_map = get_cik_map()
    
    results = []
    for ticker in tickers:
        logging.info(f"Processing {ticker}")
        cik = cik_map.get(ticker)
        if not cik:
            logging.warning(f"No CIK found for {ticker}")
            continue
        
        debt, income = get_debt_and_earnings(ticker, cik)
        if debt is None or income is None:
            continue
        
        debt_to_earnings = debt / income
        if debt_to_earnings <= 5:
            results.append({
                'Ticker': ticker,
                'LongTermDebt_2022': debt,
                'NetIncome_2022': income,
                'FiscalYear': 2022
            })
            logging.info(f"{ticker} meets criterion: Debt/Income = {debt_to_earnings:.2f}")
        
        time.sleep(0.2)  # Respect SEC rate limits
    
    # Save results
    if results:
        result_df = pd.DataFrame(results)
        result_df.to_csv('debt_filtered_stocks_2022.csv', index=False)
        logging.info(f"Saved {len(results)} tickers to debt_filtered_stocks_2022.csv")
    else:
        logging.info("No tickers met the criterion")

if __name__ == "__main__":
    main()