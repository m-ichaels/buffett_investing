import pandas as pd
import requests
import time
import yfinance as yf
from statistics import mean, median
import numpy as np
from math import pow

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
    """Try multiple concept names to find the data."""
    if 'facts' not in facts or 'us-gaap' not in facts['facts']:
        return None
    
    us_gaap_data = facts['facts']['us-gaap']
    
    for concept in concepts:
        if concept not in us_gaap_data:
            continue
        
        concept_data = us_gaap_data[concept]
        if 'units' not in concept_data or 'USD' not in concept_data['units']:
            continue
        
        entries = [e for e in concept_data['units']['USD'] 
                  if e.get('form') in ['10-K', '10-K/A'] and e.get('fy') == fy]
        
        if not entries:
            entries = [e for e in concept_data['units']['USD'] 
                      if e.get('form') in ['10-Q'] and e.get('fy') == fy and e.get('fp') == 'Q4']
        
        if not entries:
            continue
        
        latest_entry = max(entries, key=lambda x: x['filed'])
        return latest_entry['val']
    
    return None

def get_shares_outstanding(facts, concepts, fy):
    """Get shares outstanding for a given fiscal year."""
    if 'facts' not in facts or 'us-gaap' not in facts['facts']:
        return None
    
    us_gaap_data = facts['facts']['us-gaap']
    
    for concept in concepts:
        if concept not in us_gaap_data:
            continue
        
        concept_data = us_gaap_data[concept]
        if 'units' not in concept_data or 'shares' not in concept_data['units']:
            continue
        
        entries = [e for e in concept_data['units']['shares'] 
                  if e.get('form') in ['10-K', '10-K/A'] and e.get('fy') == fy]
        
        if not entries:
            entries = [e for e in concept_data['units']['shares'] 
                      if e.get('form') in ['10-Q'] and e.get('fy') == fy and e.get('fp') == 'Q4']
        
        if not entries:
            continue
        
        latest_entry = max(entries, key=lambda x: x['filed'])
        return latest_entry['val']
    
    return None

def get_stock_price_dec_2022(ticker):
    """Get stock price at the end of December 2022."""
    try:
        stock = yf.Ticker(ticker)
        start_date = "2022-12-26"
        end_date = "2023-01-03"
        
        hist = stock.history(start=start_date, end=end_date)
        
        if hist.empty:
            return None
        
        dec_2022_data = hist[hist.index.strftime('%Y-%m') == '2022-12']
        
        if not dec_2022_data.empty:
            return dec_2022_data['Close'].iloc[-1]
        else:
            return hist['Close'].iloc[0]
            
    except Exception as e:
        print(f"  Error fetching price for {ticker}: {e}")
        return None

def calculate_eps_growth_rates(eps_data):
    """Calculate year-over-year EPS growth rates."""
    if len(eps_data) < 2:
        return []
    
    growth_rates = []
    sorted_years = sorted(eps_data.keys())
    
    for i in range(1, len(sorted_years)):
        prev_year = sorted_years[i-1]
        curr_year = sorted_years[i]
        
        prev_eps = eps_data[prev_year]
        curr_eps = eps_data[curr_year]
        
        if prev_eps > 0 and curr_eps > 0:
            growth_rate = (curr_eps - prev_eps) / prev_eps
            growth_rates.append(growth_rate)
            print(f"    {prev_year} to {curr_year}: {growth_rate:.1%}")
        elif prev_eps <= 0 and curr_eps > 0:
            # Transition from loss to profit - use a conservative growth rate
            growth_rates.append(0.50)  # 50% growth assumption
            print(f"    {prev_year} to {curr_year}: Loss to profit (assumed 50% growth)")
        elif prev_eps > 0 and curr_eps <= 0:
            # Transition from profit to loss - exclude this data point
            print(f"    {prev_year} to {curr_year}: Profit to loss (excluded)")
            continue
        else:
            # Both years have losses - exclude this data point
            print(f"    {prev_year} to {curr_year}: Both years losses (excluded)")
            continue
    
    return growth_rates

