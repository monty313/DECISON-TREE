//+------------------------------------------------------------------+
//|                                                   S11_Runner.mq5 |
//+------------------------------------------------------------------+
//| STRATEGY: "S11 Runner" -- long-only NY-session drift capture.     |
//|                                                                    |
//| PROVENANCE: the single validated config from the DECISON TREE     |
//| research project (s11.py honest harness, runner_config.json).     |
//| Verified backtest numbers this EA must reproduce (OOS 2024-07..   |
//| 2026-05, recorded per-bar spread): 825 trades, win 31.6%,         |
//| avgR +0.025, coverage 90.2%, pass(traded) 12.9%, 0 DD breaches,   |
//| worst day -2.97%. Full-6yr daily EV +0.109%/day.                  |
//|                                                                    |
//| RULES (do not optimize -- they mirror s11.py harness() exactly):  |
//|  - LONG only, decisions on CLOSED M5 bars.                        |
//|  - Entry: M5 CCI(14) closes above 0 with prior close <= 0,        |
//|    decision minute inside 16:30-23:00 broker time -> market buy   |
//|    on the new bar's first tick.                                   |
//|  - Stop: 2.0 x WILDER ATR(14, M5) below fill. REFUSE the trade    |
//|    if the stop distance <= 15 index points (gap-risk guard).      |
//|  - No take-profit. Exits: +2.5% day-lock (balance OR equity vs    |
//|    day-start balance), 3.5% trailing daily-DD halt (single equity |
//|    peak, both balance & equity checked; true fail line is 4%),    |
//|    23:55 end-of-day flatten, or the server-side stop.             |
//|  - Risk 1.0% of current balance; entry guard: skip if a full      |
//|    stop-out would push the day's trailing DD past 3.5%.           |
//|  - Stop-outs do NOT end the day (next fresh cross re-enters);     |
//|    lock and DD-halt DO end the day.                               |
//|                                                                    |
//| RISK MODULE: same Daily Profit Target Lock-In + Trailing Daily    |
//| DD Halt shape as US30_ExpansionTrigger_v1.mq5, with two deliberate|
//| deviations that match the backtest: (1) the day target baseline   |
//| is DAY-START BALANCE, not initial account balance; (2) ONE equity |
//| peak per day, both balance-DD and equity-DD measured against it.  |
//+------------------------------------------------------------------+
#property copyright "DECISON TREE project - S11 Runner"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//============================ INPUTS =================================
input group "=== Session (broker/server time; FTMO server: NY open 16:30) ==="
input int    InpSessionStartMin  = 990;    // first permissible DECISION minute (16:30)
input int    InpSessionEndMin    = 1380;   // decisions allowed while minute < this (23:00)
input int    InpEodFlatMin       = 1435;   // force-flat everything at/after this minute (23:55)

input group "=== Strategy (match backtest -- do not optimize) ==="
input int    InpCciPeriod        = 14;     // M5 CCI period (PRICE_TYPICAL)
input int    InpAtrPeriod        = 14;     // M5 Wilder ATR period
input double InpSlAtrMult        = 2.0;    // stop = this x Wilder ATR(14, M5)
input double InpMinStopPts       = 15.0;   // refuse trade if stop distance <= this (index points)
input double InpRiskPct          = 1.0;    // % of current balance risked per trade

input group "=== Daily risk module (FTMO spec) ==="
input double InpDayTargetPct     = 2.5;    // day-lock: close + halt at +2.5% of day-start balance
input double InpDdHaltPct        = 3.5;    // trailing-DD safety halt (true FTMO fail line = 4.0)

input group "=== Execution ==="
input int    InpSlippagePts      = 100;    // CTrade deviation in MT5 points (US30 point=0.01 -> 1 idx pt)
input double InpMaxSpreadPts     = 0;      // entry spread cap in index points; 0 = off (backtest had none)
input long   InpMagic            = 110011;

//============================= GLOBALS =================================
int      hCCI = INVALID_HANDLE;
double   gWilderATR = 0;              // maintained once per new M5 bar
datetime gLastM5Bar = 0;              // new-bar detector
datetime gCurrentDay = 0;             // broker midnight of "today"
double   gDayStartBalance = 0;
double   gDayPeakEquity = 0;          // single per-day peak (seeded at day start)
bool     gHaltedToday = false;

