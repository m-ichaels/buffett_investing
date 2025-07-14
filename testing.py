import yfinance as yf

# Fetch net income for a stock
stock = yf.Ticker('AAPL')  # Replace 'AAPL' with your ticker
income_stmt = stock.income_stmt

# Print the income statement to explore the data
print("Income Statement:")
print(income_stmt)

# Extract net income for the fiscal year ending 2021-09-30
net_income_2021 = income_stmt.loc['Net Income']['2021-09-30']
print(f"Net Income for 2021: {net_income_2021}")