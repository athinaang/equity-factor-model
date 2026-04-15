# Equity Factor Model

A quantitative equity factor model that ranks S&P 500 stocks based on 
Value, Momentum and Quality factors.

## Results
- Portfolio Return: +91.8% (2021-2025)
- SPY Return: +69.4%
- Sharpe Ratio: 1.96 vs 1.26
- Max Drawdown: -2.7% vs -8.2%

## Factors
- **Value**: P/E ratio (lower is better)
- **Momentum**: 12-1 month price return
- **Quality**: Return on Equity (ROE)

## How it works
1. Downloads S&P 500 data from yfinance
2. Calculates and normalizes 3 factor scores
3. Builds equal-weighted portfolio of top 30 stocks
4. Rebalances every 6 months
5. Backtests against S&P 500 benchmark

## Libraries
- `yfinance` - stock data
- `pandas` - data manipulation
- `numpy` - calculations
- `matplotlib` - visualization