//+------------------------------------------------------------------+
//| GlobalVariable persistence names (survive restarts; tester-local) |
//+------------------------------------------------------------------+
string GvName(string suffix) { return "S11R_" + (string)InpMagic + "_" + suffix; }

void SaveState()
  {
   GlobalVariableSet(GvName("day"),  (double)(long)gCurrentDay);
   GlobalVariableSet(GvName("dsb"),  gDayStartBalance);
   GlobalVariableSet(GvName("peak"), gDayPeakEquity);
   GlobalVariableSet(GvName("halt"), gHaltedToday ? 1.0 : 0.0);
  }

bool RestoreState(datetime today)
  {
   if(!GlobalVariableCheck(GvName("day"))) return false;
   if((datetime)(long)GlobalVariableGet(GvName("day")) != today) return false;
   gDayStartBalance = GlobalVariableGet(GvName("dsb"));
   gDayPeakEquity   = GlobalVariableGet(GvName("peak"));
   gHaltedToday     = (GlobalVariableGet(GvName("halt")) >= 1.0);
   return (gDayStartBalance > 0 && gDayPeakEquity > 0);
  }

//+------------------------------------------------------------------+
//| Fallback recovery: day-start balance = balance - today's closed  |
//| P&L (HistorySelect from broker midnight)                          |
//+------------------------------------------------------------------+
double RecomputeDayStartBalance(datetime today)
  {
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   if(!HistorySelect(today, TimeCurrent())) return balance;
   double dayPnL = 0;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      long dealType = HistoryDealGetInteger(ticket, DEAL_TYPE);
      if(dealType != DEAL_TYPE_BUY && dealType != DEAL_TYPE_SELL) continue;
      if(HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      dayPnL += HistoryDealGetDouble(ticket, DEAL_PROFIT)
              + HistoryDealGetDouble(ticket, DEAL_SWAP)
              + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
     }
   return balance - dayPnL;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   hCCI = iCCI(_Symbol, PERIOD_M5, InpCciPeriod, PRICE_TYPICAL);
   if(hCCI == INVALID_HANDLE)
     {
      Print("S11_Runner: failed to create CCI handle");
      return(INIT_FAILED);
     }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePts);
   trade.SetTypeFillingBySymbol(_Symbol);

   datetime today = TimeCurrent() - (TimeCurrent() % 86400);
   gCurrentDay = today;

   if(!RestoreState(today))
     {
      // Fresh day or stale/missing state: recompute conservatively.
      gDayStartBalance = RecomputeDayStartBalance(today);
      gDayPeakEquity   = MathMax(gDayStartBalance,
                         MathMax(AccountInfoDouble(ACCOUNT_EQUITY),
                                 AccountInfoDouble(ACCOUNT_BALANCE)));
      gHaltedToday = false;
      // Re-derive the halted flag from recovered values.
      if(DailyDDBreached() || DailyTargetHit()) gHaltedToday = true;
      SaveState();
     }

   gLastM5Bar = 0;   // force ATR warm-up on first tick
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   if(hCCI != INVALID_HANDLE) IndicatorRelease(hCCI);
  }

//+------------------------------------------------------------------+
//| DAILY RESET / PEAK / CIRCUIT BREAKER (spec module)                 |
//+------------------------------------------------------------------+
void CheckDailyReset()
  {
   datetime today = TimeCurrent() - (TimeCurrent() % 86400);
   if(today != gCurrentDay)
     {
      gCurrentDay      = today;
      gDayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      gDayPeakEquity   = MathMax(AccountInfoDouble(ACCOUNT_EQUITY),
                                 AccountInfoDouble(ACCOUNT_BALANCE));
      gHaltedToday     = false;
      SaveState();
     }
  }

void UpdateDayPeak()
  {
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double hi  = MathMax(eq, bal);
   if(hi > gDayPeakEquity)
     {
      gDayPeakEquity = hi;
      GlobalVariableSet(GvName("peak"), gDayPeakEquity);
     }
  }

