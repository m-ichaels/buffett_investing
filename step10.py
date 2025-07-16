import pandas as pd
import os
from statistics import mean

def load_existing_results(file_path):
    """Load results from both ROE and EPS growth methods."""
    try:
        # Load ROE method results
        roe_df = pd.read_excel(file_path, sheet_name='ROE_Projection_Filtered_Stocks')
        print(f"Loaded {len(roe_df)} stocks from ROE method")
        
        # Load EPS growth method results
        eps_df = pd.read_excel(file_path, sheet_name='EPS_Growth_Filtered_Stocks')
        print(f"Loaded {len(eps_df)} stocks from EPS growth method")
        
        return roe_df, eps_df
        
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        return None, None
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None, None

def combine_return_estimates(roe_df, eps_df):
    """
    Combine ROE and EPS growth method results and calculate average returns.
    Only include stocks that appear in both methods.
    """
    
    # Find common tickers that appear in both methods
    roe_tickers = set(roe_df['Ticker'].str.upper())
    eps_tickers = set(eps_df['Ticker'].str.upper())
    common_tickers = roe_tickers.intersection(eps_tickers)
    
    print(f"Found {len(common_tickers)} stocks that appear in both methods")
    
    if not common_tickers:
        print("No common stocks found between the two methods!")
        return None
    
    # Create dictionaries for quick lookup
    roe_dict = {row['Ticker'].upper(): row for _, row in roe_df.iterrows()}
    eps_dict = {row['Ticker'].upper(): row for _, row in eps_df.iterrows()}
    
    combined_results = []
    
    for ticker in sorted(common_tickers):
        roe_row = roe_dict[ticker]
        eps_row = eps_dict[ticker]
        
        # Calculate average return
        roe_return = roe_row['Annualized_Return']
        eps_return = eps_row['Annualized_Return']
        average_return = (roe_return + eps_return) / 2
        
        # Check if meets criteria
        meets_15_percent = average_return >= 0.15
        meets_12_percent = average_return >= 0.12
        
        # Calculate other averages where applicable
        avg_current_price = (roe_row['Current_Price'] + eps_row['Current_Price']) / 2
        
        # For PE ratio, use the one from EPS method as it's more relevant
        current_pe = eps_row.get('Avg_Historical_PE', roe_row.get('Current_PE'))
        
        # Calculate confidence metrics
        return_difference = abs(roe_return - eps_return)
        return_agreement = 1 - (return_difference / max(roe_return, eps_return))
        
        # Determine which method is more optimistic
        more_optimistic = "ROE" if roe_return > eps_return else "EPS Growth"
        
        combined_result = {
            'Ticker': ticker,
            'Current_Price': avg_current_price,
            'ROE_Method_Return': roe_return,
            'EPS_Method_Return': eps_return,
            'Average_Return': average_return,
            'Return_Difference': return_difference,
            'Return_Agreement': return_agreement,
            'More_Optimistic_Method': more_optimistic,
            'Current_PE': current_pe,
            'Meets_15_Percent': meets_15_percent,
            'Meets_12_Percent': meets_12_percent,
            
            # ROE method specific data
            'ROE_Avg_ROE': roe_row['Avg_ROE'],
            'ROE_Equity_Growth_Rate': roe_row['Equity_Growth_Rate'],
            'ROE_Future_Stock_Price': roe_row['Future_Stock_Price'],
            'ROE_Total_Dividends': roe_row['Total_Dividends_10yr'],
            
            # EPS method specific data
            'EPS_Projected_Growth_Rate': eps_row['Projected_Growth_Rate'],
            'EPS_Future_EPS': eps_row['Future_EPS'],
            'EPS_Future_Stock_Price': eps_row['Future_Stock_Price'],
            'EPS_Total_Dividends': eps_row['Total_Dividends_10yr'],
            
            # Combined projections (averages)
            'Avg_Future_Stock_Price': (roe_row['Future_Stock_Price'] + eps_row['Future_Stock_Price']) / 2,
            'Avg_Total_Dividends': (roe_row['Total_Dividends_10yr'] + eps_row['Total_Dividends_10yr']) / 2,
        }
        
        combined_results.append(combined_result)
        
        # Print processing info
        agreement_level = "High" if return_agreement > 0.8 else "Medium" if return_agreement > 0.6 else "Low"
        print(f"  {ticker}: ROE={roe_return:.1%}, EPS={eps_return:.1%}, Avg={average_return:.1%} ({agreement_level} agreement)")
    
    return combined_results

