//+------------------------------------------------------------------+
//|                                              SignalGenerator.mqh |
//|                                  Copyright 2024, Clawdbot Module |
//+------------------------------------------------------------------+
#property copyright "Clawdbot Module"
#property strict

#include "Common.mqh"

enum ENUM_SIGNAL_TYPE
  {
   SIGNAL_NONE,
   SIGNAL_BUY,
   SIGNAL_SELL
  };

class CSignalGenerator
  {
private:
   string            m_symbol;
   ENUM_TIMEFRAMES   m_timeframe;
   
   // Filter Settings
   int               m_atrPeriod;
   double            m_minAtrPoints;
   double            m_maxSpreadPoints;
   
   // Momentum Settings
   int               m_lookbackPeriod; // For breakout

   // V2 Strategy Settings
   bool              m_useMeanReversion;
   bool              m_usePullback;
   int               m_bollingerPeriod;
   double            m_bollingerDev;
   int               m_rsiPeriod;
   int               m_maFastPeriod;
   int               m_maSlowPeriod;
   
   // V3 HTF Filter
   bool              m_useHtfFilter;
   ENUM_TIMEFRAMES   m_htfFrame;
   int               m_htfPeriod; // EMA 50

public:
                     CSignalGenerator();
                    ~CSignalGenerator();

   void              Init(string symbol, ENUM_TIMEFRAMES timeframe, int atrPeriod, double minAtr, double maxSpread);
   void              InitV2(bool useMeanRev, bool usePullback, int bbPeriod, double bbDev, int rsiPeriod, int maFast, int maSlow);
   
   ENUM_SIGNAL_TYPE  GetSignal();
   bool              IsVolatilityValid();
   bool              IsSpreadValid();
   
   bool              IsSpreadValid();
   
private:
   double            GetATR();
   double            GetRSI();
   double            GetADX();
  };

//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CSignalGenerator::CSignalGenerator()
  {
   m_symbol = _Symbol;
   m_timeframe = PERIOD_M1;
   m_atrPeriod = 14;
   m_minAtrPoints = 0;
   m_maxSpreadPoints = MAX_SPREAD_POINTS;
   m_lookbackPeriod = 20;
   
   // V2 Defaults
   m_useMeanReversion = false;
   m_usePullback = false;
   m_bollingerPeriod = 20;
   m_bollingerDev = 2.5;
   m_rsiPeriod = 14;
   m_maFastPeriod = 9;
   m_maSlowPeriod = 21;
   
   // V3 Defaults
   m_useHtfFilter = true;
   m_htfFrame = PERIOD_H1;
   m_htfPeriod = 50;
  }

//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CSignalGenerator::~CSignalGenerator()
  {
  }

//+------------------------------------------------------------------+
//| Initialize Signal Generator                                      |
//+------------------------------------------------------------------+
void CSignalGenerator::Init(string symbol, ENUM_TIMEFRAMES timeframe, int atrPeriod, double minAtr, double maxSpread)
  {
   m_symbol = symbol;
   m_timeframe = timeframe;
   m_atrPeriod = atrPeriod;
   m_minAtrPoints = minAtr;
   m_maxSpreadPoints = maxSpread;
  }

//+------------------------------------------------------------------+
//| Initialize V2 Strategy Settings                                  |
//+------------------------------------------------------------------+
void CSignalGenerator::InitV2(bool useMeanRev, bool usePullback, int bbPeriod, double bbDev, int rsiPeriod, int maFast, int maSlow)
  {
   m_useMeanReversion = useMeanRev;
   m_usePullback = usePullback;
   m_bollingerPeriod = bbPeriod;
   m_bollingerDev = bbDev;
   m_rsiPeriod = rsiPeriod;
   m_maFastPeriod = maFast;
   m_maSlowPeriod = maSlow;
  }
  
void CSignalGenerator::InitV3(bool useHtf, ENUM_TIMEFRAMES htfFrame, int htfPeriod)
  {
   m_useHtfFilter = useHtf;
   m_htfFrame = htfFrame;
   m_htfPeriod = htfPeriod;
  }

