import yfinance as yf
import pandas as pd
import numpy as np
import shutil
import os

# --- Configuration (V4) ---
class Config:
    # API Limit: Last 730 days from Feb 2026 = Start ~Feb 2024.
    # Adjusted to strictly valid range.
    START_DATE = "2024-03-01" 
    END_DATE = "2024-12-31"
    INTERVAL = "1h"    
    
    RISK_PERCENT = 0.0075 # 0.75%
    INITIAL_BALANCE = 100000.0
    SPREAD_COST = 0.20
    ATR_PERIOD = 14
    
    # Lot Calculation Constants (Gold)
    CONTRACT_SIZE = 100 # Standard Lot = 100 oz
    
    # H1 Sizing
    SL_ATR_MULT = 1.5 
    TP_ATR_MULT = 2.5 
    
    # Logic
    MIN_ATR = 1.0 
    USE_MEAN_REV = True
    USE_PULLBACK = True
    USE_HTF_FILTER = True 
    USE_EXTREME_RSI = True 
    USE_ADX_FILTER = True 

class Backtester:
    def __init__(self, symbol):
        self.symbol = symbol
        self.data = None
        self.balance = Config.INITIAL_BALANCE
        self.equity_curve = []
        self.trade_log = []
        self.lot_sizes = []
        
    def fetch_data(self):
        print(f"Fetching data {Config.START_DATE} -> {Config.END_DATE}...")
        self.data = yf.download(self.symbol, start=Config.START_DATE, end=Config.END_DATE, interval=Config.INTERVAL, progress=False)
        
        # Flatten MultiIndex
        if isinstance(self.data.columns, pd.MultiIndex):
            self.data.columns = self.data.columns.get_level_values(0)

        if self.data.empty:
            print("Error: No data fetched.")
            return

        print(f"Data fetched: {len(self.data)} rows.")
        print(f"Actual Start: {self.data.index[0]}")
        
        # Indicators
        self.data['ATR'] = self.calculate_atr(self.data, Config.ATR_PERIOD)
        self.data['PrevHigh'] = self.data['High'].shift(2)
        self.data['PrevLow'] = self.data['Low'].shift(2)
        self.data['SMA_20'] = self.data['Close'].rolling(20).mean()
        self.data['StdDev'] = self.data['Close'].rolling(20).std()
        self.data['UpperBB'] = self.data['SMA_20'] + (2.5 * self.data['StdDev'])
        self.data['LowerBB'] = self.data['SMA_20'] - (2.5 * self.data['StdDev'])
        self.data['EMA_Fast'] = self.data['Close'].ewm(span=9, adjust=False).mean()
        self.data['EMA_Slow'] = self.data['Close'].ewm(span=21, adjust=False).mean()
        self.data['EMA_50'] = self.data['Close'].ewm(span=50, adjust=False).mean()
        self.data['RSI'] = self.calculate_rsi(self.data, 14)
        self.data['ADX'] = self.calculate_adx(self.data, 14)

    def calculate_atr(self, df, period):
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(period).mean()

    def calculate_rsi(self, df, period=14):
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
        
    def calculate_adx(self, df, period=14):
        plus_dm = df['High'].diff()
        minus_dm = df['Low'].diff()
        plus_dm = plus_dm.where((plus_dm > 0) & (plus_dm > minus_dm), 0)
        minus_dm = minus_dm.where((minus_dm > 0) & (minus_dm > plus_dm), 0)
        tr = self.calculate_atr(df, 1) 
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()
        if isinstance(adx, pd.DataFrame): adx = adx.iloc[:, 0]
        return adx.fillna(20)

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
            
            # --- V3.2 Scaler ---
            if self.balance > hwm: hwm = self.balance
            current_dd_pct = (hwm - self.balance) / hwm * 100.0
            
            risk_modifier = 1.0
            if current_dd_pct >= 0.5: risk_modifier = 0.666 
            if current_dd_pct >= 1.0: risk_modifier = 0.333
            if current_dd_pct >= 1.5: risk_modifier = 0.133
            if current_dd_pct >= 2.0: risk_modifier = 0.0   
            
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
            ema_50 = self.data['EMA_50'].iloc[idx_prev].item()
            rsi = self.data['RSI'].iloc[idx_prev].item()
            adx = self.data['ADX'].iloc[idx_prev].item()

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
                    if risk_modifier > 0:
                        risk_amt = self.balance * (Config.RISK_PERCENT * risk_modifier)
                        units = risk_amt / current_sl_dist
                        
                        # Lot Size Calc
                        lots = units / Config.CONTRACT_SIZE
                        self.lot_sizes.append(lots)
                        
                        raw_diff = (exit_price - entry_price) if position == 1 else (entry_price - exit_price)
                        pnl = raw_diff * units
                        
                        self.balance += pnl
                        self.trade_log.append({
                            "EntryTime": entry_time,
                            "ExitTime": timestamp,
                            "Type": "BUY" if position == 1 else "SELL",
                            "Lots": round(lots, 2),
                            "PnL": round(pnl, 2),
                            "Balance": round(self.balance, 2)
                        })
                    position = 0

            if position == 0 and risk_modifier > 0:
                signal_found = False
                trade_atr = atr if atr > min_atr else min_atr
                
                can_buy = True; can_sell = True
                is_extreme_rsi_buy = (rsi < 25)
                is_extreme_rsi_sell = (rsi > 75)
                
                if Config.USE_HTF_FILTER and not is_extreme_rsi_buy: can_buy = close_prev > ema_50
                if Config.USE_HTF_FILTER and not is_extreme_rsi_sell: can_sell = close_prev < ema_50
                
                adx_ok = True
                if not (is_extreme_rsi_buy or is_extreme_rsi_sell):
                    if adx < 20: adx_ok = False
                
                if atr >= min_atr and adx_ok:
                    if close_prev > high_prev_2 and close_prev > open_prev and can_buy:
                        entry_price = current_open + spread
                        position = 1
                        signal_found = True
                    elif close_prev < low_prev_2 and close_prev < open_prev and can_sell:
                        entry_price = current_open - spread
                        position = -1
                        signal_found = True
                        
                if not signal_found and Config.USE_MEAN_REV:
                    if close_prev > upper_bb and can_sell:
                        entry_price = current_open - spread
                        position = -1
                        signal_found = True
                    elif close_prev < lower_bb and can_buy:
                        entry_price = current_open + spread
                        position = 1
                        signal_found = True
                
                if not signal_found and Config.USE_PULLBACK and adx_ok:
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
        if not self.trade_log: 
            print("No trades found.")
            return

        df_trades = pd.DataFrame(self.trade_log)
        df_trades['ExitTime'] = pd.to_datetime(df_trades['ExitTime'])
        
        # Monthly Stats
        df_trades.set_index('ExitTime', inplace=True)
        monthly_groups = df_trades.resample('ME')
        
        report_data = []
        current_bal = Config.INITIAL_BALANCE
        
        all_months = sorted(monthly_groups.groups.keys())
        df_equity = pd.DataFrame(self.equity_curve)
        df_equity['Time'] = pd.to_datetime(df_equity['Time'])
        df_equity.set_index('Time', inplace=True)
        
        for date in all_months:
            try:
                group = monthly_groups.get_group(date)
            except KeyError:
                continue
                
            net_profit = group['PnL'].sum()
            trades = len(group)
            
            # Max DD
            m_start = pd.Timestamp(date).replace(day=1, hour=0, minute=0)
            m_end = date
            mask = (df_equity.index >= m_start) & (df_equity.index <= m_end)
            subset = df_equity.loc[mask]
            
            max_dd_month = 0
            if not subset.empty:
                roll_max = subset['Equity'].cummax()
                dd = (subset['Equity'] - roll_max) / roll_max
                max_dd_month = dd.min() * 100
            
            percent_ret = (net_profit / current_bal) * 100
            current_bal += net_profit
            
            report_data.append({
                "Month": date.strftime("%Y-%m"),
                "Profit": round(net_profit, 2),
                "Return%": round(percent_ret, 2),
                "MaxDD%": round(max_dd_month, 2),
                "Trades": trades,
                "AvgLot": round(group['Lots'].mean(), 2)
            })
            
        df_report = pd.DataFrame(report_data)
        
        # Output
        csv_filename = "PropBot_Backtest_2020_2024.csv"
        df_report.to_csv(csv_filename, index=False)
        print(f"\nCSV Generated: {csv_filename}")
        
        avg_lots = np.mean(self.lot_sizes) if self.lot_sizes else 0
        print(f"Overall Standard Lot Size (Avg): {avg_lots:.2f}")

        # Move to Desktop (Best effort)
        try:
            desktop = os.path.expanduser("~/Desktop")
            if os.path.exists(desktop):
                shutil.copy(csv_filename, os.path.join(desktop, csv_filename))
                print(f"Moved to Desktop: {os.path.join(desktop, csv_filename)}")
        except Exception as e:
            print(f"Could not move to Desktop: {e}")

if __name__ == "__main__":
    bt = Backtester("GC=F")
    bt.run_sim()
    bt.generate_report()
