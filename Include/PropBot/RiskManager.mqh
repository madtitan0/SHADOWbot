//+------------------------------------------------------------------+
//|                                                  RiskManager.mqh |
//|                                  Copyright 2024, Clawdbot Module |
//+------------------------------------------------------------------+
#property copyright "Clawdbot Module"
#property strict

#include "Common.mqh"

class CRiskManager
  {
private:
   double            m_fpMaxDailyLossPercent;
   double            m_fpMaxTotalLossPercent;
   double            m_riskPerTradePercent;
   double            m_maxExposurePercent;
   
   double            m_startOfDayEquity;
   double            m_highWaterMark;
   datetime          m_lastDay;
   
   double            m_dailyLossLimit; // Actual limit value in currency
   double            m_totalLossLimit; // Actual limit value in currency

public:
                     CRiskManager();
                    ~CRiskManager();

   void              Init(double fpDailyLoss, double fpTotalLoss, double riskPerTrade, double maxExposure);
   void              OnTick();
   
   // Checkers
   bool              CheckDailyLoss();
   bool              CheckTotalLoss();
   bool              CheckMaxExposure();
   bool              CheckProfitTargets(double minProfit, double targetProfit, double maxProfit);
   
   // Getters
   double            GetLotSize(double slPoints, string symbol);
   double            GetRiskPerTrade();
   double            GetRiskModifier(); // New: Dynamic Scaling Factor

   // Setters
   void              ReduceRisk(double factor);
   void              ResetRisk();

private:
   void              UpdateDayStart();
  };

//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CRiskManager::CRiskManager()
  {
   m_startOfDayEquity = 0;
   m_highWaterMark = 0;
   m_lastDay = 0;
  }

//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CRiskManager::~CRiskManager()
  {
  }

//+------------------------------------------------------------------+
//| Initialize Risk Manager                                          |
//+------------------------------------------------------------------+
void CRiskManager::Init(double fpDailyLoss, double fpTotalLoss, double riskPerTrade, double maxExposure)
  {
   m_fpMaxDailyLossPercent = fpDailyLoss - 1.0; // Safety buffer
   m_fpMaxTotalLossPercent = fpTotalLoss - 1.0; // Safety buffer
   m_riskPerTradePercent = riskPerTrade;
   m_maxExposurePercent = maxExposure;
   
   // Load or Init Start of Day Equity
   string gvEquity = "PropBot_StartEquity_" + (string)AccountInfoInteger(ACCOUNT_LOGIN);
   string gvDay = "PropBot_Day_" + (string)AccountInfoInteger(ACCOUNT_LOGIN);
   
   datetime currentTime = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(currentTime, dt);
   int currentDay = dt.day_of_year;
   
   if(GlobalVariableCheck(gvEquity) && GlobalVariableCheck(gvDay))
     {
      int savedDay = (int)GlobalVariableGet(gvDay);
      if(savedDay == currentDay)
        {
         m_startOfDayEquity = GlobalVariableGet(gvEquity);
         Print("Restored Start Equity: ", m_startOfDayEquity);
        }
      else
        {
         // New day happened while offline
         m_startOfDayEquity = AccountInfoDouble(ACCOUNT_EQUITY);
         GlobalVariableSet(gvEquity, m_startOfDayEquity);
         GlobalVariableSet(gvDay, currentDay);
         Print("New Day (Offline Reset): Start Equity = ", m_startOfDayEquity);
        }
     }
   else
     {
      // First run
      m_startOfDayEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      GlobalVariableSet(gvEquity, m_startOfDayEquity);
      GlobalVariableSet(gvDay, currentDay);
      Print("Init Start Equity: ", m_startOfDayEquity);
     }
   
   m_highWaterMark = AccountInfoDouble(ACCOUNT_EQUITY); // HWM usually resets on restart for session or needs separate tracking. 
   // For simple Total Loss check, keeping it session based or requiring manual input is safer than auto-restoring potentially wrong HWM.
   // Ideally HWM should also be persistent but "Total Loss" usually means from Account Start. 
   // So HWM should actually just be "Initial Balance" or "Max Equity Ever". 
   // Let's rely on current equity vs check. 
   // A better approach for HWM is checking AccountInfoDouble(ACCOUNT_BALANCE) if we assume balance only goes up? No.
   // Let's leave HWM as session-based for now to avoid complexity, or just set it to current equity.
   m_lastDay = currentTime;
  }

