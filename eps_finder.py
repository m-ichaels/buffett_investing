import pandas as pd
import yfinance as yf
import time
import os

# Define the path to the CSV file inside the "US stock tickers" folder
csv_path = os.path.join('US stock tickers', 'nasdaq_screener.csv')

# Read the CSV file containing NYSE tickers
df = pd.read_csv(csv_path)
tickers = df['Symbol'].tolist()

results = []

for ticker in tickers:
    print(f"Processing {ticker}")
    try:
        stock = yf.Ticker(ticker)
        income_stmt = stock.income_stmt
        if 'Diluted EPS' in income_stmt.index:
            eps_series = income_stmt.loc['Diluted EPS']
            years = eps_series.index.map(lambda x: x.year)
            eps_2021 = eps_series[years == 2021].values[0] if any(years == 2021) else None
            eps_2022 = eps_series[years == 2022].values[0] if any(years == 2022) else None
        else:
            eps_2021 = None
            eps_2022 = None
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        eps_2021 = None
        eps_2022 = None
    results.append({'Ticker': ticker, 'EPS_2021': eps_2021, 'EPS_2022': eps_2022})
    time.sleep(0.2)  # Delay to prevent rate limiting

# Convert results to DataFrame
results_df = pd.DataFrame(results)

# Save to CSV in the current working directory
results_df.to_csv('nasdaq_data.csv', index=False)

print("EPS data collection complete. Results saved to 'nasdaq_data.csv'.")