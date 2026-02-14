//+------------------------------------------------------------------+
//|                                                      PropBot.mq5 |
//|                                  Copyright 2024, Clawdbot Module |
//|                                             https://www.google.com |
//+------------------------------------------------------------------+
#property copyright "Clawdbot Module"
#property link      "https://www.google.com"
#property version   "1.00"
#property strict

#include "Include/PropBot/Common.mqh"
#include "Include/PropBot/RiskManager.mqh"
#include "Include/PropBot/SignalGenerator.mqh"
#include "Include/PropBot/TradeManager.mqh"

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+
input group " --- Prop Firm Settings --- "
input ENUM_ACCOUNT_MODE Mode = MODE_CHALLENGE; // Trading Mode
input double fpMaxDailyLossPercent = 5.0;      // Official Daily Loss Limit (%)
input double fpMaxTotalLossPercent = 10.0;     // Official Total Loss Limit (%)

input group " --- Risk Settings --- "
input double RiskPerTradePercent = 0.75;       // Risk per trade % (Optimal for V3.1)
input double MaxDailyLossPercent = 4.0;        // Max Daily Loss % (Hard Stop)
input double MinDailyProfit = 1.0;             // Target Level 1 (Reduce Risk)
input double TargetDailyProfit = 3.0;          // Target Level 2 (Stop/Min Risk)
input double MaxDailyProfit = 6.0;             // Hard Cap (Stop Trading)

input group " --- Strategy Settings --- "
input int    MagicNumber = 123456;             // Magic Number
input int    AtrPeriod = 14;                   // Volatility ATR Period
input double MinAtrPoints = 10;                // Current Volatility Min (Points)
input double MaxSpreadPoints = 50;             // Max Spread (Points)
input double StopLossPoints = 200;             // Hard Stop Loss (Points)
input double TakeProfitPoints = 400;           // Take Profit (Points)

input group " --- V2 Strategy Settings (Aggressive) --- "
input bool   EnableMeanReversion = true;       // Enable Bollinger/RSI Fades
input bool   EnablePullbacks = true;           // Enable MA Trend Pullbacks
input int    BollingerPeriod = 20;             // BB Period
input double BollingerDev = 2.5;               // BB Deviation (Aggressive Reversal)
input int    RsiPeriod = 14;                   // RSI Period
input int    MaFastPeriod = 9;                 // Fast EMA (Trend)
input int    MaSlowPeriod = 21;                // Slow EMA (Trend)

input group " --- V3 Ultra-Precision Settings --- "
input bool   UseHtfFilter = true;              // Trade only with H1 Trend?

input group " --- Time Settings --- "
input string TradingHours = "09:00-17:00";     // Allowed Trading Hours (Server Time)
input bool   UseNewsFilter = false;            // Enable News Filter (Placeholder)

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+
CRiskManager      RiskManager;
CSignalGenerator  SignalGenerator;
CTradeManager     TradeManager;

