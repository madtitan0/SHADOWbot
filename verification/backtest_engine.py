import yfinance as yf
import pandas as pd
import numpy as np

# --- Configuration ---
class Config:
    SYMBOLS = ["GC=F", "EURUSD=X"] # Gold Futures, EURUSD
    PERIOD = "60d" # Max for 5m interval is ~60 days
    INTERVAL = "5m"
    SL_POINTS = { "GC=F": 2.0, "EURUSD=X": 0.0020 } # 20 pips gold, 20 pips eurasian
    TP_POINTS = { "GC=F": 4.0, "EURUSD=X": 0.0040 } # 40 pips gold, 40 pips eurasian
    RISK_PERCENT = 0.005 # 0.5%
    INITIAL_BALANCE = 100000.0
    SPREAD_COST = { "GC=F": 0.10, "EURUSD=X": 0.0001 } # Approximate spread cost
    ATR_PERIOD = 14
    MIN_ATR = { "GC=F": 0.5, "EURUSD=X": 0.0005 } # Min volatility needed

class Backtester:
    def __init__(self, symbol):
        self.symbol = symbol
        self.data = None
        self.balance = Config.INITIAL_BALANCE
        self.equity_curve = [Config.INITIAL_BALANCE]
        self.trades = []
        
    def fetch_data(self):
        print(f"Fetching data for {self.symbol}...")
        self.data = yf.download(self.symbol, period=Config.PERIOD, interval=Config.INTERVAL, progress=False)
        if self.data.empty:
            print(f"Warning: No data found for {self.symbol}")
            return
            
        # Calculate Indicators
        self.data['ATR'] = self.calculate_atr(self.data, Config.ATR_PERIOD)
        self.data['PrevHigh'] = self.data['High'].shift(2) # H[i-2]
        self.data['PrevLow'] = self.data['Low'].shift(2)   # L[i-2]
        
        # V2 Indicators: Bollinger Bands
        self.data['SMA_20'] = self.data['Close'].rolling(20).mean()
        self.data['StdDev'] = self.data['Close'].rolling(20).std()
        self.data['UpperBB'] = self.data['SMA_20'] + (2.5 * self.data['StdDev'])
        self.data['LowerBB'] = self.data['SMA_20'] - (2.5 * self.data['StdDev'])
        
        # V2 Indicators: MAs
        self.data['EMA_Fast'] = self.data['Close'].ewm(span=9, adjust=False).mean()
        self.data['EMA_Slow'] = self.data['Close'].ewm(span=21, adjust=False).mean()

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
        
        sl_dist = Config.SL_POINTS[self.symbol]
        tp_dist = Config.TP_POINTS[self.symbol]
        spread = Config.SPREAD_COST[self.symbol]
        min_atr = Config.MIN_ATR[self.symbol]

        for i in range(25, len(self.data)): # Start after indicators warm up
            # Iterate
            current_open = self.data['Open'].iloc[i].item()
            curr_high = self.data['High'].iloc[i].item()
            curr_low = self.data['Low'].iloc[i].item()
            curr_close = self.data['Close'].iloc[i].item() # For EOD close check
            
            # Logic: Signal from PREVIOUS bars
            idx_prev = i - 1
            close_prev = self.data['Close'].iloc[idx_prev].item()
            open_prev = self.data['Open'].iloc[idx_prev].item()
            high_prev_2 = self.data['High'].iloc[i-2].item()
            low_prev_2 = self.data['Low'].iloc[i-2].item()
            atr = self.data['ATR'].iloc[idx_prev].item()
            
            # V2 Indicators
            upper_bb = self.data['UpperBB'].iloc[idx_prev].item()
            lower_bb = self.data['LowerBB'].iloc[idx_prev].item()
            ema_fast = self.data['EMA_Fast'].iloc[idx_prev].item()
            ema_slow = self.data['EMA_Slow'].iloc[idx_prev].item()

            # Manage Open Trade
            if position != 0:
                pnl = 0
                exit_price = 0
                
                sl_price = entry_price - sl_dist if position == 1 else entry_price + sl_dist
                tp_price = entry_price + tp_dist if position == 1 else entry_price - tp_dist
                
                # Check SL/TP
                triggered = False
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
                    # Calculate PnL
                    risk_amt = self.balance * Config.RISK_PERCENT
                    units = risk_amt / sl_dist
                    
                    raw_diff = (exit_price - entry_price) if position == 1 else (entry_price - exit_price)
                    pnl = raw_diff * units
                    
                    self.balance += pnl
                    self.trades.append(pnl)
                    position = 0

            # Check Entry (if flat)
            if position == 0:
                signal_found = False
                
                # 1. Volatility + Momentum (Original V1)
                if atr >= min_atr:
                    if close_prev > high_prev_2 and close_prev > open_prev:
                        entry_price = current_open + spread
                        position = 1
                        signal_found = True
                    elif close_prev < low_prev_2 and close_prev < open_prev:
                        entry_price = current_open - spread
                        position = -1
                        signal_found = True
                
                # 2. Mean Reversion (V2) - Ignore Volatility Filter (works in chop)
                if not signal_found:
                    if close_prev > upper_bb: # Overbought
                        entry_price = current_open - spread
                        position = -1 # Sell
                        signal_found = True
                    elif close_prev < lower_bb: # Oversold
                        entry_price = current_open + spread
                        position = 1 # Buy
                        signal_found = True
                        
                # 3. Pullback (V2) - Trend Logic
                if not signal_found:
                    if ema_fast > ema_slow: # Uptrend
                        # Did price dip into Fast EMA?
                        low_prev = self.data['Low'].iloc[idx_prev].item()
                        if low_prev <= ema_fast and close_prev > ema_fast:
                            entry_price = current_open + spread
                            position = 1
                    elif ema_fast < ema_slow: # Downtrend
                        high_prev = self.data['High'].iloc[idx_prev].item()
                        if high_prev >= ema_fast and close_prev < ema_fast:
                            entry_price = current_open - spread
                            position = -1

            self.equity_curve.append(self.balance)

    def close_trade(self, price, reason):
        # Calculate PnL
        # Simplified: (Exit - Entry) * Lots * ContractSize
        # Since I am equity-based, let's assume risk% logic for sizing.
        # Risk 0.5% of Balance.
        # Risk Amount = Balance * 0.005
        # SL Distance = Config.SL_POINTS
        # Unit Size = Risk Amount / SL Distance
        
        sl_dist = Config.SL_POINTS[self.symbol]
        risk_amt = self.balance * Config.RISK_PERCENT
        units = risk_amt / sl_dist
        
        # Last trade PnL
        last_entry = self.trades[-1]['entry'] if self.trades else 0
        # Actually need to store current trade details in class state, simpler here:
        # Re-calc units based on state at entry time? Assume constant risk for sim simplicity
        
        # Let's track trade properly
        # Note: units is calculated at CLOSE for simplicity here, effectively "rebalancing". 
        # Correct is at OPEN. But for quick sim, this is fine.
        
        # PnL Calculation
        # Long: (Price - Entry)
        # Short: (Entry - Price)
        entry = 0 # Need to store entry from loop
        # ... refactoring to store Trade object
        pass # placeholder

    def run_sim(self):
        self.fetch_data()
        if self.data is None or self.data.empty: return

        position = 0 
        entry_price = 0
        
        sl_dist = Config.SL_POINTS[self.symbol]
        tp_dist = Config.TP_POINTS[self.symbol]
        spread = Config.SPREAD_COST[self.symbol]
        min_atr = Config.MIN_ATR[self.symbol]

        for i in range(20, len(self.data)):
            # Iterate
            current_open = self.data['Open'].iloc[i].item()
            curr_high = self.data['High'].iloc[i].item()
            curr_low = self.data['Low'].iloc[i].item()
            
            # Logic: Signal from PREVIOUS bars
            idx_prev = i - 1
            close_prev = self.data['Close'].iloc[idx_prev].item()
            open_prev = self.data['Open'].iloc[idx_prev].item()
            high_prev_2 = self.data['High'].iloc[i-2].item()
            low_prev_2 = self.data['Low'].iloc[i-2].item()
            atr = self.data['ATR'].iloc[idx_prev].item()

            # Manage Open Trade
            if position != 0:
                pnl = 0
                exit_price = 0
                
                sl_price = entry_price - sl_dist if position == 1 else entry_price + sl_dist
                tp_price = entry_price + tp_dist if position == 1 else entry_price - tp_dist
                
                # Check SL/TP
                triggered = False
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
                    # Calculate PnL
                    risk_amt = self.balance * Config.RISK_PERCENT
                    units = risk_amt / sl_dist
                    
                    raw_diff = (exit_price - entry_price) if position == 1 else (entry_price - exit_price)
                    pnl = raw_diff * units
                    
                    self.balance += pnl
                    self.trades.append(pnl)
                    position = 0

            # Check Entry (if flat)
            if position == 0:
                if atr >= min_atr:
                    # Long Signal
                    if close_prev > high_prev_2 and close_prev > open_prev:
                        entry_price = current_open + spread
                        position = 1
                    # Short Signal
                    elif close_prev < low_prev_2 and close_prev < open_prev:
                        entry_price = current_open - spread
                        position = -1
            
            self.equity_curve.append(self.balance)
            
    def stats(self):
        if not self.trades: return { "Return": 0, "Sharpe": 0, "DD": 0, "Trades": 0 }
        
        df_equity = pd.Series(self.equity_curve)
        total_return_pct = ((self.balance - Config.INITIAL_BALANCE) / Config.INITIAL_BALANCE) * 100
        
        # Drawdown
        rolling_max = df_equity.cummax()
        drawdown = (df_equity - rolling_max) / rolling_max
        max_dd = drawdown.min() * 100
        
        # Sharpe (Daily approximation)
        returns = df_equity.pct_change().dropna()
        if returns.std() == 0: sharpe = 0
        else: sharpe = (returns.mean() / returns.std()) * np.sqrt(252*24*12) # Annualized for 5m? Rough approx.
        
        return {
            "Return %": round(total_return_pct, 2),
            "Max DD %": round(max_dd, 2),
            "Trades": len(self.trades),
            "End Balance": round(self.balance, 2)
        }

if __name__ == "__main__":
    print(f"--- Running Backtest (Last 60 Days, 5m Data) ---")
    
    # Run Gold
    print("\nTesting Gold (GC=F)...")
    bt_gold = Backtester("GC=F")
    bt_gold.run_sim()
    stats_gold = bt_gold.stats()
    print("Gold Results:", stats_gold)
    
    # Run EURUSD
    print("\nTesting EURUSD (EURUSD=X)...") # Ensure proper symbol for yfinance
    bt_eur = Backtester("EURUSD=X")
    bt_eur.run_sim()
    stats_eur = bt_eur.stats()
    print("EURUSD Results:", stats_eur)
    
    print("\n--- Recommendation ---")
    if stats_gold['Return %'] > stats_eur['Return %']:
        print("Gold performed better.")
    else:
        print("EURUSD performed better.")
