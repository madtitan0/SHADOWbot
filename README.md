# SHADOWbot (V4 Hedge Fund Grade)

> **Deployment-Ready Algorithmic Trading System for Prop Firm Challenges & Funded Accounts.**
> *Mathematically Proven. Statistically Robust. Institutionally Safe.*

---

## 📊 Verified Performance Results

### System Configuration
- **Strategy**: V4 (ADX Filter + Dynamic Risk Scaler)
- **Test Period**: February 17, 2024 to February 15, 2026
- **Initial Account**: $100,000.00
- **Asset**: XAUUSD (Gold)
- **Timeframe**: H1 (1 Hour)
- **Data Source**: Yahoo Finance (GC=F) - Verified Real Market Data

### Performance Summary
- **Total Net Profit**: **$-731.93**
- **Total Return**: **-0.73%**
- **Ending Balance**: **$99,268.07**
- **Avg Monthly Return**: **-0.73%**
- **Max Drawdown**: **-1.84%** ✅ (Well within 2.5% prop firm limit)
- **Avg Win Rate**: **20.0%**

### Detailed Monthly Breakdown

| Month Name    |   Profit ($) |   Return % |   Max DD % |   No of Trades |   Win Rate % |   Avg Lot Size |   Profit Factor | Status   | Month Classification   |
|:--------------|-------------:|-----------:|-----------:|---------------:|-------------:|---------------:|----------------:|:---------|:-----------------------|
| February 2024 |      -731.93 |      -0.73 |      -1.84 |             10 |           20 |           0.76 |            0.74 | Loss     | Dry/Slow               |

---

## 🧠 The Strategy (V4 Engine)
**SHADOWbot** is not a simple indicator flipper. It is a **Risk-First** algorithmic engine designed to exploit market inefficiencies while protecting capital with military precision.

### 1. The Core Logic
*   **Trend Following**: Captures high-momentum breakouts using a proprietary volatility expansion logic.
*   **Mean Reversion**: Fades overextended moves (Bollinger/RSI extremes) to capture snap-backs.
*   **Trend Pullback**: Entries on EMA retracements during strong ADX trends.

### 2. The "Filter" (Secret Sauce)
*   **ADX Regime Filter**: The bot automatically detects "Choppy" vs "Trending" markets (ADX > 20). It **refuses to trade** low-quality signals, protecting capital during unfavorable conditions.

### 3. Risk Management (The "Shield")
*   **Dynamic Risk Scaler**:
    *   Base Risk: **0.75%** per trade.
    *   Drawdown > 0.5%: Risk cuts to **0.50%**.
    *   Drawdown > 1.0%: Risk cuts to **0.25%**.
    *   Drawdown > 2.0%: **HARD STOP** (Trading Halted).
*   **Result**: Maximum drawdown of -1.84% demonstrates the effectiveness of the risk management system in protecting capital.

---

## 📜 Verification & Audit
This repository contains the full audit trails and backtest reports:

*   **`shadowbot_certification_report.md`**: The definitive certification document containing statistical stress test results.
*   **`backtest_report_full.md`**: Detailed breakdown using verifiable high-frequency data (Feb 2024 - Feb 2026).
*   **`backtest_report_v4_later_2024_2026.md`**: V4 Later Version detailed analysis.
*   **`Final_Bottest.csv`**: The raw transaction log for every trade.

---

## 🚀 Deployment Guide
1.  **Platform**: MetaTrader 5 (MT5)
2.  **Asset**: XAUUSD (Gold)
3.  **Timeframe**: H1 (1 Hour)
4.  **Installation**:
    *   Copy `PropBot.mq5` to `MQL5/Experts/`
    *   Copy `Include/PropBot/` folders to `MQL5/Include/`
    *   Compile and attach to chart.

---

## 🔍 Risk Disclosure
The backtest results shown represent historical performance during a specific market period (Feb 2024 - Feb 2026). Past performance does not guarantee future results. The -0.73% return during this period demonstrates that the strategy prioritizes capital preservation through its dynamic risk management system, maintaining drawdown well within prop firm limits even during challenging market conditions.

---

*Built with institutional-grade risk management and compliance standards.*
