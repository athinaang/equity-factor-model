import yfinance as yf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import time
import urllib.request
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Step 0: Get tickers from Wikipedia
url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req)
tables = pd.read_html(response)
df = tables[0]
tickers = df['Symbol'].tolist()

os.makedirs("data", exist_ok=True)

# Step 1a: Fundamentals
if os.path.exists("data/fundamentals.csv"):
    print("Loading fundamentals from cache...")
    fundamentals_df = pd.read_csv("data/fundamentals.csv")
else:
    print("Fetching fundamentals from yfinance...")
    results = []
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            pe = info.get('trailingPE')
            roe = info.get('returnOnEquity')
            results.append({'Ticker': ticker, 'PE': pe, 'ROE': roe})
            time.sleep(0.5)
        except Exception as e:
            print(f"ticker {ticker} not found: {e}")
    fundamentals_df = pd.DataFrame(results)
    fundamentals_df.to_csv("data/fundamentals.csv", index=False)

# Step 1b: Prices
if os.path.exists("data/prices.csv"):
    print("Loading prices from cache...")
    close_prices = pd.read_csv("data/prices.csv", index_col=0, parse_dates=True)
    close_prices.index = pd.to_datetime(close_prices.index).astype('datetime64[ns]')
else:
    print("Fetching prices from yfinance...")
    prices = yf.download(tickers, start='2020-01-01')
    close_prices = prices['Close']
    close_prices.to_csv("data/prices.csv")

# Step 1c: SPY benchmark prices
if os.path.exists("data/spy.csv"):
    print("Loading SPY from cache...")
    spy_prices = pd.read_csv("data/spy.csv", index_col=0, parse_dates=True)
    spy_prices.index = pd.to_datetime(spy_prices.index).astype('datetime64[ns]')
else:
    print("Fetching SPY from yfinance...")
    spy_data = yf.download('SPY', start='2020-01-01')
    spy_prices = spy_data['Close']
    spy_prices.to_csv("data/spy.csv")

# Step 1d: Current momentum
price_recent = close_prices.iloc[-21]
price_12m = close_prices.iloc[-252]
momentum = (price_recent / price_12m) - 1
momentum_df = pd.DataFrame(momentum, columns=['Momentum'])
momentum_df.index.name = 'Ticker'
momentum_df = momentum_df.reset_index()
momentum_df.to_csv('data/momentum.csv', index=False)

# Step 2: Merge and normalize
df_combined = pd.merge(fundamentals_df, momentum_df, on='Ticker')
df_combined = df_combined.dropna()
df_combined['PE_score'] = 1 - df_combined['PE'].rank(pct=True)
df_combined['ROE_score'] = df_combined['ROE'].rank(pct=True)
df_combined['Momentum_score'] = df_combined['Momentum'].rank(pct=True)

# Step 3: Composite score
df_combined['Composite_score'] = df_combined[['PE_score', 'ROE_score', 'Momentum_score']].mean(axis=1)

# Step 4: Rank and select top 30
df_sorted = df_combined.sort_values(by='Composite_score', ascending=False)
portfolio = df_sorted.head(30)
print("Current portfolio:")
print(portfolio[['Ticker', 'Composite_score']])
portfolio.to_csv('data/portfolio.csv', index=False)

# Step 5: Backtest
portfolio_value = 10000
spy_value = 10000
portfolio_history = []
portfolio_returns = []
spy_returns = []
previous_tickers = []  # 👈 NEW: track previous portfolio
rebalance_dates = pd.date_range(start='2021-01-01', end='2025-07-01', freq='6ME')