//+------------------------------------------------------------------+
//| Main OnTick Update                                               |
//+------------------------------------------------------------------+
void CRiskManager::OnTick()
  {
   // Update Start of Day Equity
   datetime currentTime = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(currentTime, dt);
   
   // Simple day change check (assuming broker server time)
   if(dt.hour == 0 && dt.min == 0 && dt.sec == 0)
     {
      // Only update once per day
      if(currentTime > m_lastDay + 3600) 
        {
         m_startOfDayEquity = AccountInfoDouble(ACCOUNT_EQUITY);
         m_lastDay = currentTime;
         
         // Update GVs
         string gvEquity = "PropBot_StartEquity_" + (string)AccountInfoInteger(ACCOUNT_LOGIN);
         string gvDay = "PropBot_Day_" + (string)AccountInfoInteger(ACCOUNT_LOGIN);
         GlobalVariableSet(gvEquity, m_startOfDayEquity);
         GlobalVariableSet(gvDay, dt.day_of_year);
         
         Print("New Day: Start Equity = ", m_startOfDayEquity);
        }
     }
     
   // Update High Water Mark
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(currentEquity > m_highWaterMark)
     {
      m_highWaterMark = currentEquity;
     }
  }

//+------------------------------------------------------------------+
//| Check Daily Loss Limit                                           |
//+------------------------------------------------------------------+
bool CRiskManager::CheckDailyLoss()
  {
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   double limitLevel = m_startOfDayEquity * (1.0 - (m_fpMaxDailyLossPercent / 100.0));
   
   if(currentEquity <= limitLevel)
     {
      Print("CRITICAL: Daily Loss Limit Hit! Equity: ", currentEquity, " Limit: ", limitLevel);
      return false; // Stop Trading
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Check Total Loss Limit                                           |
//+------------------------------------------------------------------+
bool CRiskManager::CheckTotalLoss()
  {
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   double limitLevel = m_highWaterMark * (1.0 - (m_fpMaxTotalLossPercent / 100.0));
   
   if(currentEquity <= limitLevel)
     {
      Print("CRITICAL: Total Loss Limit Hit! Equity: ", currentEquity, " Limit: ", limitLevel);
      return false; // Stop Trading
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Calculate Lot Size based on Risk                                 |
//+------------------------------------------------------------------+
double CRiskManager::GetLotSize(double slPoints, string symbol)
  {
   if(slPoints <= 0) return 0.0;
   
   double riskAmount = AccountInfoDouble(ACCOUNT_EQUITY) * (m_riskPerTradePercent / 100.0);
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   
   if(tickValue == 0 || tickSize == 0 || point == 0) return 0.0;
   
   // Adjust tick value to point value
   double valuePerPoint = tickValue * (point / tickSize);
   
   double riskModifier = GetRiskModifier();
   double adjustedRiskPercent = m_riskPerTradePercent * riskModifier;
   
   double riskAmount = AccountInfoDouble(ACCOUNT_EQUITY) * (adjustedRiskPercent / 100.0);
   
   if(riskModifier < 1.0)
      Print("Dynamic Risk Scaling Active: Modifier = ", riskModifier, " | Adjusted Risk = ", adjustedRiskPercent, "%");
      
   double lotSize = riskAmount / (slPoints * valuePerPoint);
   
   // Normalize Lot Size
   double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   
   lotSize = MathFloor(lotSize / stepLot) * stepLot;
   
   if(lotSize < minLot) lotSize = minLot; // Or 0 if strict
   if(lotSize > maxLot) lotSize = maxLot;
   
   return lotSize;
  }
//+------------------------------------------------------------------+
//| Get Risk Modifier (Dynamic Drawdown Control)                     |
//+------------------------------------------------------------------+
double CRiskManager::GetRiskModifier()
  {
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   double startEquity = m_startOfDayEquity; // Or HWM for Total Drawdown
   
   // Calculate Current Drawdown % from Start of Day
   double drawdownPercent = 0.0;
   if(startEquity > 0)
      drawdownPercent = ((startEquity - currentEquity) / startEquity) * 100.0;
      
   // Also check Total Drawdown from HWM
   double totalDrawdownPercent = 0.0;
   if(m_highWaterMark > 0)
      totalDrawdownPercent = ((m_highWaterMark - currentEquity) / m_highWaterMark) * 100.0;
      
   double effectiveDD = MathMax(drawdownPercent, totalDrawdownPercent);
   
   // V3.2 "Strict Fortune" Rules:
   // Base Risk is 0.75%
   // DD < 0.5%: 100% Risk (0.75%)
   // DD 0.5% - 1.0%: 67% Risk (0.50%)
   // DD 1.0% - 1.5%: 33% Risk (0.25%)
   // DD 1.5% - 2.0%: 13% Risk (0.10%)
   // DD > 2.0%: STOP (0.0%)
   
   if(effectiveDD < 0.5) return 1.0;
   if(effectiveDD < 1.0) return 0.666; // ~0.50%
   if(effectiveDD < 1.5) return 0.333; // ~0.25%
   if(effectiveDD < 2.0) return 0.133; // ~0.10%
   
   return 0.0; // Hard Stop at 2.0%
  }
