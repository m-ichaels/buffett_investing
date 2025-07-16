import pandas as pd
import requests
import time
from statistics import mean

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

def calculate_retained_earnings_growth(beginning_re, ending_re, dividends_paid):
    """
    Calculate the growth in retained earnings.
    Growth = Ending RE - Beginning RE
    Net Income = RE Growth + Dividends Paid
    """
    if beginning_re is None or ending_re is None:
        return None, None
    
    re_growth = ending_re - beginning_re
    
    # If dividends paid is available, calculate net income
    net_income = re_growth + (dividends_paid if dividends_paid else 0)
    
    return re_growth, net_income

def calculate_rore(net_income, beginning_re):
    """
    Calculate Return on Retained Earnings (RORE).
    RORE = Net Income / Beginning Retained Earnings
    """
    if net_income is None or beginning_re is None or beginning_re <= 0:
        return None
    
    return net_income / beginning_re

def analyze_rore_trend(rore_values, years):
    """
    Analyze the trend of RORE over time.
    Returns trend analysis and average RORE.
    """
    if len(rore_values) < 2:
        return {"trend": "insufficient_data", "avg_rore": None, "consistent": False}
    
    avg_rore = mean(rore_values)
    
    # Check consistency - at least 80% of years should meet 12% threshold
    qualifying_years = sum(1 for rore in rore_values if rore >= 0.12)
    consistent = qualifying_years >= len(rore_values) * 0.8
    
    # Determine trend
    if avg_rore >= 0.20:  # 20% average RORE
        trend = "excellent"
    elif avg_rore >= 0.15:  # 15% average RORE
        trend = "strong"
    elif avg_rore >= 0.12:  # 12% average RORE
        trend = "good"
    elif avg_rore >= 0.08:  # 8% average RORE
        trend = "moderate"
    else:
        trend = "poor"
    
    return {
        "trend": trend,
        "avg_rore": avg_rore,
        "consistent": consistent,
        "qualifying_years": qualifying_years,
        "total_years": len(rore_values)
    }

