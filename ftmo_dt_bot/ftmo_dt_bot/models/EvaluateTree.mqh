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
