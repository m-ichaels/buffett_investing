import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
import datetime as dt

PREDICTIONS = 'PredictionsDatabase.xlsx'
N_TOP = 10

def top_n_performance(top_tickers=N_TOP):

    file = pd.ExcelFile(PREDICTIONS)
    sheets = file.sheet_names

    all_top10_returns = []
    all_spy_returns = []

    for s in sheets:
        print(f'Acquiring data for {s}')
        print(s)

        df = pd.read_excel(file, sheet_name=sheets[0])
        top10 = df.head(N_TOP)

        start = pd.to_datetime(top10.iloc[0]['period_start'])
        end = pd.to_datetime(top10.iloc[0]['period_end'])

        if end > dt.datetime.now():
            end = dt.datetime.now()
        
        # initatilise empty dataframe
        price_changes = pd.DataFrame()

        for t in top10['ticker']:
            prices = yf.download(t,start=start,end=end, progress=False)['Close']
            returns = prices.pct_change().fillna(0)
            price_changes[t] = returns
        
        # get benchmark data
        avg_top10 = price_changes.mean(axis=1)
        spy = yf.download('SPY', start=start, end=end, progress=False)['Close']
        spy_prices = spy.pct_change().fillna(0)
        spy_returns = spy_prices.reindex(avg_top10.index).fillna(0)

        all_top10_returns.append(avg_top10)
        all_spy_returns.append(spy_returns)

    full_top10 = pd.concat(all_top10_returns)
    full_spy = pd.concat(all_spy_returns)

    cum_top10 = (1 + full_top10).cumprod() - 1
    cum_spy = (1 + full_spy).cumprod() - 1

    plt.figure(figsize=(12,6))
    plt.plot(cum_top10)
    plt.plot(cum_spy)
    plt.legend(['SharpEdge Top 10', 'S&P 500'])

    return

top_n_performance()