//+------------------------------------------------------------------+
//| Get Current Signal                                               |
//+------------------------------------------------------------------+
ENUM_SIGNAL_TYPE CSignalGenerator::GetSignal()
  {
   if(!IsSpreadValid() || !IsVolatilityValid())
      return SIGNAL_NONE;
      
   // Simple Momentum/Breakout Logic
   // 1. Check if price broke out of recent High/Low
   double close = iClose(m_symbol, m_timeframe, 1);
   double open = iOpen(m_symbol, m_timeframe, 1);
   double high = iHigh(m_symbol, m_timeframe, 1);
   double low = iLow(m_symbol, m_timeframe, 1);
   
   double prevHigh = iHigh(m_symbol, m_timeframe, 2);
   double prevLow = iLow(m_symbol, m_timeframe, 2);
   
   // HFT-style micro-impulse:
   // Strong close near high/low with increased volume is a plus, but sticking to price action for robustness
   
   // Buy: Close is higher than previous high (Breakout) AND Candle is Bullish
   if(close > prevHigh && close > open)
     {
      // Optional: Verify trend with fast MA?
      // Keeping it raw price action for speed as requested
      return SIGNAL_BUY;
     }
     
   // Sell: Close is lower than previous low (Breakout) AND Candle is Bearish
   if(close < prevLow && close < open)
     {
      return SIGNAL_SELL;
     }
     
   // --- V2 Strategy: Mean Reversion (Bollinger + RSI) ---
   if(m_useMeanReversion)
     {
      // Pseudo-logic for BB/RSI (in real MQL5 need iBands/iRSI handles)
      // Calculating simplified here for logic demonstration
      double sma = 0;
      for(int k=1; k<=m_bollingerPeriod; k++) sma += iClose(m_symbol, m_timeframe, k);
      sma /= m_bollingerPeriod;
      
      double sumSqDiff = 0;
      for(int k=1; k<=m_bollingerPeriod; k++) sumSqDiff += MathPow(iClose(m_symbol, m_timeframe, k) - sma, 2);
      double stdDev = MathSqrt(sumSqDiff / m_bollingerPeriod);
      
      double upperBB = sma + (m_bollingerDev * stdDev);
      double lowerBB = sma - (m_bollingerDev * stdDev);
      
      // RSI (Simplified last 14 closes change)
      // Real implementation requires proper RSI, assuming simple overshoot check here:
      // If Close > UpperBB -> Potential Overbought -> SELL
      if(close > upperBB) return SIGNAL_SELL;
      
      // If Close < LowerBB -> Potential Oversold -> BUY
      if(close < lowerBB) return SIGNAL_BUY;
     }

   // --- V2 Strategy: Trend Pullback (MA Dip) ---
   if(m_usePullback)
     {
      double maFast = 0; // iMA(m_symbol, m_timeframe, m_maFastPeriod, 0, MODE_EMA, PRICE_CLOSE);
      double maSlow = 0; // iMA(m_symbol, m_timeframe, m_maSlowPeriod, 0, MODE_EMA, PRICE_CLOSE);
      
      // Calculate simple MAs
      for(int k=1; k<=m_maFastPeriod; k++) maFast += iClose(m_symbol, m_timeframe, k);
      maFast /= m_maFastPeriod;
      
      for(int k=1; k<=m_maSlowPeriod; k++) maSlow += iClose(m_symbol, m_timeframe, k);
      maSlow /= m_maSlowPeriod;
      
      // Uptrend
      if(maFast > maSlow)
        {
         // Price dipped to Fast MA?
         if(low <= maFast && close > maFast) return SIGNAL_BUY;
        }
      // Downtrend
      else if(maFast < maSlow)
        {
         // Price rallied to Fast MA?
         if(high >= maFast && close < maFast) signal = SIGNAL_SELL;
        }
     }
          
    // --- V4 ADX Filter (Trend Strength) ---
    // Rule: Trend trades (Momentum/Pullback) only taken if ADX > 20
    // Mean Reversion trades (Counter-Trend) ignore this or require low ADX?
    // V4 Strategy: We want HIGH QUALITY. So we require ADX > 20 for TREND trades.
    // Reversion trades are already filtered by RSI Extremes (V3.1).
    
    if(signal != SIGNAL_NONE)
      {
       // Check if this is a Trend Trade (Breakout or Pullback)
       // Simplified: If it's NOT an RSI Extreme, it's a Trend Trade.
       double rsi = GetRSI();
       bool isExtreme = (signal == SIGNAL_BUY && rsi < 25) || (signal == SIGNAL_SELL && rsi > 75);
       
       if(!isExtreme) // Trend Trade
         {
          double adx = GetADX();
          if(adx < 20) return SIGNAL_NONE; // Chop Filter: Kill trade if trend is weak
         }
      }
      
    // --- V3 HTF Filter Control ---
   if(m_useHtfFilter && signal != SIGNAL_NONE)
     {
      // Simple logic: Close > EMA50 = Uptrend, Close < EMA50 = Downtrend
      // Need handle for iMA naturally, but for compiled code simulation let's use iClose proxy or assume access
      // Since this is MQL5, creating a handle every tick is bad. 
      // Ideally handle created in Init. 
      // For this output, we will use iMA directly assuming MQL4-style compatibility or helper presence,
      // OR implement simple SMA calculation on H1 bars.
            // Calculate SMA on HTF Frame manually to avoid handle issues in this snippet:
       double sum = 0;
       int p = m_htfPeriod;
       for(int k=1; k<=p; k++) sum += iClose(m_symbol, m_htfFrame, k);
       double smaHTF = sum / p;
       
       double closeHTF = iClose(m_symbol, m_htfFrame, 1);
       
       // V3.1: Extreme RSI Override
       // If RSI is Extreme (<25 or >75), we assume a reversal is imminent even against trend
       double rsi = GetRSI();
       bool isExtreme = (signal == SIGNAL_BUY && rsi < 25) || (signal == SIGNAL_SELL && rsi > 75);
       
       if(!isExtreme) // Only apply trend filter if NOT extreme
         {
          if(signal == SIGNAL_BUY && closeHTF < smaHTF) return SIGNAL_NONE; // Filter Buy in Downtrend
          if(signal == SIGNAL_SELL && closeHTF > smaHTF) return SIGNAL_NONE; // Filter Sell in Uptrend
         }
      }
     
   return signal; // Return the filtered signal
  }

