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

def calculate_free_cash_flow(operating_cash_flow, capex):
    """
    Calculate Free Cash Flow
    FCF = Operating Cash Flow - Capital Expenditures
    """
    if operating_cash_flow is None or capex is None:
        return None
    
    # Capital expenditures are typically reported as negative values
    # If capex is positive, make it negative for the calculation
    if capex > 0:
        capex = -capex
    
    return operating_cash_flow + capex  # Adding because capex should be negative

def analyze_fcf_trend(fcf_values, years):
    """
    Analyze the trend of free cash flow over time.
    Returns trend analysis and growth metrics.
    """
    if len(fcf_values) < 2:
        return {"trend": "insufficient_data", "growth_rate": None, "is_growing": False}
    
    # Calculate year-over-year growth rates
    growth_rates = []
    for i in range(1, len(fcf_values)):
        if fcf_values[i-1] > 0:  # Avoid division by zero or negative base
            growth_rate = (fcf_values[i] - fcf_values[i-1]) / fcf_values[i-1]
            growth_rates.append(growth_rate)
    
    if not growth_rates:
        return {"trend": "no_growth_data", "growth_rate": None, "is_growing": False}
    
    avg_growth_rate = mean(growth_rates)
    
    # Check if majority of years show positive growth
    positive_growth_years = sum(1 for rate in growth_rates if rate > 0)
    is_growing = positive_growth_years >= len(growth_rates) / 2
    
    # Determine trend
    if avg_growth_rate > 0.05:  # 5% average growth
        trend = "strong_growth"
    elif avg_growth_rate > 0:
        trend = "moderate_growth"
    elif avg_growth_rate > -0.05:
        trend = "stable"
    else:
        trend = "declining"
    
    return {
        "trend": trend,
        "growth_rate": avg_growth_rate,
        "is_growing": is_growing,
        "growth_rates": growth_rates
    }