bool DailyDDBreached()
  {
   if(gDayPeakEquity <= 0) return false;
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eqDD  = (gDayPeakEquity - eq)  / gDayPeakEquity * 100.0;
   double balDD = (gDayPeakEquity - bal) / gDayPeakEquity * 100.0;
   return (eqDD >= InpDdHaltPct || balDD >= InpDdHaltPct);
  }

bool DailyTargetHit()
  {
   if(gDayStartBalance <= 0) return false;
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double balRet = (bal - gDayStartBalance) / gDayStartBalance * 100.0;
   double eqRet  = (eq  - gDayStartBalance) / gDayStartBalance * 100.0;
   return (balRet >= InpDayTargetPct || eqRet >= InpDayTargetPct);
  }

//+------------------------------------------------------------------+
//| Position helpers (magic-filtered)                                  |
//+------------------------------------------------------------------+
bool HasPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      return true;
     }
   return false;
  }

void CloseMine(string why)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(trade.PositionClose(ticket))
         Print("S11_Runner: closed position (", why, ")");
      else
         Print("S11_Runner: close FAILED (", why, ") retcode=", trade.ResultRetcode());
     }
  }

//+------------------------------------------------------------------+
//| EOD flatten + stale prior-day position recovery                    |
//+------------------------------------------------------------------+
int MinuteOfDay(datetime t)
  {
   MqlDateTime dt;
   TimeToStruct(t, dt);
   return dt.hour * 60 + dt.min;
  }

void CheckEodFlat()
  {
   if(!HasPosition()) return;
   if(MinuteOfDay(TimeCurrent()) >= InpEodFlatMin)
     {
      CloseMine("eod");
      return;
     }
   // Holiday early close: a position from a previous day could survive if the
   // 23:55 flatten never ticked. Close it at the first available tick today.
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if(opened - (opened % 86400) < gCurrentDay)
         CloseMine("stale-prior-day");
     }
  }

void EnforceCircuitBreaker()
  {
   if(gHaltedToday) return;
   if(DailyDDBreached())
     {
      gHaltedToday = true;
      SaveState();
      CloseMine("dd-halt 3.5%");
      Print("S11_Runner: trailing daily DD safety halt -- flat until next day");
      return;
     }
   if(DailyTargetHit())
     {
      gHaltedToday = true;
      SaveState();
      CloseMine("day-lock +2.5%");
      Print("S11_Runner: daily target locked -- day is won, flat until next day");
      return;
     }
  }

//+------------------------------------------------------------------+
//| New-M5-bar detection                                               |
//+------------------------------------------------------------------+
bool NewM5Bar()
  {
   datetime t = iTime(_Symbol, PERIOD_M5, 0);
   if(t == 0 || t == gLastM5Bar) return false;
   gLastM5Bar = t;
   return true;
  }

//+------------------------------------------------------------------+
//| Signal: CCI(14) zero-cross up on the just-closed M5 bar           |
//| (cci[1] > 0 && cci[2] <= 0 -- matches s11.py exactly)             |
//+------------------------------------------------------------------+
bool CciCrossUp()
  {
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(hCCI, 0, 1, 2, buf) < 2) return false;
   if(buf[0] == EMPTY_VALUE || buf[1] == EMPTY_VALUE) return false;
   return (buf[0] > 0.0 && buf[1] <= 0.0);   // buf[0]=shift1 (just closed), buf[1]=shift2
  }

//+------------------------------------------------------------------+
//| Wilder ATR(14, M5) -- manual RMA. MT5's built-in iATR is an SMA   |
//| of true range; the backtest uses Wilder smoothing (ewm 1/14), and |
//| the difference shifts the 15-pt refusal boundary. Recomputed from |
//| scratch once per new M5 bar over ~500 closed bars (cheap, exact). |
//+------------------------------------------------------------------+
double WilderATR()
  {
   const int WARMUP = 500;
   MqlRates rates[];
   ArraySetAsSeries(rates, false);                    // oldest-first
   int got = CopyRates(_Symbol, PERIOD_M5, 1, WARMUP, rates);   // closed bars only
   if(got < InpAtrPeriod * 3) return 0;               // not enough history yet
   double atr = 0;
   for(int i = 1; i < got; i++)
     {
      double tr = MathMax(rates[i].high - rates[i].low,
                  MathMax(MathAbs(rates[i].high - rates[i-1].close),
                          MathAbs(rates[i].low  - rates[i-1].close)));
      if(i <= InpAtrPeriod)
        {
         atr += tr;
         if(i == InpAtrPeriod) atr /= InpAtrPeriod;   // seed = SMA of first N TRs
        }
      else
         atr += (tr - atr) / InpAtrPeriod;            // Wilder RMA
     }
   return atr;
  }