def main():
    file_path = os.path.join('Results', '2022.xlsx')
    
    # Load existing results
    roe_df, eps_df = load_existing_results(file_path)
    
    if roe_df is None or eps_df is None:
        print("Could not load one or both result sheets. Make sure step8.py and step9.py have been run.")
        return
    
    # Combine the results
    combined_results = combine_return_estimates(roe_df, eps_df)
    
    if not combined_results:
        print("No combined results generated.")
        return
    
    # Create DataFrame and sort by average return
    results_df = pd.DataFrame(combined_results)
    results_df = results_df.sort_values('Average_Return', ascending=False)
    
    # Filter for stocks that meet minimum criteria
    qualified_stocks = results_df[results_df['Meets_12_Percent'] == True]
    
    if qualified_stocks.empty:
        print("No stocks meet the minimum 12% average return criteria.")
        return
    
    # Save to Excel file as new worksheet
    try:
        with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            qualified_stocks.to_excel(writer, sheet_name='Combined_Methods_Filtered_Stocks', index=False)
        
        print(f"\nCombined methods filtering complete! {len(qualified_stocks)} stocks meet the criteria.")
        print(f"Results saved to '{file_path}' in 'Combined_Methods_Filtered_Stocks' worksheet")
        
        # Count by performance level
        excellent_count = sum(qualified_stocks['Meets_15_Percent'])
        acceptable_count = len(qualified_stocks) - excellent_count
        
        print(f"\nPerformance breakdown:")
        print(f"- Excellent (≥15% avg): {excellent_count} stocks")
        print(f"- Acceptable (12-15% avg): {acceptable_count} stocks")
        
        # Print summary of top performers
        print("\nTop performers by average projected return:")
        for i, (_, row) in enumerate(qualified_stocks.head(10).iterrows(), 1):
            status = "Excellent" if row['Meets_15_Percent'] else "Acceptable"
            agreement = "High" if row['Return_Agreement'] > 0.8 else "Medium" if row['Return_Agreement'] > 0.6 else "Low"
            
            print(f"{i:2d}. {row['Ticker']}: {row['Average_Return']:.1%} ({status})")
            print(f"     ROE: {row['ROE_Method_Return']:.1%}, EPS: {row['EPS_Method_Return']:.1%} ({agreement} agreement)")
            print(f"     More optimistic: {row['More_Optimistic_Method']}, Diff: {row['Return_Difference']:.1%}")
        
        # Print additional insights
        print(f"\nAdditional insights:")
        print(f"- Average combined return: {qualified_stocks['Average_Return'].mean():.1%}")
        print(f"- Return range: {qualified_stocks['Average_Return'].min():.1%} to {qualified_stocks['Average_Return'].max():.1%}")
        print(f"- Average return difference between methods: {qualified_stocks['Return_Difference'].mean():.1%}")
        print(f"- Average agreement level: {qualified_stocks['Return_Agreement'].mean():.1%}")
        
        # Method comparison
        roe_higher = sum(qualified_stocks['More_Optimistic_Method'] == 'ROE')
        eps_higher = sum(qualified_stocks['More_Optimistic_Method'] == 'EPS Growth')
        
        print(f"\nMethod comparison:")
        print(f"- ROE method more optimistic: {roe_higher} stocks")
        print(f"- EPS Growth method more optimistic: {eps_higher} stocks")
        
        # Agreement analysis
        high_agreement = sum(qualified_stocks['Return_Agreement'] > 0.8)
        medium_agreement = sum((qualified_stocks['Return_Agreement'] > 0.6) & (qualified_stocks['Return_Agreement'] <= 0.8))
        low_agreement = sum(qualified_stocks['Return_Agreement'] <= 0.6)
        
        print(f"\nAgreement analysis:")
        print(f"- High agreement (>80%): {high_agreement} stocks")
        print(f"- Medium agreement (60-80%): {medium_agreement} stocks")
        print(f"- Low agreement (<60%): {low_agreement} stocks")
        
        # Show stocks with highest agreement
        print(f"\nStocks with highest method agreement:")
        high_agreement_stocks = qualified_stocks.nlargest(5, 'Return_Agreement')
        for i, (_, row) in enumerate(high_agreement_stocks.iterrows(), 1):
            print(f"{i}. {row['Ticker']}: {row['Return_Agreement']:.1%} agreement, {row['Average_Return']:.1%} avg return")
        
        # Show input source info
        print(f"\nInput sources:")
        print(f"- ROE method results: {len(roe_df)} stocks")
        print(f"- EPS Growth method results: {len(eps_df)} stocks")
        print(f"- Common stocks (both methods): {len(results_df)} stocks")
        print(f"- Final qualified stocks (≥12% avg): {len(qualified_stocks)} stocks")
        
    except Exception as e:
        print(f"Error saving results: {e}")
        return

if __name__ == "__main__":
    main()