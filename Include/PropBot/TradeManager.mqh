//+------------------------------------------------------------------+
//|                                                TradeManager.mqh |
//|                                  Copyright 2024, Clawdbot Module |
//+------------------------------------------------------------------+
#property copyright "Clawdbot Module"
#property strict

#include <Trade/Trade.mqh>
#include "Common.mqh"

class CTradeManager
  {
private:
   CTrade            m_trade;
   string            m_symbol;
   ulong             m_magic;
   double            m_trailingStep;
   
public:
                     CTradeManager();
                    ~CTradeManager();

   void              Init(string symbol, ulong magic);
   
   bool              OpenBuy(double volume, double slPoints, double tpPoints, string comment="");
   bool              OpenSell(double volume, double slPoints, double tpPoints, string comment="");
   
   void              ManageTrades(); // Trailing Stop logic
   void              CloseAll();
   
   int               CountTrades();
  };

//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CTradeManager::CTradeManager()
  {
   m_symbol = _Symbol;
   m_magic = MAGIC_NUMBER;
   m_trailingStep = 10 * _Point; // Default fallback
  }

//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CTradeManager::~CTradeManager()
  {
  }

//+------------------------------------------------------------------+
//| Init                                                             |
//+------------------------------------------------------------------+
void CTradeManager::Init(string symbol, ulong magic)
  {
   m_symbol = symbol;
   m_magic = magic;
   m_trade.SetExpertMagicNumber(magic);
   m_trade.SetMarginMode();
   m_trade.SetTypeFillingBySymbol(symbol);
  }

//+------------------------------------------------------------------+
//| Open Buy Trade                                                   |
//+------------------------------------------------------------------+
bool CTradeManager::OpenBuy(double volume, double slPoints, double tpPoints, string comment="")
  {
   double ask = SymbolInfoDouble(m_symbol, SYMBOL_ASK);
   double point = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
   
   double sl = (slPoints > 0) ? ask - slPoints * point : 0;
   double tp = (tpPoints > 0) ? ask + tpPoints * point : 0;
   
   return m_trade.Buy(volume, m_symbol, ask, sl, tp, comment);
  }

//+------------------------------------------------------------------+
//| Open Sell Trade                                                  |
//+------------------------------------------------------------------+
bool CTradeManager::OpenSell(double volume, double slPoints, double tpPoints, string comment="")
  {
   double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
   
   double sl = (slPoints > 0) ? bid + slPoints * point : 0;
   double tp = (tpPoints > 0) ? bid - tpPoints * point : 0;
   
   return m_trade.Sell(volume, m_symbol, bid, sl, tp, comment);
  }

//+------------------------------------------------------------------+
//| Manage Trades (Simple Trailing)                                  |
//+------------------------------------------------------------------+
void CTradeManager::ManageTrades()
  {
   // Basic Breakeven / Trailing Logic
   // Iterate positions
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
        {
         if(PositionGetString(POSITION_SYMBOL) == m_symbol && PositionGetInteger(POSITION_MAGIC) == m_magic)
           {
             // Implement Trailing Logic here if needed
             // For now, keep it simple: Fixed TP/SL is safest for Prop Firms to avoid over-trading modifications
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Close All Trades                                                 |
//+------------------------------------------------------------------+
void CTradeManager::CloseAll()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
        {
         if(PositionGetString(POSITION_SYMBOL) == m_symbol && PositionGetInteger(POSITION_MAGIC) == m_magic)
           {
            m_trade.PositionClose(ticket);
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Count Open Trades                                                |
//+------------------------------------------------------------------+
int CTradeManager::CountTrades()
  {
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
        {
         if(PositionGetString(POSITION_SYMBOL) == m_symbol && PositionGetInteger(POSITION_MAGIC) == m_magic)
           {
            count++;
           }
        }
     }
   return count;
  }
