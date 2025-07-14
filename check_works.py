import pandas as pd
import yfinance as yf
import time
import os

def get_pe_ratios(tickers, years=[2021, 2022]):
    results = []
    
    for ticker in tickers:
        print(f"Processing {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            # Get stock info for name and to check if it's a valid common stock
            info = stock.info
            name = info.get('shortName', '')
            
            # Skip preferred shares or non-standard securities (e.g., BCV^A, PCG^A)
            if '^' in ticker or 'preferred' in name.lower():
                print(f"Skipping {ticker}: Preferred share or non-standard security")
                results.append({
                    'Symbol': ticker,
                    'Name': name,
                    'P/E 2021': None,
                    'P/E 2022': None
                })
                continue

            # Fetch historical prices (yearly average closing price)
            pe_ratios = {}
            for year in years:
                start_date = f"{year}-01-01"
                end_date = f"{year}-12-31"
                hist = stock.history(start=start_date, end=end_date, interval="1mo")
                
                if hist.empty:
                    print(f"No price data for {ticker} in {year}")
                    pe_ratios[f"P/E {year}"] = None
                    continue
                
                # Calculate average closing price for the year
                avg_price = hist['Close'].mean()
                
                # Fetch EPS
                try:
                    eps = None
                    if 'trailingEps' in info and info['trailingEps'] is not None:
                        # Use trailing EPS as a proxy (not ideal for specific years)
                        eps = info['trailingEps']
                    else:
                        # Attempt to get EPS from quarterly financials
                        financials = stock.financials
                        if not financials.empty:
                            for date in financials.columns:
                                if date.year == year:
                                    eps_data = financials.loc['Diluted EPS', date]
                                    if not pd.isna(eps_data):
                                        eps = eps_data
                                        break
                    
                    if eps is None or eps == 0:
                        print(f"No valid EPS data for {ticker} in {year}")
                        pe_ratios[f"P/E {year}"] = None
                    else:
                        pe_ratio = avg_price / eps
                        pe_ratios[f"P/E {year}"] = round(pe_ratio, 2) if pe_ratio > 0 else None
                except Exception as e:
                    print(f"Error fetching EPS for {ticker} in {year}: {e}")
                    pe_ratios[f"P/E {year}"] = None
            
            results.append({
                'Symbol': ticker,
                'Name': name,
                'P/E 2021': pe_ratios.get('P/E 2021'),
                'P/E 2022': pe_ratios.get('P/E 2022')
            })
        
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            results.append({
                'Symbol': ticker,
                'Name': '',
                'P/E 2021': None,
                'P/E 2022': None
            })
        
        time.sleep(0.2)  # Avoid rate limits

    return results

try:
    # Define the path to amex_screener.csv in the US stock tickers subfolder
    csv_path = os.path.join('US stock tickers', 'amex_screener.csv')
    
    # Check if the file exists
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Could not find {csv_path}. Please ensure the file is in the 'US stock tickers' folder.")
    
    # Read the AMEX screener CSV
    df = pd.read_csv(csv_path)
    tickers = df['Symbol'].tolist()
    
    # Fetch P/E ratios
    results = get_pe_ratios(tickers)
    
    # Create DataFrame and save to CSV
    result_df = pd.DataFrame(results)
    result_df.to_csv('pe_ratios_amex.csv', index=False)
    print(f"Saved {len(result_df)} P/E ratios to pe_ratios_amex.csv")

except Exception as e:
    print(f"Error processing data: {e}")