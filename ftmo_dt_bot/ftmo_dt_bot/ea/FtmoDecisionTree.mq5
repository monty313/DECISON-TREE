//+------------------------------------------------------------------+
//|  FtmoDecisionTree.mq5                                            |
//|  AUTO-GENERATED frozen decision tree + FTMO risk manager.        |
//|  One tree, identical to the Python backtest & RL alpha.          |
//|  Attach to ONE chart per symbol (M1). Tree is symbol-agnostic.   |
//+------------------------------------------------------------------+
#property strict
#include <Trade/Trade.mqh>

input double InpRiskPctPerTrade = 0.01;   // % equity risked / trade (0.01 = 0.01%)
input int    InpMaxTradesPerDay = 800;
input double InpMaxDailyLossPct = 5;
input double InpMaxTotalLossPct = 10;
input double InpDailyStopPct    = 3;
input double InpDailyLockPct    = 2;
input double InpTotalStopPct    = 8;
input int    InpAtrPeriod       = 14;
input double InpSlAtrMult       = 1.5;
input double InpTpAtrMult       = 2;
input int    InpMaxHoldBars     = 30;
input int    InpSessStartMin    = 420;   // UTC minutes
input int    InpSessEndMin      = 1260;
input int    InpBrokerUtcOffset = 2;
input bool   InpSwingMode       = false;
input ulong  InpMagic           = 16016;
input int    InpSlippagePts     = 2;

CTrade   trade;
ENUM_TIMEFRAMES TFS[] = { PERIOD_M1,PERIOD_M5,PERIOD_M30,PERIOD_H4 };
int hRSI14[],hRSI4[],hCCI30[],hCCI100[],hSMA200[],hSMA50[],hSMA20[],hSMA4c[],hSMA4h[],hSMA4l[],hATR[],hBB20[],hBB200[];

double   g_init_balance = 0.0;
double   g_day_start_eq = 0.0;
datetime g_cur_day      = 0;
int      g_trades_today = 0;
bool     g_day_blocked  = false;
bool     g_killed       = false;
datetime g_last_bar     = 0;

//------------------------------------------------------------------ helpers
double Buf(int h,int shift){ double t[]; ArraySetAsSeries(t,true);
   if(h==INVALID_HANDLE) return(EMPTY_VALUE);
   if(CopyBuffer(h,0,shift,1,t)!=1) return(EMPTY_VALUE); return(t[0]); }
double BufN(int h,int b,int shift){ double t[]; ArraySetAsSeries(t,true);
   if(h==INVALID_HANDLE) return(EMPTY_VALUE);
   if(CopyBuffer(h,b,shift,1,t)!=1) return(EMPTY_VALUE); return(t[0]); }
double Div(double a,double b){ if(b==0.0||!MathIsValidNumber(a)||!MathIsValidNumber(b)) return(EMPTY_VALUE); return(a/b); }

int UtcMinuteOfDay(){ datetime utc=TimeCurrent()-InpBrokerUtcOffset*3600; MqlDateTime s; TimeToStruct(utc,s); return(s.hour*60+s.min); }
datetime ServerDay(){ MqlDateTime s; TimeToStruct(TimeCurrent(),s); s.hour=0; s.min=0; s.sec=0; return(StructToTime(s)); }
bool InSession(int m){ return(m>=InpSessStartMin && m<InpSessEndMin); }

