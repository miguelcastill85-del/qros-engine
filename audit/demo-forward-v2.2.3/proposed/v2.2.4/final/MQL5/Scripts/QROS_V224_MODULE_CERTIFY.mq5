#property strict
#property script_show_inputs

#include <QROS_DEMO_BUS_v2_2_4.mqh>

input string InpTemplateName="QROS_V224_MODULE_NATIVE";
input string InpReceiptFile="QROS_V224_MODULE_CERT.csv";
input string InpExpectedExpertName="";
input int    InpModuleId=1;
input int    InpTimeoutSeconds=900;
input int    InpMaxHeartbeatAgeMs=3000;
input int    InpStableSamples=8;
input long   InpExpectedSourceToken=0;

double GvOrMinusOne(const string key)
  {
   if(!GlobalVariableCheck(key))
      return -1.0;
   return GlobalVariableGet(key);
  }

void Receipt(const string decision,
             const string reason,
             const string actual,
             const long age,
             const int state,
             const bool saved)
  {
   long sync=0;
   long lastbar=0;

   SeriesInfoInteger(_Symbol,_Period,SERIES_SYNCHRONIZED,sync);
   SeriesInfoInteger(_Symbol,_Period,SERIES_LASTBAR_DATE,lastbar);

   double init_done=-1.0;
   double init_total=-1.0;

   if(InpModuleId==QROS_MOD_DIV3)
     {
      init_done=GvOrMinusOne("Q24.3.INIT_DONE");
      init_total=GvOrMinusOne("Q24.3.INIT_TOTAL");
     }

   int file=FileOpen(InpReceiptFile,
                     FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,
                     ',');

   if(file==INVALID_HANDLE)
      return;

   FileWrite(file,
             "decision","reason","template",
             "expected_expert","actual_expert",
             "module_id","state","heartbeat_age_ms",
             "init_done","init_total","init_pct",
             "saved","symbol","period",
             "series_sync","series_lastbar",
             "server","trade_mode","build","producer_owner","producer_epoch","source_token","watermark_ms");

   double pct=-1.0;
   if(init_total>0.0)
      pct=100.0*init_done/init_total;

   FileWrite(file,
             decision,reason,InpTemplateName,
             InpExpectedExpertName,actual,
             InpModuleId,state,age,
             init_done,init_total,DoubleToString(pct,6),
             saved?1:0,_Symbol,EnumToString(_Period),
             sync,TimeToString((datetime)lastbar,TIME_DATE|TIME_MINUTES),
             AccountInfoString(ACCOUNT_SERVER),
             (long)AccountInfoInteger(ACCOUNT_TRADE_MODE),
             (long)TerminalInfoInteger(TERMINAL_BUILD),
             QrosBusProducerOwner(InpModuleId),QrosBusProducerEpoch(InpModuleId),GvOrMinusOne(QrosBusKey(InpModuleId,"SOURCE_TOKEN")),QrosBusWatermarkMs(InpModuleId));

   FileFlush(file);
   FileClose(file);
  }

void OnStart()
  {
   long deadline=(long)GetTickCount64()+((long)InpTimeoutSeconds*1000L);

   int stable=0;
   string actual="";
   long age=LONG_MAX;
   int state=QROS_STATE_OFF;

   while((long)GetTickCount64()<deadline && !IsStopped())
     {
      actual=ChartGetString(0,CHART_EXPERT_NAME);
      age=QrosBusHeartbeatAgeMs(InpModuleId);
      state=QrosBusState(InpModuleId);

      if(actual==InpExpectedExpertName &&
         state==QROS_STATE_READY &&
         age<=InpMaxHeartbeatAgeMs &&
         QrosBusProducerOwner(InpModuleId)>0 &&
         QrosBusProducerEpoch(InpModuleId)>0 &&
         InpExpectedSourceToken>0 &&
         GvOrMinusOne(QrosBusKey(InpModuleId,"SOURCE_TOKEN"))==(double)InpExpectedSourceToken)
         stable++;
      else
         stable=0;

      if(stable>=InpStableSamples)
         break;

      Sleep(500);
     }

   if(stable<InpStableSamples)
     {
      Receipt("FAIL","MODULE_NOT_READY",actual,age,state,false);
      return;
     }

   ResetLastError();
   bool ok=ChartSaveTemplate(0,InpTemplateName);
   int err=(int)GetLastError();

   if(!ok)
     {
      Receipt("FAIL",
              "TEMPLATE_SAVE_ERROR_"+IntegerToString(err),
              actual,age,state,false);
      return;
     }

   Receipt("PASS","MODULE_READY_TEMPLATE_SAVED",actual,age,state,true);
  }
