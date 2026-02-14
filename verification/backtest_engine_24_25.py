import yfinance as yf
import pandas as pd
import numpy as np

# --- Configuration ---
class Config:
    SYMBOLS = ["GC=F"] 
    # Exact Date Range for 2024-2025
    START_DATE = "2024-01-01"
    END_DATE = "2026-01-01" # Covers full year 2025
    INTERVAL = "1h"    
    
    RISK_PERCENT = 0.005 # 0.5% Base Risk
    INITIAL_BALANCE = 100000.0
    SPREAD_COST = 0.20
    ATR_PERIOD = 14
    
    # H1 Sizing
    SL_ATR_MULT = 1.5 
    TP_ATR_MULT = 2.5 
    
    # V3 Logic
    MIN_ATR = 1.0 
    USE_MEAN_REV = True
    USE_PULLBACK = True
    USE_HTF_FILTER = True # Enforce Trend

class Backtester:
    def __init__(self, symbol):
        self.symbol = symbol
        self.data = None
        self.balance = Config.INITIAL_BALANCE
        self.equity_curve = []
        self.trade_log = []
        
    def fetch_data(self):
        print(f"Fetching data from {Config.START_DATE} to {Config.END_DATE}...")
        self.data = yf.download(self.symbol, start=Config.START_DATE, end=Config.END_DATE, interval=Config.INTERVAL, progress=False)
        if self.data.empty:
            print(f"Warning: No data found for {self.symbol}")
            return
            
        # Indicators
        self.data['ATR'] = self.calculate_atr(self.data, Config.ATR_PERIOD)
        self.data['PrevHigh'] = self.data['High'].shift(2)
        self.data['PrevLow'] = self.data['Low'].shift(2)
        
        # V2
        self.data['SMA_20'] = self.data['Close'].rolling(20).mean()
        self.data['StdDev'] = self.data['Close'].rolling(20).std()
        self.data['UpperBB'] = self.data['SMA_20'] + (2.5 * self.data['StdDev'])
        self.data['LowerBB'] = self.data['SMA_20'] - (2.5 * self.data['StdDev'])
        
        self.data['EMA_Fast'] = self.data['Close'].ewm(span=9, adjust=False).mean()
        self.data['EMA_Slow'] = self.data['Close'].ewm(span=21, adjust=False).mean()
        
        # V3
        self.data['EMA_50'] = self.data['Close'].ewm(span=50, adjust=False).mean()

    def calculate_atr(self, df, period):
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(period).mean()

    def run_sim(self):
        self.fetch_data()
        if self.data is None or self.data.empty: return

        position = 0 
        entry_price = 0
        current_sl_dist = 0
        current_tp_dist = 0
        
        hwm = Config.INITIAL_BALANCE
        spread = Config.SPREAD_COST
        min_atr = Config.MIN_ATR

        for i in range(55, len(self.data)):
            timestamp = self.data.index[i]
            current_open = self.data['Open'].iloc[i].item()
            curr_high = self.data['High'].iloc[i].item()
            curr_low = self.data['Low'].iloc[i].item()
            curr_close = self.data['Close'].iloc[i].item()
            
            # --- V3 Dynamic Risk Scaling ---
            if self.balance > hwm: hwm = self.balance
            current_dd_pct = (hwm - self.balance) / hwm * 100.0
            risk_modifier = 1.0
            # Strict V3 Scaling
            if current_dd_pct >= 1.0: risk_modifier = 0.5
            if current_dd_pct >= 1.5: risk_modifier = 0.25
            if current_dd_pct >= 2.0: risk_modifier = 0.1
            
            # Indicators
            idx_prev = i - 1
            close_prev = self.data['Close'].iloc[idx_prev].item()
            open_prev = self.data['Open'].iloc[idx_prev].item()
            high_prev_2 = self.data['High'].iloc[i-2].item()
            low_prev_2 = self.data['Low'].iloc[i-2].item()
            atr = self.data['ATR'].iloc[idx_prev].item()
            
            upper_bb = self.data['UpperBB'].iloc[idx_prev].item()
            lower_bb = self.data['LowerBB'].iloc[idx_prev].item()
            ema_fast = self.data['EMA_Fast'].iloc[idx_prev].item()
            ema_slow = self.data['EMA_Slow'].iloc[idx_prev].item()
            ema_50_htf = self.data['EMA_50'].iloc[idx_prev].item()

            # Manage Open Trade
            if position != 0:
                pnl = 0
                exit_price = 0
                triggered = False
                
                sl_price = entry_price - current_sl_dist if position == 1 else entry_price + current_sl_dist
                tp_price = entry_price + current_tp_dist if position == 1 else entry_price - current_tp_dist
                
                if position == 1:
                    if curr_low <= sl_price:
                        exit_price = sl_price
                        triggered = True
                    elif curr_high >= tp_price:
                        exit_price = tp_price
                        triggered = True
                else: 
                    if curr_high >= sl_price:
                        exit_price = sl_price
                        triggered = True
                    elif curr_low <= tp_price:
                        exit_price = tp_price
                        triggered = True
                        
                if triggered:
                    risk_amt = self.balance * (Config.RISK_PERCENT * risk_modifier)
                    units = risk_amt / current_sl_dist
                    
                    raw_diff = (exit_price - entry_price) if position == 1 else (entry_price - exit_price)
                    pnl = raw_diff * units
                    
                    self.balance += pnl
                    self.trade_log.append({
                        "ExitTime": timestamp,
                        "PnL": pnl,
                        "Result": "Win" if pnl > 0 else "Loss"
                    })
                    position = 0

            # Check Entry
            if position == 0:
                signal_found = False
                trade_atr = atr if atr > min_atr else min_atr
                
                can_buy = close_prev > ema_50_htf if Config.USE_HTF_FILTER else True
                can_sell = close_prev < ema_50_htf if Config.USE_HTF_FILTER else True
                
                # 1. Momentum
                if atr >= min_atr:
                    if close_prev > high_prev_2 and close_prev > open_prev and can_buy:
                        entry_price = current_open + spread
                        position = 1
                        signal_found = True
                    elif close_prev < low_prev_2 and close_prev < open_prev and can_sell:
                        entry_price = current_open - spread
                        position = -1
                        signal_found = True
                        
                # 2. Mean Rev (Counter Trend allowed if extreme? No, enforcing HTF Filter strictly for V3)
                if not signal_found and Config.USE_MEAN_REV:
                    if close_prev > upper_bb and can_sell:
                        entry_price = current_open - spread
                        position = -1
                        signal_found = True
                    elif close_prev < lower_bb and can_buy:
                        entry_price = current_open + spread
                        position = 1
                        signal_found = True
                
                # 3. Pullback
                if not signal_found and Config.USE_PULLBACK:
                    if ema_fast > ema_slow and can_buy:
                        low_prev = self.data['Low'].iloc[idx_prev].item()
                        if low_prev <= ema_fast and close_prev > ema_fast:
                            entry_price = current_open + spread
                            position = 1
                            signal_found = True
                    elif ema_fast < ema_slow and can_sell:
                        high_prev = self.data['High'].iloc[idx_prev].item()
                        if high_prev >= ema_fast and close_prev < ema_fast:
                            entry_price = current_open - spread
                            position = -1
                            signal_found = True
                            
                if signal_found:
                    entry_time = timestamp
                    current_sl_dist = trade_atr * Config.SL_ATR_MULT
                    current_tp_dist = trade_atr * Config.TP_ATR_MULT

            self.equity_curve.append({"Time": timestamp, "Equity": self.balance})

    def generate_report(self):
        if not self.trade_log: return

        df_trades = pd.DataFrame(self.trade_log)
        df_trades['ExitTime'] = pd.to_datetime(df_trades['ExitTime'])
        df_trades.set_index('ExitTime', inplace=True)
        
        # Monthly Stats
        monthly = df_trades.resample('ME').agg({
            'PnL': 'sum',
            'Result': ['count', lambda x: (x == 'Win').sum()]
        })
        monthly.columns = ['Profit ($)', 'Trades', 'Wins']
        
        # Monthly Start Equity for Percentage Calculation
        # We need equity at intervals.
        df_equity = pd.DataFrame(self.equity_curve)
        df_equity['Time'] = pd.to_datetime(df_equity['Time'])
        df_equity.set_index('Time', inplace=True)
        
        # Resample Equity to get Start of Month Balance
        monthly_equity = df_equity['Equity'].resample('ME').first() # Actually taking first of next bucket usually? 
        # Better: Shift it or use .ohlc()
        # Simplest: Just use cumulative profit to infer start
        
        # Let's iterate monthly to calculate % Return and Max DD per month
        report_data = []
        
        current_bal = Config.INITIAL_BALANCE
        cumulative_pnl = 0
        
        for date, row in monthly.iterrows():
            profit = row['Profit ($)']
            trades = int(row['Trades'])
            wins = int(row['Wins'])
            loss = trades - wins
            win_rate = (wins / trades * 100) if trades > 0 else 0
            
            # Month specific subset for DD
            month_start = date.replace(day=1) # Approx
            # Exact mask
            mask = (df_equity.index >= pd.Timestamp(date).replace(day=1, hour=0, minute=0)) & (df_equity.index <= date)
            subset = df_equity.loc[mask]
            
            max_dd_month = 0
            if not subset.empty:
                roll_max = subset['Equity'].cummax()
                dd = (subset['Equity'] - roll_max) / roll_max
                max_dd_month = dd.min() * 100
                
            # Month Return %
            start_of_month_bal = current_bal
            pct_return = (profit / start_of_month_bal) * 100
            
            current_bal += profit
            
            report_data.append({
                "Month": date.strftime("%Y-%b"),
                "Profit ($)": round(profit, 2),
                "Return (%)": round(pct_return, 2),
                "Max DD (%)": round(max_dd_month, 2),
                "Trades": trades,
                "Win Rate (%)": round(win_rate, 1)
            })
            
        df_report = pd.DataFrame(report_data)
        
        print("\n--- 2024-2025 MONTHLY BREAKDOWN (V3 ULTRA-PRECISION) ---")
        print(df_report.to_markdown(index=False))
        
        Global_DD = (df_equity['Equity'] - df_equity['Equity'].cummax()).min() / df_equity['Equity'].cummax().max() * 100
        print(f"\nGlobal Max Drawdown: {Global_DD:.2f}%") # Should be different calc slightly
        
        # Save Report
        with open("backtest_report_2024_2025.md", "w") as f:
            f.write("# PropBot 2024-2025 Performance Report\n")
            f.write("## Config\n")
            f.write("- **Strategy**: V3 Ultra-Precision (HTF Filter + Dynamic Risk)\n")
            f.write("- **Period**: Jan 1, 2024 - Dec 31, 2025\n\n")
            f.write("## Monthly Breakdown\n")
            f.write(df_report.to_markdown(index=False))

if __name__ == "__main__":
    bt = Backtester("GC=F")
    bt.run_sim()
    bt.generate_report()