//------------------------------------------------------------------ the frozen tree
// Frozen decision tree -> +1 long / -1 short / 0 flat.
int EvaluateTree(const double &x[])
{
   if(x[45] <= 0.006051698481355776) // atrfrac_4h
   {
      if(x[9] <= 0.0004042893682319979) // atrfrac_1m
      {
         if(x[12] <= -5.9175075331642795) // rsi14_5m
         {
            if(x[0] <= -25.88040192606681) // rsi14_1m
            {
               return(0);
            }
            else
            {
               if(x[26] <= -149.41941115540874) // cci30_30m
               {
                  return(0);
               }
               else
               {
                  if(x[26] <= -112.62197653591305) // cci30_30m
                  {
                     return(0);
                  }
                  else
                  {
                     return(0);
                  }
               }
            }
         }
         else
         {
            if(x[21] <= 0.0006220844320405189) // atrfrac_5m
            {
               if(x[5] <= 1.2108634816009447) // d_sma50_1m
               {
                  if(x[21] <= 0.0006033564650328657) // atrfrac_5m
                  {
                     return(0);
                  }
                  else
                  {
                     return(0);
                  }
               }
               else
               {
                  if(x[18] <= 0.836725296248011) // d_sma20_5m
                  {
                     return(0);
                  }
                  else
                  {
                     return(0);
                  }
               }
            }
            else
            {
               if(x[32] <= 0.867531832833141) // fan_30m
               {
                  if(x[45] <= 0.004871438196437055) // atrfrac_4h
                  {
                     return(0);
                  }
                  else
                  {
                     return(0);
                  }
               }
               else
               {
                  if(x[15] <= 219.79410645414316) // cci100_5m
                  {
                     return(0);
                  }
                  else
                  {
                     return(0);
                  }
               }
            }
         }
      }
      else
      {
         if(x[9] <= 0.0005260960966166561) // atrfrac_1m
         {
            if(x[18] <= 0.23298035911797488) // d_sma20_5m
            {
               if(x[29] <= -2.272913691082843) // d_sma50_30m
               {
                  if(x[6] <= -0.49452485004620395) // d_sma20_1m
                  {
                     return(0);
                  }
                  else
                  {
                     return(-1);
                  }
               }
               else
               {
                  if(x[25] <= 7.306858985628516) // rsi4_30m
                  {
                     return(0);
                  }
                  else
                  {
                     return(0);
                  }
               }
            }
            else
            {
               if(x[21] <= 0.0008028540557513296) // atrfrac_5m
               {
                  return(1);
               }
               else
               {
                  if(x[22] <= -0.1894696242177112) // stack_hi_5m
                  {
                     return(1);
                  }
                  else
                  {
                     return(0);
                  }
               }
            }
         }
         else
         {
            if(x[27] <= -153.77566190716135) // cci100_30m
            {
               return(0);
            }
            else
            {
               if(x[23] <= -0.15685187963600877) // stack_lo_5m
               {
                  if(x[44] <= 0.12473353108930546) // fan_4h
                  {
                     return(-1);
                  }
                  else
                  {
                     return(1);
                  }
               }
               else
               {
                  if(x[15] <= 80.1629058493483) // cci100_5m
                  {
                     return(0);
                  }
                  else
                  {
                     return(-1);
                  }
               }
            }
         }
      }
   }
   else
   {
      if(x[27] <= 105.88928069270546) // cci100_30m
      {
         if(x[20] <= -0.6516154414732849) // fan_5m
         {
            if(x[20] <= -0.7303439812214827) // fan_5m
            {
               if(x[45] <= 0.007183874163660074) // atrfrac_4h
               {
                  if(x[47] <= -0.5081047783934867) // stack_lo_4h
                  {
                     return(-1);
                  }
                  else
                  {
                     return(-1);
                  }
               }
               else
               {
                  if(x[22] <= -1.249259717564695) // stack_hi_5m
                  {
                     return(1);
                  }
                  else
                  {
                     return(-1);
                  }
               }
            }
            else
            {
               if(x[38] <= -86.29277663787823) // cci30_4h
               {
                  return(1);
               }
               else
               {
                  return(1);
               }
            }
         }
         else
         {
            if(x[21] <= 0.001036815274792901) // atrfrac_5m
            {
               if(x[29] <= -1.5191409461079264) // d_sma50_30m
               {
                  if(x[29] <= -2.8495227819007622) // d_sma50_30m
                  {
                     return(1);
                  }
                  else
                  {
                     return(-1);
                  }
               }
               else
               {
                  if(x[12] <= 0.49628160213411476) // rsi14_5m
                  {
                     return(1);
                  }
                  else
                  {
                     return(-1);
                  }
               }
            }
            else
            {
               if(x[24] <= -20.944810287471938) // rsi14_30m
               {
                  if(x[0] <= -1.6899885422103047) // rsi14_1m
                  {
                     return(1);
                  }
                  else
                  {
                     return(1);
                  }
               }
               else
               {
                  if(x[39] <= -87.10794316574598) // cci100_4h
                  {
                     return(1);
                  }
                  else
                  {
                     return(-1);
                  }
               }
            }
         }
      }
      else
      {
         if(x[33] <= 0.003238580556714106) // atrfrac_30m
         {
            if(x[28] <= 0.9621598093630135) // d_sma200_30m
            {
               if(x[12] <= 2.652594460371862) // rsi14_5m
               {
                  if(x[15] <= 44.28116834303826) // cci100_5m
                  {
                     return(1);
                  }
                  else
                  {
                     return(1);
                  }
               }
               else
               {
                  if(x[20] <= 0.11291911664080745) // fan_5m
                  {
                     return(1);
                  }
                  else
                  {
                     return(1);
                  }
               }
            }
            else
            {
               if(x[13] <= 9.356784618916844) // rsi4_5m
               {
                  if(x[35] <= 0.7081937774209932) // stack_lo_30m
                  {
                     return(1);
                  }
                  else
                  {
                     return(1);
                  }
               }
               else
               {
                  if(x[14] <= 134.78619451702252) // cci30_5m
                  {
                     return(-1);
                  }
                  else
                  {
                     return(-1);
                  }
               }
            }
         }
         else
         {
            if(x[0] <= -2.1873451472542733) // rsi14_1m
            {
               return(-1);
            }
            else
            {
               return(-1);
            }
         }
      }
   }
}


