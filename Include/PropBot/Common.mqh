//+------------------------------------------------------------------+
//|                                                       Common.mqh |
//|                                  Copyright 2024, Clawdbot Module |
//+------------------------------------------------------------------+
#property copyright "Clawdbot Module"
#property link      "https://www.google.com"
#property strict

//--- Enums
enum ENUM_ACCOUNT_MODE
  {
   MODE_CHALLENGE, // Challenge (Aggressive)
   MODE_FUNDED     // Funded (Conservative)
  };

enum ENUM_PROFIT_TAKE_ACTION
  {
   ACTION_NONE,
   ACTION_REDUCE_RISK,
   ACTION_STOP_TRADING,
   ACTION_HARD_STOP
  };

//--- Constants
#define MAGIC_NUMBER 123456
#define TRAILING_STEP_ATR 0.5
#define MAX_SLIPPAGE 3
#define MAX_SPREAD_POINTS 50 // 5 pips
