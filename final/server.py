"""Run this final server: py final/server.py"""
from __future__ import annotations
import json, math
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from data_loader import BACKEND_DIR, DatasetLoadError, load_dataset

HORIZONS = {"7d": 7, "1m": 30, "6m": 182, "12m": 365}
def forecast(values, days=365):
    n=len(values)
    if n<2:return values[-1]
    sx=sum(range(n));sy=sum(values);sxx=sum(i*i for i in range(n));sxy=sum(i*y for i,y in enumerate(values));slope=(n*sxy-sx*sy)/(n*sxx-sx*sx);intercept=(sy-slope*sx)/n
    return max(0,values[-1]+slope*days)
def analytics(dataset):
    grouped={}
    for row in dataset.rows: grouped.setdefault(row['quote'],[]).append(row)
    result=[]
    for currency, rows in grouped.items():
        values=[row['rate'] for row in rows]; mean=sum(values)/len(values); vol=math.sqrt(sum(((values[i]/values[i-1]-1)*100)**2 for i in range(1,len(values)))/max(1,len(values)-1)) if len(values)>1 else 0
        result.append({'currency':currency,'current':values[-1],'forecast':forecast(values),'forecasts':{key:forecast(values,days) for key,days in HORIZONS.items()},'observations':len(values),'mean':mean,'min':min(values),'max':max(values),'volatility':vol})
    return sorted(result,key=lambda x:x['currency'])
class Server(SimpleHTTPRequestHandler):
    _dataset_cache=None
    def response(self,status,payload):
        body=json.dumps(payload,default=str).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def dataset(self):
        if Server._dataset_cache is not None:return Server._dataset_cache,None
        try:
            Server._dataset_cache=load_dataset()
            return Server._dataset_cache,None
        except DatasetLoadError as error:return None,str(error)
    def do_GET(self):
        route=urlparse(self.path).path
        if route=='/api/dataset/summary':
            dataset,error=self.dataset();return self.response(200,dataset.summary() if dataset else {'error':error})
        if route=='/api/insights':
            dataset,error=self.dataset();return self.response(200,analytics(dataset) if dataset else {'error':error,'items':[]})
        if route.startswith('/api/history/'):
            dataset,error=self.dataset()
            if not dataset:return self.response(422,{'error':error})
            currency=unquote(route.rsplit('/',1)[-1]).upper();rows=[row for row in dataset.rows if row['quote']==currency]
            return self.response(200,{'currency':currency,'rates':[row['rate'] for row in rows],'dates':[row['date'].date().isoformat() if row['date'] else None for row in rows]})
        if route=='/all-currencies' or route=='/all-currencies.html':
            page=(BACKEND_DIR/'all-currencies.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(page)));self.end_headers();self.wfile.write(page);return
        if route=='/':
            page=(BACKEND_DIR/'index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(page)));self.end_headers();self.wfile.write(page);return
        return super().do_GET()
if __name__=='__main__':
    print('Currency Atlas final server: http://127.0.0.1:8000');ThreadingHTTPServer(('127.0.0.1',8000),Server).serve_forever()