//+------------------------------------------------------------------+
//| LOT SIZE: % of current balance / stop distance.                   |
//| Deviation from the shared CalcLotSize helper: REFUSE (return 0)   |
//| below VOLUME_MIN instead of bumping up -- bumping would overshoot |
//| the 1% risk and break the 3.5% entry-guard math.                  |
//+------------------------------------------------------------------+
double CalcLots(double slDistance, double riskMoney)
  {
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(slDistance <= 0 || tickSize <= 0 || tickValue <= 0) return 0;

   double lossPerLot = (slDistance / tickSize) * tickValue;
   if(lossPerLot <= 0) return 0;

   double lots    = riskMoney / lossPerLot;
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   lots = MathFloor(lots / lotStep) * lotStep;
   if(lots < minLot) return 0;                        // refuse, never bump up
   if(lots > maxLot) { Print("S11_Runner: lots clamped to max (risk < 1%)"); lots = maxLot; }
   return lots;
  }

//+------------------------------------------------------------------+
//| ENTRY PIPELINE (runs once per new M5 bar)                          |
//+------------------------------------------------------------------+
void TryEnter()
  {
   if(HasPosition()) return;                          // one position at a time

   // The new bar's open time IS the decision time of the just-closed bar.
   int m = MinuteOfDay(gLastM5Bar);
   if(m < InpSessionStartMin || m >= InpSessionEndMin) return;

   if(!CciCrossUp()) return;

   gWilderATR = WilderATR();
   if(gWilderATR <= 0) return;                        // warm-up / no history

   double sd = InpSlAtrMult * gWilderATR;             // stop distance in price units
   if(sd <= InpMinStopPts) return;                    // strict: refuse small-ATR trades (gap guard)

   if(InpMaxSpreadPts > 0)
     {
      double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(spread > InpMaxSpreadPts) return;
     }

   // Entry guard: a full stop-out must not push the day's trailing DD past the halt.
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * (InpRiskPct / 100.0);
   if(gDayPeakEquity > 0)
     {
      double worstDD = (gDayPeakEquity - (balance - riskMoney)) / gDayPeakEquity * 100.0;
      if(worstDD >= InpDdHaltPct) return;
     }

   double lots = CalcLots(sd, riskMoney);
   if(lots <= 0) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl  = NormalizeDouble(ask - sd, _Digits);

   // Broker stops-level sanity (US30: sd >= 15 idx pts, virtually always fine)
   long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   if(stopsLevel > 0 && (ask - sl) / _Point < (double)stopsLevel)
     {
      Print("S11_Runner: stop inside broker stops-level, trade skipped");
      return;
     }

   bool ok = trade.Buy(lots, _Symbol, ask, sl, 0.0, "S11_Runner");
   if(!ok)
     {
      uint rc = trade.ResultRetcode();
      // one immediate retry on transient price errors; signal is otherwise consumed
      if(rc == TRADE_RETCODE_REQUOTE || rc == TRADE_RETCODE_PRICE_CHANGED)
        {
         ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         ok = trade.Buy(lots, _Symbol, ask, NormalizeDouble(ask - sd, _Digits), 0.0, "S11_Runner");
        }
      if(!ok)
         Print("S11_Runner: Buy failed retcode=", trade.ResultRetcode(), " (",
               trade.ResultRetcodeDescription(), ")");
     }
   if(ok)
      Print("S11_Runner: BUY ", DoubleToString(trade.ResultVolume(), 2), " @ ",
            DoubleToString(trade.ResultPrice(), _Digits), " sl=", DoubleToString(sl, _Digits),
            " sd=", DoubleToString(sd, 1), "pts risk=", DoubleToString(riskMoney, 2));
  }

