import pandas as pd
import requests
import time
import yfinance as yf
from statistics import mean
import numpy as np

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

def calculate_roe(net_income, shareholders_equity):
    """Calculate Return on Equity."""
    if net_income is None or shareholders_equity is None or shareholders_equity <= 0:
        return None
    return net_income / shareholders_equity

def calculate_payout_ratio(dividends_paid, net_income):
    """Calculate dividend payout ratio."""
    if dividends_paid is None or net_income is None or net_income <= 0:
        return 0.0  # Assume no dividends if data is missing
    return abs(dividends_paid) / net_income

def calculate_retention_ratio(payout_ratio):
    """Calculate retention ratio (1 - payout ratio)."""
    return 1 - payout_ratio

def project_future_equity(current_equity, roe, retention_ratio, years):
    """Project future book value using ROE method."""
    # Growth rate = ROE × Retention Ratio
    growth_rate = roe * retention_ratio
    
    # Future equity = Current equity × (1 + growth_rate)^years
    future_equity = current_equity * ((1 + growth_rate) ** years)
    
    return future_equity, growth_rate

def estimate_future_pe_ratio(current_pe, projected_growth_rate):
    """
    Estimate future P/E ratio based on growth prospects.
    Conservative approach: assume P/E compression over time.
    """
    if current_pe is None or current_pe <= 0:
        # Use market average P/E if current P/E is unavailable
        current_pe = 15.0
    
    # Conservative assumption: P/E ratio decreases slightly over time
    # but stays higher for higher growth companies
    if projected_growth_rate > 0.15:  # High growth (>15%)
        future_pe = max(current_pe * 0.9, 12.0)  # Slight compression, min 12
    elif projected_growth_rate > 0.10:  # Moderate growth (10-15%)
        future_pe = max(current_pe * 0.85, 10.0)  # More compression, min 10
    elif projected_growth_rate > 0.05:  # Low growth (5-10%)
        future_pe = max(current_pe * 0.8, 8.0)   # Significant compression, min 8
    else:  # Very low/no growth (<5%)
        future_pe = max(current_pe * 0.7, 6.0)   # Major compression, min 6
    
    return future_pe

def calculate_projected_return(ticker, current_price, current_equity, current_shares, 
                             roe_avg, payout_ratio_avg, current_pe, years=10):
    """
    Calculate projected return using ROE method.
    
    Steps:
    1. Calculate retention ratio
    2. Project future equity growth
    3. Estimate future EPS
    4. Estimate future stock price
    5. Calculate total return including dividends
    """
    
    # Step 1: Calculate retention ratio
    retention_ratio = calculate_retention_ratio(payout_ratio_avg)
    
    # Step 2: Project future equity
    future_equity, growth_rate = project_future_equity(
        current_equity, roe_avg, retention_ratio, years
    )
    
    # Step 3: Estimate future EPS
    # Assume shares outstanding remain constant (conservative)
    future_book_value_per_share = future_equity / current_shares
    
    # Future EPS = Future Book Value × ROE
    future_eps = future_book_value_per_share * roe_avg
    
    # Step 4: Estimate future P/E and stock price
    future_pe = estimate_future_pe_ratio(current_pe, growth_rate)
    future_stock_price = future_eps * future_pe
    
    # Step 5: Calculate dividends over the period
    # Assume dividends grow at the same rate as equity
    current_eps = current_equity * roe_avg / current_shares
    current_dividend_per_share = current_eps * payout_ratio_avg
    
    # Total dividends over the period (growing annuity)
    if growth_rate > 0:
        total_dividends = current_dividend_per_share * (
            ((1 + growth_rate) ** years - 1) / growth_rate
        )
    else:
        total_dividends = current_dividend_per_share * years
    
    # Step 6: Calculate total return
    total_future_value = future_stock_price + total_dividends
    total_return = (total_future_value / current_price) - 1
    
    # Step 7: Calculate annualized return
    annualized_return = (total_future_value / current_price) ** (1/years) - 1
    
    return {
        'retention_ratio': retention_ratio,
        'equity_growth_rate': growth_rate,
        'future_equity': future_equity,
        'future_eps': future_eps,
        'future_pe': future_pe,
        'future_stock_price': future_stock_price,
        'total_dividends': total_dividends,
        'total_return': total_return,
        'annualized_return': annualized_return,
        'current_dividend_per_share': current_dividend_per_share
    }

