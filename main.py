import pandas as pd
import os
from step1a import collect_eps_data
from step1b import screen_eps_growth
from step2 import filter_debt_to_earnings
from step3 import filter_roe
from step4 import filter_rotc
from step5 import filter_fcf
from old_code.step6 import filter_rore
from old_code.step7 import filter_earnings_yield

def main():
    # Configurable parameters
    end_year = 2022  # Change this to analyze a different year
    look_back_period = 10  # Years to look back for multi-year analyses
    min_years_increase = 8

    # EPS screening parameters
    min_years_increase = 8
    min_total_growth = 0

    # Debt-to-earnings parameters
    max_debt_to_earnings = 5

    # ROE parameters
    min_roe = 0.15
    min_roe_years = 7

    # ROTC parameters
    min_rotc = 0.12
    min_rotc_years = 7

    # FCF parameters
    min_fcf_years = 3

    # RORE parameters
    min_rore = 0.12
    min_rore_years = 2

    # Calculate years for EPS data
    years = range(end_year - look_back_period + 1, end_year + 1)

    # Load initial tickers from CSV files
    csv_files = {
        'AMEX': 'US stock tickers/amex_screener.csv',
        'NASDAQ': 'US stock tickers/nasdaq_screener.csv',
        'NYSE': 'US stock tickers/nyse_screener.csv'
    }
    initial_tickers = []
    for exchange, path in csv_files.items():
        if not os.path.exists(path):
            print(f"Warning: {path} not found")
            continue
        df = pd.read_csv(path)
        tickers = df['Symbol'].tolist()
        initial_tickers.extend(tickers)
    initial_tickers = list(set(initial_tickers))  # Remove duplicates
    print(f"Loaded {len(initial_tickers)} unique tickers")

    # Step 1a: Collect EPS data
    eps_df = collect_eps_data(initial_tickers, years)

    # Step 1b: Screen EPS growth
    eps_tickers, eps_df = screen_eps_growth(eps_df, min_years_increase, min_total_growth)
    print(f"After EPS screening: {len(eps_tickers)} stocks")

    # Initialize Excel writer
    excel_file = f'Results/Results_{end_year}.xlsx'
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        eps_df.to_excel(writer, sheet_name='EPS_Screening', index=False)
        progress = [
            {'Step': 'Initial', 'Number of Stocks': len(initial_tickers)},
            {'Step': 'After EPS Screening', 'Number of Stocks': len(eps_tickers)}
        ]

        # Step 2: Debt-to-earnings filter
        debt_tickers, debt_df = filter_debt_to_earnings(eps_tickers, end_year, max_debt_to_earnings)
        debt_df.to_excel(writer, sheet_name='Debt_Filter', index=False)
        progress.append({'Step': 'After Debt Filter', 'Number of Stocks': len(debt_tickers)})
        print(f"After debt filter: {len(debt_tickers)} stocks")

        # Step 3: ROE filter
        roe_tickers, roe_df = filter_roe(debt_tickers, end_year, look_back_period, min_roe, min_roe_years)
        roe_df.to_excel(writer, sheet_name='ROE_Filter', index=False)
        progress.append({'Step': 'After ROE Filter', 'Number of Stocks': len(roe_tickers)})
        print(f"After ROE filter: {len(roe_tickers)} stocks")

        # Step 4: ROTC filter
        rotc_tickers, rotc_df = filter_rotc(roe_tickers, end_year, look_back_period, min_rotc, min_rotc_years)
        rotc_df.to_excel(writer, sheet_name='ROTC_Filter', index=False)
        progress.append({'Step': 'After ROTC Filter', 'Number of Stocks': len(rotc_tickers)})
        print(f"After ROTC filter: {len(rotc_tickers)} stocks")

        # Step 5: FCF filter
        fcf_tickers, fcf_df = filter_fcf(rotc_tickers, end_year, min_fcf_years)
        fcf_df.to_excel(writer, sheet_name='FCF_Filter', index=False)
        progress.append({'Step': 'After FCF Filter', 'Number of Stocks': len(fcf_tickers)})
        print(f"After FCF filter: {len(fcf_tickers)} stocks")

        # Step 6: RORE filter
        rore_tickers, rore_df = filter_rore(fcf_tickers, end_year, min_rore, min_rore_years)
        rore_df.to_excel(writer, sheet_name='RORE_Filter', index=False)
        progress.append({'Step': 'After RORE Filter', 'Number of Stocks': len(rore_tickers)})
        print(f"After RORE filter: {len(rore_tickers)} stocks")

        # Step 7: Earnings yield filter
        final_tickers, ey_df = filter_earnings_yield(rore_tickers, end_year)
        ey_df.to_excel(writer, sheet_name='Earnings_Yield', index=False)
        progress.append({'Step': 'Final Qualifying Stocks', 'Number of Stocks': len(final_tickers)})
        print(f"Final qualifying stocks: {len(final_tickers)}")

        # Write final qualifying stocks
        final_df = pd.DataFrame({'Ticker': final_tickers})
        final_df.to_excel(writer, sheet_name='Final_Qualifying_Stocks', index=False)

        # Write progress summary
        progress_df = pd.DataFrame(progress)
        progress_df.to_excel(writer, sheet_name='Progress', index=False)

    print(f"Analysis complete. Results saved to {excel_file}")

if __name__ == "__main__":
    main()