for i in range(len(rebalance_dates) - 1):
    start_date = rebalance_dates[i]
    end_date = rebalance_dates[i + 1]

    # A: Get index positions for dates
    start_idx = close_prices.index.get_indexer([start_date], method='nearest')[0]
    end_idx = close_prices.index.get_indexer([end_date], method='nearest')[0]

    # B: Momentum at start_date
    price_recent = close_prices.iloc[start_idx]
    price_12m = close_prices.iloc[start_idx - 252]
    momentum = (price_recent / price_12m) - 1

    # C: SPY benchmark
    spy_start_idx = spy_prices.index.get_indexer([start_date], method='nearest')[0]
    spy_end_idx = spy_prices.index.get_indexer([end_date], method='nearest')[0]
    spy_start = spy_prices.iloc[spy_start_idx].values[0]
    spy_end = spy_prices.iloc[spy_end_idx].values[0]
    spy_return = (spy_end / spy_start) - 1
    spy_value = spy_value * (1 + spy_return)
    spy_returns.append(spy_return)

    # D: Scores and top 30
    momentum_df = pd.DataFrame(momentum, columns=['Momentum'])
    momentum_df.index.name = 'Ticker'
    momentum_df = momentum_df.reset_index()
    df_combined = pd.merge(fundamentals_df, momentum_df, on='Ticker')
    df_combined = df_combined.dropna()
    df_combined['PE_score'] = 1 - df_combined['PE'].rank(pct=True)
    df_combined['ROE_score'] = df_combined['ROE'].rank(pct=True)
    df_combined['Momentum_score'] = df_combined['Momentum'].rank(pct=True)
    df_combined['Composite_score'] = df_combined[['PE_score', 'ROE_score', 'Momentum_score']].mean(axis=1)
    df_sorted = df_combined.sort_values(by='Composite_score', ascending=False)
    top30 = df_sorted.head(30)
    top30_tickers = top30['Ticker'].tolist()

    # E: Transaction costs 
    if previous_tickers:
        prev = set(previous_tickers)
        curr = set(top30_tickers)
        stocks_left = prev - curr
        stocks_entered = curr - prev
        trades = len(stocks_left) + len(stocks_entered)
        transaction_cost = (trades / 30) * 0.002
        portfolio_value = portfolio_value * (1 - transaction_cost)
        print(f"  Trades: {trades} stocks | TC: {transaction_cost:.2%}")
    previous_tickers = top30_tickers  

    # F: Stock returns start_date to end_date
    price_start = close_prices.iloc[start_idx][top30_tickers]
    price_end = close_prices.iloc[end_idx][top30_tickers]
    stock_returns = (price_end / price_start) - 1

    # G: Update portfolio value
    portfolio_return = stock_returns.mean()
    portfolio_value = portfolio_value * (1 + portfolio_return)
    portfolio_returns.append(portfolio_return)

    # H: Save to history
    portfolio_history.append({
        'Date': end_date,
        'Value': portfolio_value,
        'SPY_Value': spy_value
    })
    print(f"{start_date.date()} → {end_date.date()} | Portfolio: ${portfolio_value:,.0f} | SPY: ${spy_value:,.0f}")

# Step 6: Performance metrics
portfolio_df = pd.DataFrame(portfolio_history)
portfolio_df.to_csv("data/backtest.csv", index=False)

# Sharpe Ratio
sharpe_portfolio = np.mean(portfolio_returns) / np.std(portfolio_returns) * np.sqrt(2)
sharpe_spy = np.mean(spy_returns) / np.std(spy_returns) * np.sqrt(2)

# Max Drawdown
rolling_max = portfolio_df['Value'].cummax()
drawdown = (portfolio_df['Value'] - rolling_max) / rolling_max
max_drawdown = drawdown.min()

rolling_max_spy = portfolio_df['SPY_Value'].cummax()
drawdown_spy = (portfolio_df['SPY_Value'] - rolling_max_spy) / rolling_max_spy
max_drawdown_spy = drawdown_spy.min()

print("\n========== PERFORMANCE SUMMARY ==========")
print(f"Final Portfolio Value:  ${portfolio_value:,.0f}")
print(f"Final SPY Value:        ${spy_value:,.0f}")
print(f"Outperformance:         ${portfolio_value - spy_value:,.0f}")
print(f"Sharpe Ratio:           Portfolio {sharpe_portfolio:.2f} | SPY {sharpe_spy:.2f}")
print(f"Max Drawdown:           Portfolio {max_drawdown:.1%} | SPY {max_drawdown_spy:.1%}")
print("=========================================")

# Step 7: Visualization
plt.figure(figsize=(12, 6))
plt.plot(portfolio_df['Date'], portfolio_df['Value'], label='Portfolio', color='blue', linewidth=2)
plt.plot(portfolio_df['Date'], portfolio_df['SPY_Value'], label='SPY', color='orange', linewidth=2)
plt.title('Portfolio vs SPY Performance')
plt.xlabel('Date')
plt.ylabel('Portfolio Value ($)')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig('data/backtest_chart.png')
plt.show()