def main():
    # Load tickers from the FCF filtered results
    input_file = 'fcf_filtered_stocks.csv'
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

    # Alternative concept names for retained earnings and related metrics
    retained_earnings_concepts = [
        'RetainedEarningsAccumulatedDeficit',
        'RetainedEarnings',
        'AccumulatedDeficit',
        'AccumulatedEarningsLossesIncludingOtherComprehensiveIncome'
    ]
    
    net_income_concepts = [
        'NetIncomeLoss',
        'NetIncomeLossAvailableToCommonStockholdersBasic',
        'NetIncomeLossAttributableToParent',
        'NetIncome'
    ]
    
    dividends_concepts = [
        'PaymentsOfDividendsCommonStock',
        'PaymentsOfDividends',
        'CommonStockDividendsPerShareCashPaid',
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

        # Get available fiscal years for this company
        if 'facts' not in facts or 'us-gaap' not in facts['facts']:
            print(f"No us-gaap data found for {ticker}")
            continue
            
        us_gaap_data = facts['facts']['us-gaap']
        
        # Find available fiscal years from retained earnings data
        available_years = set()
        for concept in retained_earnings_concepts:
            if concept in us_gaap_data and 'units' in us_gaap_data[concept] and 'USD' in us_gaap_data[concept]['units']:
                for entry in us_gaap_data[concept]['units']['USD']:
                    if entry.get('form') in ['10-K', '10-K/A']:
                        available_years.add(entry.get('fy'))
        
        # Focus on recent years (2019-2022 for calculating RORE for 2020-2022)
        available_years = sorted([year for year in available_years if year and 2019 <= year <= 2022])
        
        print(f"Available fiscal years for {ticker}: {available_years}")
        
        if len(available_years) < 3:  # Need at least 3 years (2019, 2020, 2021 minimum)
            print(f"{ticker} has insufficient fiscal years ({len(available_years)} years, need at least 3)")
            continue

        rore_values = []
        years_with_data = []
        detailed_data = []
        
        # Calculate RORE for each available year (starting from 2020)
        for year in available_years[1:]:  # Skip first year as it's used as beginning RE
            prev_year = year - 1
            
            # Get retained earnings for current and previous year
            beginning_re = get_latest_value(facts, retained_earnings_concepts, prev_year)
            ending_re = get_latest_value(facts, retained_earnings_concepts, year)
            
            # Try to get net income directly (more reliable than calculating from RE)
            net_income = get_latest_value(facts, net_income_concepts, year)
            
            # Get dividends paid (optional, for verification)
            dividends_paid = get_latest_value(facts, dividends_concepts, year)
            
            # Calculate RORE
            if net_income is not None and beginning_re is not None and beginning_re > 0:
                rore = calculate_rore(net_income, beginning_re)
                
                if rore is not None:
                    rore_values.append(rore)
                    years_with_data.append(year)
                    
                    detailed_data.append({
                        'year': year,
                        'beginning_re': beginning_re,
                        'ending_re': ending_re,
                        'net_income': net_income,
                        'dividends_paid': dividends_paid,
                        'rore': rore
                    })
                    
                    print(f"  {year}: RORE = {rore:.1%} (Net Income: ${net_income:,.0f}, Beginning RE: ${beginning_re:,.0f})")
                else:
                    print(f"  {year}: Could not calculate RORE")
            else:
                print(f"  {year}: Missing data - Net Income: {net_income}, Beginning RE: {beginning_re}")
        
        # Check if we have enough data and if RORE meets criteria
        if len(rore_values) >= 2:  # At least 2 years of RORE data
            # Calculate average RORE
            avg_rore = mean(rore_values)
            
            # Check if average RORE meets 12% threshold
            if avg_rore >= 0.12:
                # Analyze trend
                trend_analysis = analyze_rore_trend(rore_values, years_with_data)
                
                result = {
                    'Ticker': ticker,
                    'Years_Count': len(rore_values),
                    'Years_Data': ','.join(map(str, years_with_data)),
                    'Avg_RORE': avg_rore,
                    'Meets_12_Percent': avg_rore >= 0.12,
                    'Trend': trend_analysis['trend'],
                    'Consistent': trend_analysis['consistent'],
                    'Qualifying_Years': trend_analysis['qualifying_years'],
                    'Total_Years': trend_analysis['total_years']
                }
                
                # Add individual year RORE data
                for data in detailed_data:
                    result[f'RORE_{data["year"]}'] = data['rore']
                    result[f'NetIncome_{data["year"]}'] = data['net_income']
                    result[f'BeginningRE_{data["year"]}'] = data['beginning_re']
                
                results.append(result)
                print(f"{ticker} qualifies with {avg_rore:.1%} average RORE over {len(rore_values)} years")
                print(f"  Trend: {trend_analysis['trend']}, Consistent: {trend_analysis['consistent']}")
            else:
                print(f"{ticker} does not meet 12% RORE threshold (avg: {avg_rore:.1%})")
        else:
            print(f"{ticker} has insufficient RORE data ({len(rore_values)} years, need at least 2)")
        
        time.sleep(0.2)  # Respect SEC EDGAR API rate limit

    if results:
        results_df = pd.DataFrame(results)
        
        # Reorder columns to put basic info first
        basic_cols = [
            'Ticker', 'Years_Count', 'Years_Data', 'Avg_RORE', 'Meets_12_Percent',
            'Trend', 'Consistent', 'Qualifying_Years', 'Total_Years'
        ]
        
        # Get all RORE, NetIncome, and BeginningRE columns and sort them
        rore_cols = sorted([col for col in results_df.columns if col.startswith('RORE_')])
        ni_cols = sorted([col for col in results_df.columns if col.startswith('NetIncome_')])
        re_cols = sorted([col for col in results_df.columns if col.startswith('BeginningRE_')])
        
        results_df = results_df[basic_cols + rore_cols + ni_cols + re_cols]
        
        output_file = 'rore_filtered_stocks.csv'
        results_df.to_csv(output_file, index=False)
        print(f"\nRORE filtering complete! {len(results)} stocks meet the 12% criterion.")
        print(f"Results saved to {output_file}")
        
        # Print summary
        print("\nSummary of qualifying stocks:")
        for _, row in results_df.iterrows():
            consistency = "Consistent" if row['Consistent'] else "Variable"
            print(f"{row['Ticker']}: {row['Avg_RORE']:.1%} avg RORE over {row['Years_Count']} years, "
                  f"Trend: {row['Trend']}, {consistency}")
        
        # Print additional insights
        excellent_count = sum(1 for _, row in results_df.iterrows() if row['Trend'] == 'excellent')
        strong_count = sum(1 for _, row in results_df.iterrows() if row['Trend'] == 'strong')
        consistent_count = sum(results_df['Consistent'])
        
        print(f"\nAdditional insights:")
        print(f"- {excellent_count} stocks with excellent RORE (≥20%)")
        print(f"- {strong_count} stocks with strong RORE (15-20%)")
        print(f"- {consistent_count}/{len(results)} stocks show consistent performance")
        print(f"- RORE range: {results_df['Avg_RORE'].min():.1%} to {results_df['Avg_RORE'].max():.1%}")
        
    else:
        print("No stocks meet the 12% RORE criterion.")

if __name__ == "__main__":
    main()