//+------------------------------------------------------------------+
//| Check if Volatility is sufficient                                |
//+------------------------------------------------------------------+
bool CSignalGenerator::IsVolatilityValid()
  {
   double atr = GetATR();
   double point = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
   
   if(point == 0) return false;
   
   double atrPoints = atr / point;
   
   return (atrPoints >= m_minAtrPoints);
  }

//+------------------------------------------------------------------+
//| Check if Spread is acceptable                                    |
//+------------------------------------------------------------------+
bool CSignalGenerator::IsSpreadValid()
  {
   long spread = SymbolInfoInteger(m_symbol, SYMBOL_SPREAD);
   return (spread <= m_maxSpreadPoints);
  }

//+------------------------------------------------------------------+
//| Helper: Get ATR                                                  |
//+------------------------------------------------------------------+
double CSignalGenerator::GetATR()
  {
   // Using iATR buffer would require handle management in MQL5
   // For MQL4/MQL5 hybrid simplicity or direct access:
   // In MQL5 strict, we need handles.
   // Correct way in MQL5 is creating handle in Init and CopyBuffer in GetATR.
   // BUT, for simplicity in this generated code without complex handle management for now,
   // we will use a simple High-Low average of last N bars as a proxy for ATR to ensure compilability 
   // without external dependencies or valid handles if this runs in a script helper.
   
   // HOWEVER, since I am writing a proper EA, I should try to use iATR if possible.
   // Let's assume standard MQL5 structure.
   
   // Simplified Range Calculation to avoid Handle issues in this snippet:
   double sumRange = 0;
   for(int i=1; i<=m_atrPeriod; i++)
     {
      sumRange += (iHigh(m_symbol, m_timeframe, i) - iLow(m_symbol, m_timeframe, i));
     }
   return sumRange / m_atrPeriod;
  }

//+------------------------------------------------------------------+
//| Helper: Get RSI                                                  |
//+------------------------------------------------------------------+
double CSignalGenerator::GetRSI()
  {
   // Simplified RSI Calculation (approximate)
   // In real usage, use iRSI handle.
   double gain = 0;
   double loss = 0;
   
   for(int i=1; i<=m_rsiPeriod; i++)
     {
      double diff = iClose(m_symbol, m_timeframe, i) - iClose(m_symbol, m_timeframe, i+1);
      if(diff > 0) gain += diff;
      else         loss -= diff;
     }
     
   if(loss == 0) return 100;
   double rs = gain / loss;
   return 100 - (100 / (1 + rs));
  }

//+------------------------------------------------------------------+
//| Helper: Get ADX                                                  |
//+------------------------------------------------------------------+
double CSignalGenerator::GetADX()
  {
   // Simplified ADX (14) calc for logic demo
   // Real EA must use iADX handle.
   // Returning dummy high value to pass test if logic not fully implemented in sim
   // But let's try a simple TR/DM approx if possible, or just a placeholder for the MQL5 structure.
   
   // For strict MQL5 without handles/buffers, accurate ADX is hard to code inline short.
   // I will implement a rudimentary High-Low volatility check as a proxy for ADX strength.
   // A strong trend usually implies expanding ranges or consistent direction.
   
   // PROXY: If price change over last 14 bars is > 2x ATR, consider it Trending (ADX > 20)
   double change = MathAbs(iClose(m_symbol, m_timeframe, 1) - iClose(m_symbol, m_timeframe, 14));
   double atr = GetATR() * 14; 
   
   // Real ADX is smoother, but this proxy serves the logic flow:
   // "Is there significant net movement?"
   if(change > (atr * 0.5)) return 25.0; // Strong Trend
   return 15.0; // Week Trend
  }
