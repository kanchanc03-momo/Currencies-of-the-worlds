"""Currency Atlas Advanced Edition. Run from project root: py final/app.py"""
from __future__ import annotations
import csv,json,math,re
from datetime import timedelta
from functools import lru_cache
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from data_loader import DatasetLoadError, load_dataset
from currency_metadata import COUNTRY_LABELS
ROOT=Path(__file__).resolve().parent; DATA_ROOT=ROOT.parent
def key(x):return re.sub(r'[ _-]','',str(x).lower())
def pick(keys,names):return next((x for x in keys if key(x) in names),None)or next((x for x in keys if any(n in key(x)for n in names)),None)
def load():
 p=next((DATA_ROOT/n for n in ('cleaned_currency_data.csv','cleaned_currency_data.CSV','cleaned_currency_data','cleaned_currency_data.json')if(DATA_ROOT/n).exists()),None)
 if not p:return{}
 rows=json.loads(p.read_text(encoding='utf8'))if p.suffix=='.json'else list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
 if not rows:return{}
 name=pick(rows[0],('currencycode','currency','code','symbol','country','countryname','nation'));value=pick(rows[0],('exchangerate','usdrate','rate','value','close','price'));out={}
 for r in rows:
  try:
   c=str(r[name]).strip().upper();v=float(str(r[value]).replace(',','').replace('$','').strip())
   if c and v>0:out.setdefault(c,[]).append(v)
  except:pass
 return out
def model(v):
 n=len(v)
 if n<2:return v[-1]if v else 0
 sx=sum(range(n));sy=sum(v);sxx=sum(i*i for i in range(n));sxy=sum(i*y for i,y in enumerate(v));m=(n*sxy-sx*sy)/(n*sxx-sx*sx);b=(sy-m*sx)/n
 return max(0,v[-1]+m*(min(12,max(1,round(n*.15)))))
def forecast_horizons(v):
 n=len(v)
 if n<2:return {h:(v[-1] if v else 0) for h in ('7d','1m','6m','12m')}
 sx=sum(range(n));sy=sum(v);sxx=sum(i*i for i in range(n));sxy=sum(i*y for i,y in enumerate(v));m=(n*sxy-sx*sy)/(n*sxx-sx*sx);b=(sy-m*sx)/n
 return {h:max(0,v[-1]+m*days) for h,days in (('7d',7),('1m',30),('6m',182),('12m',365))}
def backtest(rows):
 dates=[row['date'].date() for row in rows]
 values=[row['rate'] for row in rows]
 by_date={day:index for index,day in enumerate(dates)}
 prefix_y=[0.0]
 prefix_xy=[0.0]
 for index,value in enumerate(values):
  prefix_y.append(prefix_y[-1]+value)
  prefix_xy.append(prefix_xy[-1]+index*value)
 result={}
 for label,days in (('7d',7),('1m',30),('6m',182),('12m',365)):
  candidates=[]
  for index,day in enumerate(dates):
   target_index=by_date.get(day+timedelta(days=days))
   if index>=180 and target_index is not None and dates[target_index].year>=2025:
    candidates.append((index,target_index))
  if len(candidates)>12:
   candidates=[candidates[round(k*(len(candidates)-1)/11)] for k in range(12)]
  errors=[]
  for index,target_index in candidates:
   n=index+1
   sx=n*(n-1)/2
   sxx=n*(n-1)*(2*n-1)/6
   slope=(n*prefix_xy[n]-sx*prefix_y[n])/(n*sxx-sx*sx)
   intercept=(prefix_y[n]-slope*sx)/n
   predicted=max(0,values[index]+slope*days)
   actual=values[target_index]
   errors.append(abs(predicted-actual)/actual*100)
  result[label]={'within_5_pct':round(100*sum(error<=5 for error in errors)/len(errors),1) if errors else None,
                 'mape_pct':round(sum(errors)/len(errors),2) if errors else None,
                 'samples':len(errors),
                 'first_target':dates[candidates[0][1]].isoformat() if candidates else None,
                 'last_target':dates[candidates[-1][1]].isoformat() if candidates else None}
 return result
@lru_cache(maxsize=1)
def cached_dataset():
 return load_dataset()
@lru_cache(maxsize=1)
def data():
 grouped={}
 dataset=cached_dataset()
 for row in dataset.rows:
  if row['base']=='USD' and row['date']:grouped.setdefault(row['quote'],[]).append(row)
 latest_date=max((row['date'].date().isoformat() for row in dataset.rows if row['date']),default=None)
 all_dates=sorted({r['date'].date().isoformat() for rows in grouped.values() for r in rows if r['date']})
 out=[]
 for c,rows in grouped.items():
  v=[r['rate'] for r in rows];forecasts=forecast_horizons(v);dates=[r['date'].date().isoformat() if r['date'] else None for r in rows]
  avg=sum(v)/len(v);vol=math.sqrt(sum(((v[i]/v[i-1]-1)*100)**2 for i in range(1,len(v)))/max(1,len(v)-1))if len(v)>1 else 0
  out.append({'currency':c,'country':COUNTRY_LABELS.get(c,'Country not identified in source'),'current':v[-1],'forecast':forecasts['12m'],'forecasts':forecasts,'accuracy':backtest(rows),'observations':len(v),'mean':avg,'min':min(v),'max':max(v),'volatility':vol,'latest_date':dates[-1]})
 result=sorted(out,key=lambda x:x['currency'])
 for item in result:item['dataset_latest_date']=latest_date
 return result
class App(SimpleHTTPRequestHandler):
 def __init__(self, *args, **kwargs):super().__init__(*args, directory=str(ROOT), **kwargs)
 def json(self,v):
  b=json.dumps(v).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urlparse(self.path).path
  if p=='/api/insights':return self.json(data())
  if p.startswith('/api/history/'):
   c=p.rsplit('/',1)[-1].upper();rows=[row for row in cached_dataset().rows if row['base']=='USD' and row['quote']==c and row['date']];return self.json({'currency':c,'rates':[row['rate'] for row in rows],'dates':[row['date'].date().isoformat() for row in rows]})
  if p in ('/all-currencies','/all-currencies.html'):
   b=(ROOT/'all-currencies.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  if p=='/':
   b=(ROOT/'index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  return super().do_GET()
if __name__=='__main__':
 print('Currency Atlas Advanced Edition at http://127.0.0.1:8000');ThreadingHTTPServer(('127.0.0.1',8000),App).serve_forever()
