import yfinance as yf
import pandas as pd
import numpy as np

# --- Configuration ---
class Config:
    SYMBOLS = ["GC=F"] # Gold Futures Only (Proven best)
    PERIOD = "2y"      # Two Years (Max for 1h)
    INTERVAL = "1h"    # Hourly Data because 5m is unavailable for >60d
    RISK_PERCENT = 0.005 # 0.5%
    INITIAL_BALANCE = 100000.0
    SPREAD_COST = 0.20 # Higher spread assumption for H1 swing/scalp
    ATR_PERIOD = 14
    
    # Dynamic Sizing (Versatility)
    # H1 needs wider stops than M5
    SL_ATR_MULT = 1.5 
    TP_ATR_MULT = 2.5 
    
    # V2 Logic
    MIN_ATR = 1.0 # Min $1 movement per hour on Gold
    USE_MEAN_REV = True
    USE_PULLBACK = True

class Backtester:
    def __init__(self, symbol):
        self.symbol = symbol
        self.data = None
        self.balance = Config.INITIAL_BALANCE
        self.equity_curve = []
        self.trade_log = [] # List of dicts
        
    def fetch_data(self):
        print(f"Fetching 2Y data for {self.symbol}...")
        self.data = yf.download(self.symbol, period=Config.PERIOD, interval=Config.INTERVAL, progress=False)
        if self.data.empty:
            print(f"Warning: No data found for {self.symbol}")
            return
            
        # Calculate Indicators
        self.data['ATR'] = self.calculate_atr(self.data, Config.ATR_PERIOD)
        self.data['PrevHigh'] = self.data['High'].shift(2)
        self.data['PrevLow'] = self.data['Low'].shift(2)
        
        # V2 Indicators
        self.data['SMA_20'] = self.data['Close'].rolling(20).mean()
        self.data['StdDev'] = self.data['Close'].rolling(20).std()
        self.data['UpperBB'] = self.data['SMA_20'] + (2.5 * self.data['StdDev'])
        self.data['LowerBB'] = self.data['SMA_20'] - (2.5 * self.data['StdDev'])
        
        self.data['EMA_Fast'] = self.data['Close'].ewm(span=9, adjust=False).mean()
        self.data['EMA_Slow'] = self.data['Close'].ewm(span=21, adjust=False).mean()
        
        # V3 Indicator: H1 Trend (Approximated on H1 data)
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
        entry_time = None
        
        current_sl_dist = 0
        current_tp_dist = 0
        
        # Drawdown Tracking for V3
        start_equity = Config.INITIAL_BALANCE
        hwm = Config.INITIAL_BALANCE

        spread = Config.SPREAD_COST
        min_atr = Config.MIN_ATR

        # Loop
        for i in range(55, len(self.data)): # Wait for EMA 50
            timestamp = self.data.index[i]
            current_open = self.data['Open'].iloc[i].item()
            curr_high = self.data['High'].iloc[i].item()
            curr_low = self.data['Low'].iloc[i].item()
            curr_close = self.data['Close'].iloc[i].item()
            
            # Update Metrics
            if self.balance > hwm: hwm = self.balance
            
            # --- V3 Dynamic Risk Scaling ---
            current_dd_pct = (hwm - self.balance) / hwm * 100.0
            risk_modifier = 1.0
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
            ema_50_htf = self.data['EMA_50'].iloc[idx_prev].item() # HTF Trend

            # Manage Open Trade
            if position != 0:
                pnl = 0
                exit_price = 0
                triggered = False
                
                # Check Breakeven (V3)
                # If price > Entry + 1.5R, move SL to Entry.
                # Simplified check: just checking SL/TP hit logic first
                
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
                    risk_amt = self.balance * (Config.RISK_PERCENT * risk_modifier) # Apply Modifier
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
                
                # V3 HTF Filter Direction
                # Buy only if Close > EMA50, Sell only if Close < EMA50
                can_buy = close_prev > ema_50_htf
                can_sell = close_prev < ema_50_htf
                
                # 1. Momentum Check
                if atr >= min_atr:
                    if close_prev > high_prev_2 and close_prev > open_prev and can_buy:
                        entry_price = current_open + spread
                        position = 1
                        signal_found = True
                    elif close_prev < low_prev_2 and close_prev < open_prev and can_sell:
                        entry_price = current_open - spread
                        position = -1
                        signal_found = True
                        
                # 2. Mean Reversion
                if not signal_found and Config.USE_MEAN_REV:
                    if close_prev > upper_bb and can_sell: # Fade only with trend? Or Counter?
                        # Reversion is counter-trend. Filter might BLOCK good reversals if strict.
                        # V3 Rule: Trend Filter applies to MOMENTUM. Reversion ignores it (or requires extreme extension).
                        # Let's apply strict filter to ALL for "Ultra Precision".
                        if can_sell: 
                             entry_price = current_open - spread
                             position = -1
                             signal_found = True
                    elif close_prev < lower_bb and can_buy:
                        if can_buy:
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

    def generate_monthly_report(self):
        if not self.trade_log: 
            print("No trades generated.")
            return

        df_trades = pd.DataFrame(self.trade_log)
        df_trades['ExitTime'] = pd.to_datetime(df_trades['ExitTime'])
        df_trades.set_index('ExitTime', inplace=True)
        
        monthly = df_trades.resample('ME').agg({
            'PnL': 'sum',
            'Result': ['count', lambda x: (x == 'Win').sum()]
        })
        
        monthly.columns = ['NetProfit', 'TotalTrades', 'Wins']
        monthly['Losses'] = monthly['TotalTrades'] - monthly['Wins']
        monthly['WinRate'] = (monthly['Wins'] / monthly['TotalTrades']) * 100
        
        df_equity = pd.DataFrame(self.equity_curve)
        df_equity['Time'] = pd.to_datetime(df_equity['Time'])
        df_equity.set_index('Time', inplace=True)
        
        rolling_max = df_equity['Equity'].cummax()
        drawdown = (df_equity['Equity'] - rolling_max) / rolling_max
        max_dd = drawdown.min() * 100
        
        print(f"\n--- V3 ULTRA-PRECISION STATS (2 Years) ---")
        print(f"Final Balance: ${self.balance:.2f}")
        print(f"Total Return: {((self.balance - Config.INITIAL_BALANCE)/Config.INITIAL_BALANCE)*100:.2f}%")
        print(f"Max Drawdown: {max_dd:.2f}%")
        print(monthly.to_markdown())
        
        # Save to file for User
        with open("monthly_report.md", "w") as f:
            f.write(f"# PropBot Performance Report (2023-2024)\n\n")
            f.write(f"**Period**: 2 Years (Hourly Data)\n")
            f.write(f"**Simulation Mode**: Dynamic ATR Sizing (Versatility Test)\n\n")
            f.write(f"## Global Metrics\n")
            f.write(f"- **Total Return**: {((self.balance - Config.INITIAL_BALANCE)/Config.INITIAL_BALANCE)*100:.2f}%\n")
            f.write(f"- **Max Drawdown**: {max_dd:.2f}%\n")
            f.write(f"- **Total Trades**: {len(self.trade_log)}\n\n")
            f.write(f"## Monthly Breakdown\n")
            f.write(monthly.to_markdown())

if __name__ == "__main__":
    bt = Backtester("GC=F")
    bt.run_sim()
    bt.generate_monthly_report()