def estimate_future_eps_growth(growth_rates, method='conservative'):
    """
    Estimate future EPS growth rate based on historical data.
    
    Methods:
    - conservative: Use the median growth rate, capped at reasonable levels
    - average: Use the mean growth rate
    - trend: Use a weighted average favoring recent years
    """
    if not growth_rates:
        return 0.05  # Default 5% growth if no data
    
    if method == 'conservative':
        # Use median to avoid outliers, cap at 20%
        base_growth = median(growth_rates)
        return min(max(base_growth, 0.0), 0.20)
    
    elif method == 'average':
        # Use mean, cap at 25%
        base_growth = mean(growth_rates)
        return min(max(base_growth, 0.0), 0.25)
    
    elif method == 'trend':
        # Weight recent years more heavily
        if len(growth_rates) >= 3:
            weights = [1, 2, 3]  # Recent years get higher weights
            weighted_growth = sum(r * w for r, w in zip(growth_rates[-3:], weights)) / sum(weights)
        else:
            weighted_growth = mean(growth_rates)
        return min(max(weighted_growth, 0.0), 0.25)
    
    return 0.05

def calculate_payout_ratio(dividends_paid, net_income):
    """Calculate dividend payout ratio."""
    if dividends_paid is None or net_income is None or net_income <= 0:
        return 0.0  # Assume no dividends if data is missing
    return abs(dividends_paid) / net_income

def estimate_future_pe_ratio(historical_pe_ratios, projected_growth_rate):
    """
    Estimate future P/E ratio based on historical P/E and growth prospects.
    """
    if not historical_pe_ratios:
        # Use growth-adjusted market P/E if no historical data
        if projected_growth_rate > 0.15:
            return 15.0
        elif projected_growth_rate > 0.10:
            return 12.0
        elif projected_growth_rate > 0.05:
            return 10.0
        else:
            return 8.0
    
    avg_historical_pe = mean([pe for pe in historical_pe_ratios if pe > 0])
    
    # Adjust P/E based on growth prospects
    if projected_growth_rate > 0.15:  # High growth
        future_pe = min(avg_historical_pe * 1.1, 25.0)  # Slight premium, cap at 25
    elif projected_growth_rate > 0.10:  # Moderate growth
        future_pe = avg_historical_pe
    elif projected_growth_rate > 0.05:  # Low growth
        future_pe = avg_historical_pe * 0.9
    else:  # Very low growth
        future_pe = avg_historical_pe * 0.8
    
    # Ensure reasonable bounds
    return max(min(future_pe, 30.0), 6.0)

def calculate_eps_projected_return(ticker, current_price, eps_data, pe_data, 
                                 payout_ratio_avg, projected_growth_rate, years=10):
    """
    Calculate projected return using EPS Growth Method.
    
    Steps:
    1. Project future EPS using growth rate
    2. Estimate future P/E ratio
    3. Calculate future stock price
    4. Estimate dividend payments over the period
    5. Calculate total return
    """
    
    # Get current EPS (most recent year)
    current_year = max(eps_data.keys())
    current_eps = eps_data[current_year]
    
    if current_eps <= 0:
        return None
    
    # Step 1: Project future EPS
    future_eps = current_eps * ((1 + projected_growth_rate) ** years)
    
    # Step 2: Estimate future P/E ratio
    future_pe = estimate_future_pe_ratio(pe_data, projected_growth_rate)
    
    # Step 3: Calculate future stock price
    future_stock_price = future_eps * future_pe
    
    # Step 4: Calculate dividends over the period
    current_dividend_per_share = current_eps * payout_ratio_avg
    
    # Total dividends over the period (growing annuity)
    if projected_growth_rate > 0:
        total_dividends = current_dividend_per_share * (
            ((1 + projected_growth_rate) ** years - 1) / projected_growth_rate
        )
    else:
        total_dividends = current_dividend_per_share * years
    
    # Step 5: Calculate total return
    total_future_value = future_stock_price + total_dividends
    
    if total_future_value <= current_price:
        return None
    
    total_return = (total_future_value / current_price) - 1
    annualized_return = (total_future_value / current_price) ** (1/years) - 1
    
    return {
        'current_eps': current_eps,
        'projected_growth_rate': projected_growth_rate,
        'future_eps': future_eps,
        'future_pe': future_pe,
        'future_stock_price': future_stock_price,
        'current_dividend_per_share': current_dividend_per_share,
        'total_dividends': total_dividends,
        'total_future_value': total_future_value,
        'total_return': total_return,
        'annualized_return': annualized_return
    }

