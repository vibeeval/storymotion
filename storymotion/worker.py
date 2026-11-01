"""Durable local preparation worker. Never dispatches a provider or paid operation."""
import argparse
import json
import uuid
import threading
from .dashboard import Dashboard


class LocalWorker:
    def __init__(self,dashboard,owner=None):self.dashboard=dashboard;self.owner=owner or 'local_'+uuid.uuid4().hex[:12]
    def run_once(self):
        claim=self.dashboard.claim(self.owner)
        if claim is None:return {'status':'idle','provider_calls':0}
        stopped=threading.Event()
        def heartbeat():
            while not stopped.wait(30):
                if not self.dashboard.renew_claim(claim):return
        pulse=threading.Thread(target=heartbeat,daemon=True);pulse.start()
        try:
            result=self.dashboard.prepare(claim['job'],lease_token=claim['token'])
            self.dashboard.finish_claim(claim)
            return {'status':'prepared','job':result['id'],'provider_calls':0,'mode':'local_preparation_only'}
        except Exception:
            try:self.dashboard.finish_claim(claim,error=True)
            except Exception:pass
            return {'status':'failed','job':claim['job'],'provider_calls':0,'error':'Local preparation failed; inspect pinned version and input'}
        finally:stopped.set();pulse.join(timeout=1)


def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',default='work');p.add_argument('--hf');p.add_argument('--max-jobs',type=int,default=1);a=p.parse_args()
    if not 1<=a.max_jobs<=100:p.error('max-jobs must be 1–100')
    d=Dashboard(a.workspace,a.hf);worker=LocalWorker(d);results=[]
    try:
        for _ in range(a.max_jobs):
            result=worker.run_once();results.append(result)
            if result['status']=='idle':break
        print(json.dumps({'results':results,'provider_calls':0},ensure_ascii=False,indent=2))
    finally:d.clear_keys()


if __name__=='__main__':main()