//------------------------------------------------------------------ features (FEATURES order)
bool BuildFeatures(double &x[]){
   ArrayResize(x,48);
   // ---- 1m ----
   double cl0=iClose(_Symbol,TFS[0],1);
   double r14_0=Buf(hRSI14[0],1), r4_0=Buf(hRSI4[0],1);
   double c30_0=Buf(hCCI30[0],1), c100_0=Buf(hCCI100[0],1);
   double s200_0=Buf(hSMA200[0],1), s50_0=Buf(hSMA50[0],1), s20_0=Buf(hSMA20[0],1);
   double s4_0=Buf(hSMA4c[0],4), atr_0=Buf(hATR[0],1);
   double bbu2_0=BufN(hBB20[0],1,1), bbl2_0=BufN(hBB20[0],2,1);
   double b2u_0=BufN(hBB200[0],1,1), b2l_0=BufN(hBB200[0],2,1);
   double sh_0=Buf(hSMA4h[0],5), slw_0=Buf(hSMA4l[0],5);
   double w20_0=(bbu2_0-bbl2_0)/2.0, w200_0=(b2u_0-b2l_0);
   if(cl0==EMPTY_VALUE||r14_0==EMPTY_VALUE||r4_0==EMPTY_VALUE||c30_0==EMPTY_VALUE||c100_0==EMPTY_VALUE||s200_0==EMPTY_VALUE||s50_0==EMPTY_VALUE||s20_0==EMPTY_VALUE||s4_0==EMPTY_VALUE||atr_0==EMPTY_VALUE||bbu2_0==EMPTY_VALUE||bbl2_0==EMPTY_VALUE||b2u_0==EMPTY_VALUE||b2l_0==EMPTY_VALUE||sh_0==EMPTY_VALUE||slw_0==EMPTY_VALUE) return(false);
   x[0]=r14_0-50.0;  x[1]=r4_0-50.0;  x[2]=c30_0;  x[3]=c100_0;
   x[4]=Div(cl0-s200_0,w200_0);  x[5]=Div(cl0-s50_0,w20_0);  x[6]=Div(cl0-s20_0,w20_0);
   x[7]=Div(cl0-bbl2_0,bbu2_0-bbl2_0);  x[8]=Div(cl0-s4_0,w20_0);  x[9]=Div(atr_0,cl0);
   x[10]=Div(cl0-sh_0,w20_0);  x[11]=Div(cl0-slw_0,w20_0);
   // ---- 5m ----
   double cl1=iClose(_Symbol,TFS[1],1);
   double r14_1=Buf(hRSI14[1],1), r4_1=Buf(hRSI4[1],1);
   double c30_1=Buf(hCCI30[1],1), c100_1=Buf(hCCI100[1],1);
   double s200_1=Buf(hSMA200[1],1), s50_1=Buf(hSMA50[1],1), s20_1=Buf(hSMA20[1],1);
   double s4_1=Buf(hSMA4c[1],4), atr_1=Buf(hATR[1],1);
   double bbu2_1=BufN(hBB20[1],1,1), bbl2_1=BufN(hBB20[1],2,1);
   double b2u_1=BufN(hBB200[1],1,1), b2l_1=BufN(hBB200[1],2,1);
   double sh_1=Buf(hSMA4h[1],5), slw_1=Buf(hSMA4l[1],5);
   double w20_1=(bbu2_1-bbl2_1)/2.0, w200_1=(b2u_1-b2l_1);
   if(cl1==EMPTY_VALUE||r14_1==EMPTY_VALUE||r4_1==EMPTY_VALUE||c30_1==EMPTY_VALUE||c100_1==EMPTY_VALUE||s200_1==EMPTY_VALUE||s50_1==EMPTY_VALUE||s20_1==EMPTY_VALUE||s4_1==EMPTY_VALUE||atr_1==EMPTY_VALUE||bbu2_1==EMPTY_VALUE||bbl2_1==EMPTY_VALUE||b2u_1==EMPTY_VALUE||b2l_1==EMPTY_VALUE||sh_1==EMPTY_VALUE||slw_1==EMPTY_VALUE) return(false);
   x[12]=r14_1-50.0;  x[13]=r4_1-50.0;  x[14]=c30_1;  x[15]=c100_1;
   x[16]=Div(cl1-s200_1,w200_1);  x[17]=Div(cl1-s50_1,w20_1);  x[18]=Div(cl1-s20_1,w20_1);
   x[19]=Div(cl1-bbl2_1,bbu2_1-bbl2_1);  x[20]=Div(cl1-s4_1,w20_1);  x[21]=Div(atr_1,cl1);
   x[22]=Div(cl1-sh_1,w20_1);  x[23]=Div(cl1-slw_1,w20_1);
   // ---- 30m ----
   double cl2=iClose(_Symbol,TFS[2],1);
   double r14_2=Buf(hRSI14[2],1), r4_2=Buf(hRSI4[2],1);
   double c30_2=Buf(hCCI30[2],1), c100_2=Buf(hCCI100[2],1);
   double s200_2=Buf(hSMA200[2],1), s50_2=Buf(hSMA50[2],1), s20_2=Buf(hSMA20[2],1);
   double s4_2=Buf(hSMA4c[2],4), atr_2=Buf(hATR[2],1);
   double bbu2_2=BufN(hBB20[2],1,1), bbl2_2=BufN(hBB20[2],2,1);
   double b2u_2=BufN(hBB200[2],1,1), b2l_2=BufN(hBB200[2],2,1);
   double sh_2=Buf(hSMA4h[2],5), slw_2=Buf(hSMA4l[2],5);
   double w20_2=(bbu2_2-bbl2_2)/2.0, w200_2=(b2u_2-b2l_2);
   if(cl2==EMPTY_VALUE||r14_2==EMPTY_VALUE||r4_2==EMPTY_VALUE||c30_2==EMPTY_VALUE||c100_2==EMPTY_VALUE||s200_2==EMPTY_VALUE||s50_2==EMPTY_VALUE||s20_2==EMPTY_VALUE||s4_2==EMPTY_VALUE||atr_2==EMPTY_VALUE||bbu2_2==EMPTY_VALUE||bbl2_2==EMPTY_VALUE||b2u_2==EMPTY_VALUE||b2l_2==EMPTY_VALUE||sh_2==EMPTY_VALUE||slw_2==EMPTY_VALUE) return(false);
   x[24]=r14_2-50.0;  x[25]=r4_2-50.0;  x[26]=c30_2;  x[27]=c100_2;
   x[28]=Div(cl2-s200_2,w200_2);  x[29]=Div(cl2-s50_2,w20_2);  x[30]=Div(cl2-s20_2,w20_2);
   x[31]=Div(cl2-bbl2_2,bbu2_2-bbl2_2);  x[32]=Div(cl2-s4_2,w20_2);  x[33]=Div(atr_2,cl2);
   x[34]=Div(cl2-sh_2,w20_2);  x[35]=Div(cl2-slw_2,w20_2);
   // ---- 4h ----
   double cl3=iClose(_Symbol,TFS[3],1);
   double r14_3=Buf(hRSI14[3],1), r4_3=Buf(hRSI4[3],1);
   double c30_3=Buf(hCCI30[3],1), c100_3=Buf(hCCI100[3],1);
   double s200_3=Buf(hSMA200[3],1), s50_3=Buf(hSMA50[3],1), s20_3=Buf(hSMA20[3],1);
   double s4_3=Buf(hSMA4c[3],4), atr_3=Buf(hATR[3],1);
   double bbu2_3=BufN(hBB20[3],1,1), bbl2_3=BufN(hBB20[3],2,1);
   double b2u_3=BufN(hBB200[3],1,1), b2l_3=BufN(hBB200[3],2,1);
   double sh_3=Buf(hSMA4h[3],5), slw_3=Buf(hSMA4l[3],5);
   double w20_3=(bbu2_3-bbl2_3)/2.0, w200_3=(b2u_3-b2l_3);
   if(cl3==EMPTY_VALUE||r14_3==EMPTY_VALUE||r4_3==EMPTY_VALUE||c30_3==EMPTY_VALUE||c100_3==EMPTY_VALUE||s200_3==EMPTY_VALUE||s50_3==EMPTY_VALUE||s20_3==EMPTY_VALUE||s4_3==EMPTY_VALUE||atr_3==EMPTY_VALUE||bbu2_3==EMPTY_VALUE||bbl2_3==EMPTY_VALUE||b2u_3==EMPTY_VALUE||b2l_3==EMPTY_VALUE||sh_3==EMPTY_VALUE||slw_3==EMPTY_VALUE) return(false);
   x[36]=r14_3-50.0;  x[37]=r4_3-50.0;  x[38]=c30_3;  x[39]=c100_3;
   x[40]=Div(cl3-s200_3,w200_3);  x[41]=Div(cl3-s50_3,w20_3);  x[42]=Div(cl3-s20_3,w20_3);
   x[43]=Div(cl3-bbl2_3,bbu2_3-bbl2_3);  x[44]=Div(cl3-s4_3,w20_3);  x[45]=Div(atr_3,cl3);
   x[46]=Div(cl3-sh_3,w20_3);  x[47]=Div(cl3-slw_3,w20_3);
   for(int k=0;k<ArraySize(x);k++) if(x[k]==EMPTY_VALUE || !MathIsValidNumber(x[k])) return(false);
   return(true);
}