def main():
    # Load tickers from the ROTC filtered results
    input_file = 'rotc_filtered_stocks.csv'
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

    # Alternative concept names for free cash flow components
    operating_cash_flow_concepts = [
        'NetCashProvidedByUsedInOperatingActivities',
        'CashProvidedByUsedInOperatingActivities',
        'OperatingActivitiesCashFlow'
    ]
    
    capex_concepts = [
        'PaymentsToAcquirePropertyPlantAndEquipment',
        'PaymentsForPropertyPlantAndEquipment',
        'CapitalExpenditures',
        'PaymentsToAcquireProductiveAssets',
        'CashOutflowsForPropertyPlantAndEquipment'
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
        
        # Find available fiscal years from operating cash flow data
        available_years = set()
        for concept in operating_cash_flow_concepts:
            if concept in us_gaap_data and 'units' in us_gaap_data[concept] and 'USD' in us_gaap_data[concept]['units']:
                for entry in us_gaap_data[concept]['units']['USD']:
                    if entry.get('form') in ['10-K', '10-K/A']:
                        available_years.add(entry.get('fy'))
        
        # Focus on recent years (2020-2022 for last 3 years, extend to 2018-2022 for 5 years)
        available_years = sorted([year for year in available_years if year and 2018 <= year <= 2022])
        recent_years = sorted([year for year in available_years if year >= 2020])  # Last 3 years
        
        print(f"Available fiscal years for {ticker}: {available_years}")
        print(f"Recent years (2020-2022): {recent_years}")
        
        if len(recent_years) < 3:
            print(f"{ticker} has insufficient recent fiscal years ({len(recent_years)} years, need at least 3)")
            continue

        fcf_values = []
        years_with_data = []
        
        # Calculate FCF for each available year (use all available for trend analysis)
        for year in available_years:
            operating_cf = get_latest_value(facts, operating_cash_flow_concepts, year)
            capex = get_latest_value(facts, capex_concepts, year)
            
            # Calculate free cash flow
            fcf = calculate_free_cash_flow(operating_cf, capex)
            
            if fcf is not None:
                fcf_values.append(fcf)
                years_with_data.append(year)
                print(f"  {year}: FCF = ${fcf:,.0f}")
            else:
                print(f"  {year}: Missing or invalid data for FCF calculation")
        
        # Check if we have enough data and if recent years are all positive
        if len(fcf_values) >= 3 and len(years_with_data) >= 3:
            # Get FCF values for recent years (last 3-5 years)
            recent_fcf_indices = [i for i, year in enumerate(years_with_data) if year >= 2020]
            recent_fcf_values = [fcf_values[i] for i in recent_fcf_indices]
            recent_fcf_years = [years_with_data[i] for i in recent_fcf_indices]
            
            # Check if all recent years have positive FCF
            all_recent_positive = all(fcf > 0 for fcf in recent_fcf_values)
            
            if all_recent_positive and len(recent_fcf_values) >= 3:
                # Analyze trend over all available years
                trend_analysis = analyze_fcf_trend(fcf_values, years_with_data)
                
                result = {
                    'Ticker': ticker,
                    'Recent_Years_Count': len(recent_fcf_values),
                    'Recent_Years': ','.join(map(str, recent_fcf_years)),
                    'All_Recent_Positive': all_recent_positive,
                    'Total_Years_Data': len(fcf_values),
                    'All_Data_Years': ','.join(map(str, years_with_data)),
                    'Trend': trend_analysis['trend'],
                    'Avg_Growth_Rate': trend_analysis['growth_rate'],
                    'Is_Growing': trend_analysis['is_growing'],
                    'Recent_Avg_FCF': mean(recent_fcf_values),
                    'Total_Avg_FCF': mean(fcf_values)
                }
                
                # Add individual year FCF data
                for i, year in enumerate(years_with_data):
                    result[f'FCF_{year}'] = fcf_values[i]
                
                results.append(result)
                print(f"{ticker} qualifies with positive FCF in all {len(recent_fcf_values)} recent years")
                print(f"  Trend: {trend_analysis['trend']}, Growing: {trend_analysis['is_growing']}")
                if trend_analysis['growth_rate']:
                    print(f"  Average growth rate: {trend_analysis['growth_rate']:.1%}")
            else:
                negative_years = [years_with_data[i] for i in recent_fcf_indices if fcf_values[i] <= 0]
                print(f"{ticker} has negative FCF in recent years: {negative_years}")
        else:
            print(f"{ticker} has insufficient data ({len(fcf_values)} years, need at least 3)")
        
        time.sleep(0.2)  # Respect SEC EDGAR API rate limit of 10 requests per second

    if results:
        results_df = pd.DataFrame(results)
        
        # Reorder columns to put basic info first
        basic_cols = [
            'Ticker', 'Recent_Years_Count', 'Recent_Years', 'All_Recent_Positive',
            'Total_Years_Data', 'All_Data_Years', 'Trend', 'Avg_Growth_Rate', 
            'Is_Growing', 'Recent_Avg_FCF', 'Total_Avg_FCF'
        ]
        fcf_cols = [col for col in results_df.columns if col.startswith('FCF_')]
        fcf_cols.sort()  # Sort FCF columns by year
        
        results_df = results_df[basic_cols + fcf_cols]
        
        output_file = 'fcf_filtered_stocks.csv'
        results_df.to_csv(output_file, index=False)
        print(f"\nFCF filtering complete! {len(results)} stocks meet the criterion.")
        print(f"Results saved to {output_file}")
        
        # Print summary
        print("\nSummary of qualifying stocks:")
        for _, row in results_df.iterrows():
            growth_status = "Growing" if row['Is_Growing'] else "Stable/Declining"
            print(f"{row['Ticker']}: {row['Recent_Years_Count']} recent years positive FCF, "
                  f"${row['Recent_Avg_FCF']:,.0f} avg recent FCF, {growth_status}")
        
        # Print additional insights
        growing_count = sum(results_df['Is_Growing'])
        print(f"\nAdditional insights:")
        print(f"- {growing_count}/{len(results)} stocks show growing FCF trend")
        print(f"- Average recent FCF range: ${results_df['Recent_Avg_FCF'].min():,.0f} to ${results_df['Recent_Avg_FCF'].max():,.0f}")
        
    else:
        print("No stocks meet the FCF criterion.")

if __name__ == "__main__":
    main()