def main():
    # Load tickers from the earnings yield filtered results
    input_file = 'earnings_yield_filtered_stocks.csv'
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
    
    shareholders_equity_concepts = [
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        'CommonStockholdersEquity'
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

        # Collect historical data for ROE and payout ratio calculation
        years_to_analyze = [2020, 2021, 2022]  # Last 3 years
        roe_values = []
        payout_ratios = []
        
        current_equity = None
        current_shares = None
        current_pe = None
        
        for year in years_to_analyze:
            # Get financial data for each year
            net_income = get_latest_value(facts, net_income_concepts, year)
            shareholders_equity = get_latest_value(facts, shareholders_equity_concepts, year)
            shares_outstanding = get_shares_outstanding(facts, shares_outstanding_concepts, year)
            dividends_paid = get_latest_value(facts, dividends_concepts, year)
            
            if net_income and shareholders_equity and shares_outstanding:
                # Calculate ROE
                roe = calculate_roe(net_income, shareholders_equity)
                if roe:
                    roe_values.append(roe)
                
                # Calculate payout ratio
                payout_ratio = calculate_payout_ratio(dividends_paid, net_income)
                payout_ratios.append(payout_ratio)
                
                # Store 2022 data as current data
                if year == 2022:
                    current_equity = shareholders_equity
                    current_shares = shares_outstanding
                    current_eps = net_income / shares_outstanding
                    current_pe = current_price / current_eps if current_eps > 0 else None
                
                print(f"  {year}: ROE = {roe:.1%}, Payout Ratio = {payout_ratio:.1%}")
        
        # Check if we have enough data
        if len(roe_values) < 2:
            print(f"  Insufficient ROE data for {ticker}")
            continue
        
        if current_equity is None or current_shares is None:
            print(f"  Missing current financial data for {ticker}")
            continue
        
        # Calculate averages
        roe_avg = mean(roe_values)
        payout_ratio_avg = mean(payout_ratios)
        
        print(f"  Average ROE: {roe_avg:.1%}")
        print(f"  Average Payout Ratio: {payout_ratio_avg:.1%}")
        print(f"  Current P/E: {current_pe:.1f}" if current_pe else "  Current P/E: N/A")
        
        # Calculate projected return
        try:
            projection = calculate_projected_return(
                ticker, current_price, current_equity, current_shares,
                roe_avg, payout_ratio_avg, current_pe, years=10
            )
            
            annualized_return = projection['annualized_return']
            
            print(f"  Projected 10-year annualized return: {annualized_return:.1%}")
            print(f"  Equity growth rate: {projection['equity_growth_rate']:.1%}")
            print(f"  Future stock price: ${projection['future_stock_price']:.2f}")
            
            # Check if meets our criteria
            meets_15_percent = annualized_return >= 0.15
            meets_12_percent = annualized_return >= 0.12
            
            if meets_12_percent:
                result = {
                    'Ticker': ticker,
                    'Current_Price': current_price,
                    'Current_PE': current_pe,
                    'Avg_ROE': roe_avg,
                    'Avg_Payout_Ratio': payout_ratio_avg,
                    'Retention_Ratio': projection['retention_ratio'],
                    'Equity_Growth_Rate': projection['equity_growth_rate'],
                    'Future_Stock_Price': projection['future_stock_price'],
                    'Future_PE': projection['future_pe'],
                    'Total_Dividends_10yr': projection['total_dividends'],
                    'Total_Return_10yr': projection['total_return'],
                    'Annualized_Return': annualized_return,
                    'Meets_15_Percent': meets_15_percent,
                    'Meets_12_Percent': meets_12_percent,
                    'ROE_Years_Count': len(roe_values)
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
        
        output_file = 'roe_projection_filtered_stocks.csv'
        results_df.to_csv(output_file, index=False)
        print(f"\nROE projection filtering complete! {len(results)} stocks meet the criteria.")
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
            print(f"     ROE: {row['Avg_ROE']:.1%}, Growth: {row['Equity_Growth_Rate']:.1%}, "
                  f"Current P/E: {row['Current_PE']:.1f}")
        
        # Print additional insights
        avg_return = results_df['Annualized_Return'].mean()
        max_return = results_df['Annualized_Return'].max()
        min_return = results_df['Annualized_Return'].min()
        
        print(f"\nAdditional insights:")
        print(f"- Average projected return: {avg_return:.1%}")
        print(f"- Return range: {min_return:.1%} to {max_return:.1%}")
        print(f"- Average ROE: {results_df['Avg_ROE'].mean():.1%}")
        print(f"- Average equity growth rate: {results_df['Equity_Growth_Rate'].mean():.1%}")
        
    else:
        print("No stocks meet the minimum 12% projected return criteria.")

if __name__ == "__main__":
    main()