//------------------------------------------------------------------ position helpers
bool HasPosition(){ for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i);
   if(PositionSelectByTicket(tk) && PositionGetString(POSITION_SYMBOL)==_Symbol &&
      PositionGetInteger(POSITION_MAGIC)==(long)InpMagic) return(true);} return(false); }
void CloseMine(string why){ for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i);
   if(PositionSelectByTicket(tk) && PositionGetString(POSITION_SYMBOL)==_Symbol &&
      PositionGetInteger(POSITION_MAGIC)==(long)InpMagic){ trade.PositionClose(tk); } } }

double LotsFor(double atr){
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double risk_cash=InpRiskPctPerTrade/100.0*eq;
   double sl_dist=InpSlAtrMult*atr;
   double tick_val=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tick_sz =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(sl_dist<=0||tick_val<=0||tick_sz<=0) return(0.0);
   double per_lot=sl_dist/tick_sz*tick_val;
   double lots=risk_cash/MathMax(per_lot,1e-9);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   lots=MathFloor(lots/step)*step; lots=MathMax(vmin,MathMin(vmax,lots));
   return(lots);
}

//------------------------------------------------------------------ lifecycle
int OnInit(){
   int n=4;
   ArrayResize(hRSI14,n);ArrayResize(hRSI4,n);ArrayResize(hCCI30,n);ArrayResize(hCCI100,n);
   ArrayResize(hSMA200,n);ArrayResize(hSMA50,n);ArrayResize(hSMA20,n);ArrayResize(hSMA4c,n);
   ArrayResize(hSMA4h,n);ArrayResize(hSMA4l,n);ArrayResize(hATR,n);ArrayResize(hBB20,n);ArrayResize(hBB200,n);
   for(int i=0;i<n;i++){
      hRSI14[i]=iRSI(_Symbol,TFS[i],14,PRICE_CLOSE);
      hRSI4[i] =iRSI(_Symbol,TFS[i],4,PRICE_CLOSE);
      hCCI30[i]=iCCI(_Symbol,TFS[i],30,PRICE_TYPICAL);
      hCCI100[i]=iCCI(_Symbol,TFS[i],100,PRICE_TYPICAL);
      hSMA200[i]=iMA(_Symbol,TFS[i],200,0,MODE_SMA,PRICE_CLOSE);
      hSMA50[i]=iMA(_Symbol,TFS[i],50,0,MODE_SMA,PRICE_CLOSE);
      hSMA20[i]=iMA(_Symbol,TFS[i],20,0,MODE_SMA,PRICE_CLOSE);
      hSMA4c[i]=iMA(_Symbol,TFS[i],4,0,MODE_SMA,PRICE_CLOSE);
      hSMA4h[i]=iMA(_Symbol,TFS[i],4,0,MODE_SMA,PRICE_HIGH);
      hSMA4l[i]=iMA(_Symbol,TFS[i],4,0,MODE_SMA,PRICE_LOW);
      hATR[i]=iATR(_Symbol,TFS[i],14);
      hBB20[i]=iBands(_Symbol,TFS[i],20,0,2.0,PRICE_CLOSE);
      hBB200[i]=iBands(_Symbol,TFS[i],200,0,1.0,PRICE_CLOSE);
   }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePts);
   g_init_balance=AccountInfoDouble(ACCOUNT_BALANCE);
   g_day_start_eq=AccountInfoDouble(ACCOUNT_EQUITY);
   g_cur_day=ServerDay();
   return(INIT_SUCCEEDED);
}

