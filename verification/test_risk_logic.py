import unittest

class MockAccount:
    def __init__(self, balance=100000.0):
        self.balance = balance
        self.equity = balance
        self.start_day_equity = balance
        self.high_water_mark = balance

class RiskManager:
    def __init__(self, account):
        self.account = account
        self.fp_max_daily_loss = 4.0 # 5% - 1% buffer
        self.fp_max_total_loss = 9.0 # 10% - 1% buffer
        self.daily_limit_hit = False
        self.total_limit_hit = False

    def on_tick(self):
        # Daily Loss Check
        limit_level_daily = self.account.start_day_equity * (1.0 - (self.fp_max_daily_loss / 100.0))
        if self.account.equity <= limit_level_daily:
            self.daily_limit_hit = True
            print(f"CRITICAL: Daily Loss Hit! Equity: {self.account.equity} <= Limit: {limit_level_daily}")

        # Total Loss Check (High Water Mark trailing)
        # Update HWM
        if self.account.equity > self.account.high_water_mark:
            self.account.high_water_mark = self.account.equity
            
        limit_level_total = self.account.high_water_mark * (1.0 - (self.fp_max_total_loss / 100.0))
        if self.account.equity <= limit_level_total:
            self.total_limit_hit = True
            print(f"CRITICAL: Total Loss Hit! Equity: {self.account.equity} <= Limit: {limit_level_total}")

    def get_lot_size(self, risk_percent, sl_points, tick_value=1.0, tick_size=0.01, point=0.01):
        risk_amount = self.account.equity * (risk_percent / 100.0)
        value_per_point = tick_value * (point / tick_size)
        if value_per_point == 0 or sl_points == 0:
            return 0
        lot_size = risk_amount / (sl_points * value_per_point)
        return round(lot_size, 2)

class TestPropBotRisk(unittest.TestCase):
    def setUp(self):
        self.account = MockAccount(100000.0)
        self.risk_manager = RiskManager(self.account)

    def test_daily_loss_limit(self):
        print("\n--- Testing Daily Loss Limit ---")
        # Start Equity = 100,000
        # Limit = 4% = 4,000 -> Stop at 96,000
        
        self.account.equity = 97000
        self.risk_manager.on_tick()
        self.assertFalse(self.risk_manager.daily_limit_hit, "Should be alive at -3%")
        
        self.account.equity = 96000
        self.risk_manager.on_tick()
        self.assertTrue(self.risk_manager.daily_limit_hit, "Should stop at -4% exactly")

    def test_total_loss_limit(self):
        print("\n--- Testing Total Loss Limit ---")
        # Start Equity = 100,000. HWM = 100,000.
        # Limit = 9% = 9,000 -> Stop at 91,000.
        
        # Scenario: Account grows first
        self.account.equity = 110000
        self.risk_manager.on_tick() # Update HWM to 110,000
        print(f"Account grew to {self.account.equity}. HWM is now {self.account.high_water_mark}")
        
        # New Total Limit = 110,000 * (1 - 0.09) = 100,100
        self.account.equity = 100200
        self.risk_manager.on_tick()
        self.assertFalse(self.risk_manager.total_limit_hit, "Should be alive above dynamic total limit")
        
        self.account.equity = 100000
        self.risk_manager.on_tick()
        self.assertTrue(self.risk_manager.total_limit_hit, f"Should stop below dynamic total limit (Limit approx 100,100). Equity: {self.account.equity}")

    def test_lot_sizing(self):
        print("\n--- Testing Lot Sizing ---")
        # Equity 100,000. Risk 0.5% = $500.
        # SL = 200 points (20 pips on Gold). 
        # TickValue=1, TickSize=0.01, Point=0.01 -> ValuePerPoint = 1.
        # Lot = 500 / (200 * 1) = 2.5 Lots.
        
        lots = self.risk_manager.get_lot_size(0.5, 200)
        print(f"Calculated Lots: {lots}")
        self.assertAlmostEqual(lots, 2.5)
        
        # Test Equity Drop
        self.account.equity = 50000
        # Risk 0.5% = $250.
        # Lot = 250 / 200 = 1.25 Lots.
        lots = self.risk_manager.get_lot_size(0.5, 200)
        print(f"Calculated Lots (Low Equity): {lots}")
        self.assertAlmostEqual(lots, 1.25)

if __name__ == '__main__':
    unittest.main()