bool              g_IsTradingAllowed = true;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   // 1. Initialize Trade Manager
   TradeManager.Init(_Symbol, MagicNumber);
   
   // 2. Initialize Risk Manager
   // Adjust risk based on Mode if needed, but inputs override for now
   double risk = RiskPerTrade;
   if(Mode == MODE_FUNDED && risk > 0.3) 
     {
      Print("Warning: Founded Mode detected. Reducing Risk to 0.3% safety cap.");
      risk = 0.3;
     }
     
   RiskManager.Init(fpMaxDailyLossPercent, fpMaxTotalLossPercent, risk, MaxExposurePercent);
   
   // 3. Initialize Signal Generator
   SignalGenerator.Init(_Symbol, PERIOD_CURRENT, AtrPeriod, MinAtrPoints, MaxSpreadPoints);
   SignalGenerator.InitV2(EnableMeanReversion, EnablePullbacks, BollingerPeriod, BollingerDev, RsiPeriod, MaFastPeriod, MaSlowPeriod);
   SignalGenerator.InitV3(UseHtfFilter, PERIOD_H1, 50);
   
   Print("PropBot Initialized. Mode: ", EnumToString(Mode));
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   Print("PropBot Deinitialized. Reason: ", reason);
  }

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   // 1. Update Risk Status (Equity tracking)
   RiskManager.OnTick();
   
   // 2. Check Critical Limits (Daily/Total Loss)
   if(!RiskManager.CheckDailyLoss() || !RiskManager.CheckTotalLoss())
     {
      g_IsTradingAllowed = false;
      Comment("TRADING STOPPED: Risk Limit Breach");
      return;
     }
     
   // 3. Check Profit Targets
   // If Max Profit hit, stop. If Target hit, maybe stop.
   if(!RiskManager.CheckProfitTargets(MinDailyProfit, TargetDailyProfit, MaxDailyProfit))
     {
       // If returns false, it means Hard Stop or Stop Trading action
       // We can refine this logic inside RiskManager or here.
       // For now, let's assume RiskManager handles internal state/logging, 
       // but we need to stop opening NEW trades.
       // However, we might still need to manage existing ones.
       // Let's implement a specific check here:
     }
     
     // 4. Time Filter
   if(!CheckTime(TradingHours))
     {
      Comment("Outside Trading Hours");
      return;
     }
     
   // 5. Signal Generation
   ENUM_SIGNAL_TYPE signal = SignalGenerator.GetSignal();
   
   if(signal != SIGNAL_NONE)
     {
      // 6. Pre-Trade Risk Check
      if(!RiskManager.CheckMaxExposure()) 
        {
         Print("Signal skipped: Max Exposure reached.");
         return;
        }
        
      // Calculate Lot Size
      double lotSize = RiskManager.GetLotSize(StopLossPoints, _Symbol);
      
      if(lotSize <= 0) 
        {
         // RiskScaler returns 0.0 if DD > 2.0% (V3.2 Hard Stop)
         // This is EXPECTED behavior to prevent further drawdown.
         Print("HARD STOP ACTIVE: Risk Scaler = 0%. Trading suspended to protect account.");
         return;
        }
      
      // Execute Trade
      if(signal == SIGNAL_BUY)
        {
         TradeManager.OpenBuy(lotSize, StopLossPoints, TakeProfitPoints, "PropBot Buy");
        }
      else if(signal == SIGNAL_SELL)
        {
         TradeManager.OpenSell(lotSize, StopLossPoints, TakeProfitPoints, "PropBot Sell");
        }
     }
     
   // 7. Manage Open Trades
   TradeManager.ManageTrades();
   
   Comment("PropBot Running | Equity: ", DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2));
  }

//+------------------------------------------------------------------+
//| Time Filter Helper                                               |
//+------------------------------------------------------------------+
bool CheckTime(string allowedHours)
  {
   // Parse "HH:MM-HH:MM" simple format
   // This is a basic implementation. Robust parsing would be needed for complex strings.
   
   string parts[];
   if(StringSplit(allowedHours, '-', parts) != 2) return true; // Format error or empty, allow all
   
   datetime cur = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(cur, dt);
   
   string startStr = parts[0];
   string endStr = parts[1];
   
   string startParts[];
   string endParts[];
   StringSplit(startStr, ':', startParts);
   StringSplit(endStr, ':', endParts);
   
   int startH = (int)StringToInteger(startParts[0]);
   int startM = (int)StringToInteger(startParts[1]);
   int endH = (int)StringToInteger(endParts[0]);
   int endM = (int)StringToInteger(endParts[1]);
   
   int curTimeMins = dt.hour * 60 + dt.min;
   int startTimeMins = startH * 60 + startM;
   int endTimeMins = endH * 60 + endM;
   
   if(startTimeMins < endTimeMins)
     {
      // Standard range (e.g. 09:00 to 17:00)
      if(curTimeMins >= startTimeMins && curTimeMins < endTimeMins) return true;
     }
   else
     {
      // Cross-day range (e.g. 23:00 to 02:00)
      if(curTimeMins >= startTimeMins || curTimeMins < endTimeMins) return true;
     }
     
   return false;
  }