void OnTick(){
   datetime bt=iTime(_Symbol,PERIOD_M1,0);
   if(bt==g_last_bar) { ManageOpen(); return; }   // act once per new M1 bar
   g_last_bar=bt;

   datetime day=ServerDay();
   if(day!=g_cur_day){ g_cur_day=day; g_day_start_eq=AccountInfoDouble(ACCOUNT_EQUITY);
                       g_trades_today=0; g_day_blocked=false; }

   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double day_pl=(eq-g_day_start_eq)/MathMax(g_day_start_eq,1e-9);

   if(eq<=g_day_start_eq*(1.0-InpMaxDailyLossPct/100.0)){ CloseMine("daily_wall"); g_day_blocked=true; return; }
   if(eq<=g_init_balance*(1.0-InpMaxTotalLossPct/100.0)){ CloseMine("total_wall"); g_killed=true; return; }
   if(day_pl<=-InpDailyStopPct/100.0) g_day_blocked=true;
   if(day_pl>= InpDailyLockPct/100.0){ CloseMine("daily_lock"); g_day_blocked=true; }
   if(eq<=g_init_balance*(1.0-InpTotalStopPct/100.0)) g_killed=true;

   ManageOpen();
   if(g_killed||g_day_blocked) return;
   if(HasPosition()) return;
   if(g_trades_today>=InpMaxTradesPerDay) return;
   int mod=UtcMinuteOfDay();
   if(!InSession(mod)) return;

   double x[]; if(!BuildFeatures(x)) return;
   int s=EvaluateTree(x);
   if(s==0) return;

   double atr=Buf(hATR[0],1); if(atr==EMPTY_VALUE||atr<=0) return;
   double lots=LotsFor(atr); if(lots<=0) return;
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double slp=InpSlAtrMult*atr, tpp=InpTpAtrMult*atr;
   bool ok=false;
   if(s>0)  ok=trade.Buy (lots,_Symbol,ask, ask-slp, ask+tpp, "dt_ftmo");
   else     ok=trade.Sell(lots,_Symbol,bid, bid+slp, bid-tpp, "dt_ftmo");
   if(ok) g_trades_today++;
}

void ManageOpen(){
   if(!HasPosition()) return;
   int mod=UtcMinuteOfDay();
   bool near_roll=(mod>=1440-5);
   if(!InpSwingMode && (!InSession(mod)||near_roll)){ CloseMine("session_flat"); return; }
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i);
      if(PositionSelectByTicket(tk) && PositionGetString(POSITION_SYMBOL)==_Symbol &&
         PositionGetInteger(POSITION_MAGIC)==(long)InpMagic){
         datetime ot=(datetime)PositionGetInteger(POSITION_TIME);
         if((TimeCurrent()-ot)>=InpMaxHoldBars*60) trade.PositionClose(tk);
      }
   }
}
//+------------------------------------------------------------------+