def main():
    # Load tickers from the ROE projection filtered results
    input_file = 'roe_projection_filtered_stocks.csv'
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
    
    dividends_concepts = [
        'PaymentsOfDividendsCommonStock',
        'PaymentsOfDividends',
        'DividendsPaid',
        'PaymentsOfDividendsAndDividendEquivalentsOnCommonStockAndPreferredStock'
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

        # Get current stock price (Dec 2022)
        current_price = get_stock_price_dec_2022(ticker)
        if current_price is None:
            print(f"  Could not get stock price for {ticker}")
            continue

        # Collect historical EPS data
        years_to_analyze = [2018, 2019, 2020, 2021, 2022]  # 5 years for better trend analysis
        eps_data = {}
        pe_data = []
        payout_ratios = []
        
        print(f"  Analyzing EPS history:")
        
        for year in years_to_analyze:
            # Get financial data for each year
            net_income = get_latest_value(facts, net_income_concepts, year)
            shares_outstanding = get_shares_outstanding(facts, shares_outstanding_concepts, year)
            dividends_paid = get_latest_value(facts, dividends_concepts, year)
            
            if net_income is not None and shares_outstanding is not None and shares_outstanding > 0:
                eps = net_income / shares_outstanding
                eps_data[year] = eps
                
                # Calculate P/E ratio for this year (using 2022 price as approximation)
                if eps > 0:
                    pe_ratio = current_price / eps
                    pe_data.append(pe_ratio)
                
                # Calculate payout ratio
                payout_ratio = calculate_payout_ratio(dividends_paid, net_income)
                payout_ratios.append(payout_ratio)
                
                print(f"    {year}: EPS = ${eps:.2f}, P/E = {pe_ratio:.1f}" if eps > 0 else f"    {year}: EPS = ${eps:.2f} (loss)")
        
        # Check if we have enough EPS data
        if len(eps_data) < 3:
            print(f"  Insufficient EPS data for {ticker} (need at least 3 years)")
            continue
        
        # Calculate EPS growth rates
        print(f"  EPS growth rates:")
        growth_rates = calculate_eps_growth_rates(eps_data)
        
        if not growth_rates:
            print(f"  No valid growth rates calculated for {ticker}")
            continue
        
        # Estimate future EPS growth rate using conservative method
        projected_growth_rate = estimate_future_eps_growth(growth_rates, method='conservative')
        
        # Calculate average payout ratio
        payout_ratio_avg = mean(payout_ratios) if payout_ratios else 0.0
        
        print(f"  Projected EPS growth rate: {projected_growth_rate:.1%}")
        print(f"  Average payout ratio: {payout_ratio_avg:.1%}")
        print(f"  Historical P/E range: {min(pe_data):.1f} - {max(pe_data):.1f}" if pe_data else "  No P/E data")
        
        # Calculate projected return using EPS Growth Method
        try:
            projection = calculate_eps_projected_return(
                ticker, current_price, eps_data, pe_data,
                payout_ratio_avg, projected_growth_rate, years=10
            )
            
            if projection is None:
                print(f"  Unable to calculate projection for {ticker}")
                continue
            
            annualized_return = projection['annualized_return']
            
            print(f"  Projected 10-year annualized return: {annualized_return:.1%}")
            print(f"  Future EPS: ${projection['future_eps']:.2f}")
            print(f"  Future P/E: {projection['future_pe']:.1f}")
            print(f"  Future stock price: ${projection['future_stock_price']:.2f}")
            
            # Check if meets our criteria
            meets_15_percent = annualized_return >= 0.15
            meets_12_percent = annualized_return >= 0.12
            
            if meets_12_percent:
                result = {
                    'Ticker': ticker,
                    'Current_Price': current_price,
                    'Current_EPS': projection['current_eps'],
                    'Projected_Growth_Rate': projected_growth_rate,
                    'Future_EPS': projection['future_eps'],
                    'Future_PE': projection['future_pe'],
                    'Future_Stock_Price': projection['future_stock_price'],
                    'Avg_Payout_Ratio': payout_ratio_avg,
                    'Current_Dividend_Per_Share': projection['current_dividend_per_share'],
                    'Total_Dividends_10yr': projection['total_dividends'],
                    'Total_Future_Value': projection['total_future_value'],
                    'Total_Return_10yr': projection['total_return'],
                    'Annualized_Return': annualized_return,
                    'Meets_15_Percent': meets_15_percent,
                    'Meets_12_Percent': meets_12_percent,
                    'EPS_Years_Count': len(eps_data),
                    'Growth_Rate_Count': len(growth_rates),
                    'Avg_Historical_PE': mean(pe_data) if pe_data else None
                }
                
                results.append(result)
                
                status = "✓ Excellent" if meets_15_percent else "✓ Acceptable"
                print(f"  {status} - {ticker} qualifies with {annualized_return:.1%} projected return")
            else:
                print(f"  ✗ {ticker} does not meet minimum 12% return threshold")
                
        except Exception as e:
            print(f"  Error calculating projection for {ticker}: {e}")
            continue
        
        time.sleep(0.1)  # Small delay

    if results:
        results_df = pd.DataFrame(results)
        
        # Sort by annualized return (highest first)
        results_df = results_df.sort_values('Annualized_Return', ascending=False)
        
        output_file = 'eps_growth_filtered_stocks.csv'
        results_df.to_csv(output_file, index=False)
        print(f"\nEPS Growth Method filtering complete! {len(results)} stocks meet the criteria.")
        print(f"Results saved to {output_file}")
        
        # Count by performance level
        excellent_count = sum(results_df['Meets_15_Percent'])
        acceptable_count = len(results_df) - excellent_count
        
        print(f"\nPerformance breakdown:")
        print(f"- Excellent (≥15%): {excellent_count} stocks")
        print(f"- Acceptable (12-15%): {acceptable_count} stocks")
        
        # Print summary
        print("\nTop performers by projected return:")
        for i, (_, row) in enumerate(results_df.head(10).iterrows(), 1):
            status = "Excellent" if row['Meets_15_Percent'] else "Acceptable"
            print(f"{i:2d}. {row['Ticker']}: {row['Annualized_Return']:.1%} ({status})")
            print(f"     Current EPS: ${row['Current_EPS']:.2f}, Growth: {row['Projected_Growth_Rate']:.1%}, "
                  f"Future EPS: ${row['Future_EPS']:.2f}")
        
        # Print additional insights
        avg_return = results_df['Annualized_Return'].mean()
        max_return = results_df['Annualized_Return'].max()
        min_return = results_df['Annualized_Return'].min()
        
        print(f"\nAdditional insights:")
        print(f"- Average projected return: {avg_return:.1%}")
        print(f"- Return range: {min_return:.1%} to {max_return:.1%}")
        print(f"- Average EPS growth rate: {results_df['Projected_Growth_Rate'].mean():.1%}")
        print(f"- Average future P/E: {results_df['Future_PE'].mean():.1f}")
        
        # Compare with original ROE method results
        print(f"\nMethodology comparison:")
        print(f"- ROE Method: {len(df)} stocks qualified")
        print(f"- EPS Growth Method: {len(results_df)} stocks qualified")
        
        # Show overlap
        original_tickers = set(df['Ticker'].tolist())
        new_tickers = set(results_df['Ticker'].tolist())
        overlap = original_tickers.intersection(new_tickers)
        
        print(f"- Stocks that qualify under both methods: {len(overlap)}")
        if overlap:
            print(f"  {', '.join(sorted(overlap))}")
        
    else:
        print("No stocks meet the minimum 12% projected return criteria using EPS Growth Method.")

if __name__ == "__main__":
    main()