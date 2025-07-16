import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
import datetime as dt
import os

RESULTS_FILE = os.path.join('Results', '2022.xlsx')
N_TOP = 10

def load_combined_results():
    """Load the combined results from step10.py output."""
    try:
        df = pd.read_excel(RESULTS_FILE, sheet_name='Combined_Methods_Filtered_Stocks')
        print(f"Loaded {len(df)} stocks from combined methods results")
        return df
    except FileNotFoundError:
        print(f"Error: {RESULTS_FILE} not found. Make sure step10.py has been run.")
        return None
    except Exception as e:
        print(f"Error reading {RESULTS_FILE}: {e}")
        return None

def analyze_performance(top_tickers=N_TOP):
    """Analyze the performance of top stocks from step10.py results."""
    
    # Load the combined results
    df = load_combined_results()
    if df is None:
        return
    
    # Get top N stocks by average return
    top_stocks = df.head(top_tickers)
    
    # Set date range (start of 2023 to start of 2024)
    start_date = dt.datetime(2023, 1, 1)
    end_date = dt.datetime(2024, 1, 1)
    
    print(f"\nAnalyzing performance from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Top {top_tickers} stocks by projected average return:")
    
    for i, (_, row) in enumerate(top_stocks.iterrows(), 1):
        print(f"{i:2d}. {row['Ticker']}: {row['Average_Return']:.1%} projected return")
    
    # Initialize empty dataframe for price changes
    price_changes = pd.DataFrame()
    successful_tickers = []
    failed_tickers = []
    
    # Download price data for each ticker
    for ticker in top_stocks['Ticker']:
        try:
            print(f"Downloading data for {ticker}...")
            prices = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=False)['Close']
            
            if len(prices) > 0:
                returns = prices.pct_change().fillna(0)
                price_changes[ticker] = returns
                successful_tickers.append(ticker)
            else:
                failed_tickers.append(ticker)
                print(f"  Warning: No data found for {ticker}")
                
        except Exception as e:
            failed_tickers.append(ticker)
            print(f"  Error downloading {ticker}: {e}")
    
    if price_changes.empty:
        print("No price data could be downloaded for any tickers.")
        return
    
    print(f"\nSuccessfully downloaded data for {len(successful_tickers)} out of {len(top_stocks)} tickers")
    if failed_tickers:
        print(f"Failed tickers: {', '.join(failed_tickers)}")
    
    # Calculate portfolio average returns
    avg_portfolio_returns = price_changes.mean(axis=1)
    
    # Get benchmark data (S&P 500)
    print("Downloading S&P 500 benchmark data...")
    try:
        spy = yf.download('SPY', start=start_date, end=end_date, progress=False, auto_adjust=False)['Close']
        spy_returns = spy.pct_change().fillna(0)
        
        # Align dates
        spy_returns = spy_returns.reindex(avg_portfolio_returns.index).fillna(0)
        
    except Exception as e:
        print(f"Error downloading SPY data: {e}")
        return
    
    # Calculate cumulative returns
    cum_portfolio = (1 + avg_portfolio_returns).cumprod() - 1
    cum_spy = (1 + spy_returns).cumprod() - 1
    
    # Calculate performance metrics - FIX: Extract scalar values properly
    portfolio_total_return = float(cum_portfolio.iloc[-1])
    spy_total_return = float(cum_spy.iloc[-1])
    outperformance = portfolio_total_return - spy_total_return
    
    # Calculate volatility (annualized)
    portfolio_volatility = float(avg_portfolio_returns.std() * (252 ** 0.5))
    spy_volatility = float(spy_returns.std() * (252 ** 0.5))
    
    # Calculate Sharpe ratio (assuming 0% risk-free rate)
    portfolio_sharpe = float((avg_portfolio_returns.mean() * 252) / portfolio_volatility)
    spy_sharpe = float((spy_returns.mean() * 252) / spy_volatility)
    
    # Print performance summary
    print(f"\n{'='*60}")
    print(f"PERFORMANCE SUMMARY ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})")
    print(f"{'='*60}")
    print(f"SharpEdge Top {len(successful_tickers)} Portfolio:")
    print(f"  Total Return: {portfolio_total_return:.1%}")
    print(f"  Annualized Volatility: {portfolio_volatility:.1%}")
    print(f"  Sharpe Ratio: {portfolio_sharpe:.2f}")
    print(f"\nS&P 500 Benchmark:")
    print(f"  Total Return: {spy_total_return:.1%}")
    print(f"  Annualized Volatility: {spy_volatility:.1%}")
    print(f"  Sharpe Ratio: {spy_sharpe:.2f}")
    print(f"\nOutperformance: {outperformance:.1%}")
    print(f"Risk-Adjusted Outperformance: {portfolio_sharpe - spy_sharpe:.2f}")
    
    # Individual stock performance
    print(f"\nIndividual Stock Performance:")
    individual_returns = {}
    for ticker in successful_tickers:
        stock_cum_return = float((1 + price_changes[ticker]).cumprod().iloc[-1] - 1)
        individual_returns[ticker] = stock_cum_return
    
    # Sort by performance
    sorted_stocks = sorted(individual_returns.items(), key=lambda x: x[1], reverse=True)
    
    for i, (ticker, return_val) in enumerate(sorted_stocks, 1):
        print(f"{i:2d}. {ticker}: {return_val:.1%}")
    
    # Plot results
    plt.figure(figsize=(12, 8))
    plt.plot(cum_portfolio.index, cum_portfolio.values * 100, linewidth=2, label=f'SharpEdge Top {len(successful_tickers)}')
    plt.plot(cum_spy.index, cum_spy.values * 100, linewidth=2, label='S&P 500 (SPY)')
    
    plt.title(f'SharpEdge Portfolio vs S&P 500 Performance\n({start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")})', fontsize=14)
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Cumulative Return (%)', fontsize=12)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    # Add performance text box
    textstr = f'Portfolio: {portfolio_total_return:.1%}\nS&P 500: {spy_total_return:.1%}\nOutperformance: {outperformance:.1%}'
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    plt.text(0.02, 0.98, textstr, transform=plt.gca().transAxes, fontsize=10,
             verticalalignment='top', bbox=props)
    
    plt.show()
    
    # Show which stocks contributed most to performance
    print(f"\nBest performers vs worst performers:")
    best_performer = sorted_stocks[0]
    worst_performer = sorted_stocks[-1]
    print(f"Best: {best_performer[0]} ({best_performer[1]:.1%})")
    print(f"Worst: {worst_performer[0]} ({worst_performer[1]:.1%})")
    
    # Show correlation with projected returns
    print(f"\nProjected vs Actual Return Comparison:")
    for ticker in successful_tickers:
        actual_return = individual_returns[ticker]
        projected_return = float(df[df['Ticker'] == ticker]['Average_Return'].iloc[0])
        print(f"{ticker}: Projected {projected_return:.1%}, Actual {actual_return:.1%}")

if __name__ == "__main__":
    analyze_performance(N_TOP)