//+------------------------------------------------------------------+
//| ONTICK: tick-level risk module first, bar-level entries second    |
//+------------------------------------------------------------------+
void OnTick()
  {
   CheckDailyReset();
   UpdateDayPeak();
   CheckEodFlat();
   EnforceCircuitBreaker();
   if(gHaltedToday) return;

   if(!NewM5Bar()) return;
   TryEnter();
  }

//+------------------------------------------------------------------+
//| SCORING -- day-by-day FTMO pass-rate (same scorer as the          |
//| ExpansionTrigger module: a day passes at >= +2.5% with trailing   |
//| DD < 4.0%). Lets the Strategy Tester report day-pass directly.    |
//+------------------------------------------------------------------+
#define S11_DD_FAIL_LINE 4.0

double agent_standard(double &dailyReturn[], double &dailyMaxDD[], int dailyCount)
  {
   if(dailyCount <= 0) return 0.0;
   int passDays = 0;
   for(int d = 0; d < dailyCount; d++)
     {
      bool ddOk     = dailyMaxDD[d] < S11_DD_FAIL_LINE;
      bool targetOk = dailyReturn[d] >= InpDayTargetPct;
      if(ddOk && targetOk) passDays++;
     }
   return 100.0 * (double)passDays / (double)dailyCount;
  }

double OnTester()
  {
   if(!HistorySelect(0, TimeCurrent())) return 0.0;
   int totalDeals = HistoryDealsTotal();
   if(totalDeals <= 0) return 0.0;

   datetime dayStart = 0;
   double dayOpenBalance = 0;
   double runningBalance = 0;
   // establish starting balance from the initial deposit deal
   for(int i = 0; i < totalDeals; i++)
     {
      ulong t = HistoryDealGetTicket(i);
      if(t != 0 && HistoryDealGetInteger(t, DEAL_TYPE) == DEAL_TYPE_BALANCE)
        { runningBalance = HistoryDealGetDouble(t, DEAL_PROFIT); break; }
     }
   if(runningBalance <= 0) runningBalance = 100000.0;

   double dayPeak = runningBalance;
   double dayWorstDD = 0.0;
   double dailyReturn[]; double dailyMaxDD[];
   int dailyCount = 0;

   for(int i = 0; i < totalDeals; i++)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;

      datetime dealTime = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
      double dealProfit = HistoryDealGetDouble(ticket, DEAL_PROFIT)
                        + HistoryDealGetDouble(ticket, DEAL_SWAP)
                        + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      datetime thisDay = dealTime - (dealTime % 86400);

      if(dayStart == 0)
        { dayStart = thisDay; dayOpenBalance = runningBalance; dayPeak = runningBalance; dayWorstDD = 0; }

      if(thisDay != dayStart)
        {
         double dayRetPct = (runningBalance - dayOpenBalance) / dayOpenBalance * 100.0;
         ArrayResize(dailyReturn, dailyCount + 1); ArrayResize(dailyMaxDD, dailyCount + 1);
         dailyReturn[dailyCount] = dayRetPct; dailyMaxDD[dailyCount] = dayWorstDD; dailyCount++;
         dayStart = thisDay; dayOpenBalance = runningBalance; dayPeak = runningBalance; dayWorstDD = 0;
        }

      runningBalance += dealProfit;
      if(runningBalance > dayPeak) dayPeak = runningBalance;
      double dd = (dayPeak - runningBalance) / dayPeak * 100.0;
      if(dd > dayWorstDD) dayWorstDD = dd;
     }
   if(dayStart != 0)
     {
      double dayRetPct = (runningBalance - dayOpenBalance) / dayOpenBalance * 100.0;
      ArrayResize(dailyReturn, dailyCount + 1); ArrayResize(dailyMaxDD, dailyCount + 1);
      dailyReturn[dailyCount] = dayRetPct; dailyMaxDD[dailyCount] = dayWorstDD; dailyCount++;
     }
   if(dailyCount == 0) return 0.0;
   return agent_standard(dailyReturn, dailyMaxDD, dailyCount);
  }
//+------------------------------------------------------------------+
