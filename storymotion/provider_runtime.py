"""Durable, request-scoped provider execution. Default HTTPS remains disabled.

All tests use MockTransport. Live receipt retrieval/account validation is not claimed.
"""
import datetime
import json
import sqlite3
import time
from pathlib import Path
from .engine import microusd
from .providers import ADAPTERS,HTTPSTransport,MockTransport,Plan,Permit,ProviderError,Response,SecretBroker,execute,safe_public_json,validate_plan,credential_echo
from .security import WorkflowError,canonical,digest,file_hash,within,write_json
from .store import Store,now


class ProviderRuntime:
    def __init__(self,workspace,broker=None,transport=None):
        self.store=Store(workspace);self._owns_broker=broker is None;self.broker=broker or SecretBroker();self.transport=transport or HTTPSTransport()
        try:
            self.store.db.executescript('''
              CREATE TABLE IF NOT EXISTS provider_requests(id TEXT PRIMARY KEY,job TEXT NOT NULL,payload TEXT NOT NULL,
                status TEXT NOT NULL,cap INTEGER,approver TEXT,expires REAL,synthetic INTEGER,receipt TEXT,error TEXT);
              CREATE TABLE IF NOT EXISTS provider_receipts(request TEXT PRIMARY KEY,actual_microusd INTEGER,
                cost_status TEXT NOT NULL,created TEXT NOT NULL);
            ''');self.store.db.commit()
        except BaseException:
            self.close()
            raise
    def close(self):
        if self._owns_broker:self.broker.clear()
        self.store.close()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def registered_job(self,job):
        if self.store.db.execute('SELECT 1 FROM jobs WHERE id=?',(job,)).fetchone():return
        try:
            if self.store.db.execute('SELECT 1 FROM dashboard_jobs WHERE id=?',(job,)).fetchone():return
        except sqlite3.OperationalError:pass
        raise ProviderError('UNKNOWN_JOB_SCOPE')
    def prepare(self,job,plan,estimate_usd,quote_source):
        self.registered_job(job);validate_plan(plan)
        estimate=microusd(estimate_usd)
        if not isinstance(quote_source,str) or not quote_source.strip() or len(quote_source)>500:raise ProviderError('QUOTE_SOURCE_REQUIRED')
        payload={'provider':plan.provider,'capability':plan.capability,'model':plan.model,'url':plan.url,'body':plan.body,
                 'estimate_microusd':estimate,'quote_source':quote_source,'request_hash':plan.fingerprint}
        safe_public_json(payload,self.broker)
        ref=digest({'job':job,'request_hash':plan.fingerprint})
        with self.store.lock():
            old=self.store.db.execute('SELECT payload FROM provider_requests WHERE id=?',(ref,)).fetchone()
            if old and old[0]!=canonical(payload):raise ProviderError('REQUEST_ALREADY_QUOTED_NO_REKEY')
            self.store.db.execute('INSERT OR IGNORE INTO provider_requests(id,job,payload,status) VALUES(?,?,?,?)',(ref,job,canonical(payload),'awaiting_budget'))
            self.store.db.commit();self.store.event(job,'provider','request_prepared',{'request':ref,'provider':plan.provider,'live_default':False})
        return {'request':ref,'plan':plan.public(),'status':self.row(ref)['status'],'estimated_microusd':estimate}
    def row(self,ref):
        row=self.store.db.execute('SELECT * FROM provider_requests WHERE id=?',(ref,)).fetchone()
        if not row:raise ProviderError('UNKNOWN_REQUEST')
        return dict(row)
    def approve(self,ref,max_usd,approved_by,seconds=3600):
        amount=microusd(max_usd)
        if not isinstance(seconds,(int,float)) or not 0<seconds<=86400:raise ProviderError('INVALID_APPROVAL_EXPIRY')
        if not isinstance(approved_by,str) or not approved_by.strip() or len(approved_by)>500:raise ProviderError('APPROVAL_REFERENCE_REQUIRED')
        safe_public_json({'reference':approved_by},self.broker)
        with self.store.lock():
            row=self.row(ref);payload=json.loads(row['payload'])
            if row['status'] not in {'awaiting_budget','approved'}:raise ProviderError('REQUEST_NOT_APPROVABLE')
            if amount<payload['estimate_microusd']:raise ProviderError('BUDGET_TOO_SMALL')
            self.store.db.execute('UPDATE provider_requests SET status=?,cap=?,approver=?,expires=? WHERE id=?',('approved',amount,approved_by,time.time()+seconds,ref));self.store.db.commit()
            self.store.event(row['job'],'provider','request_budget_recorded',{'request':ref,'cap_microusd':amount})
        return {'request':ref,'status':'approved','live_enabled':isinstance(self.transport,HTTPSTransport) and self.transport.allow_live}
    def plan_and_permit(self,row):
        p=json.loads(row['payload']);plan=Plan(p['provider'],p['capability'],p['model'],p['url'],p['body']);validate_plan(plan)
        if p['request_hash']!=plan.fingerprint:raise ProviderError('PINNED_PLAN_MISMATCH')
        permit=Permit(plan.fingerprint,row['job'],row['cap'] if row['cap'] is not None else -1,p['estimate_microusd'],row['expires'] or 0,row['approver'] or '')
        permit.verify(plan,row['job']);return plan,permit
    def run(self,ref,slot):
        with self.store.lock():
            row=self.row(ref)
            if row['status']=='complete':
                receipt=json.loads(row['receipt']);path=within(self.store.root,receipt['file'])
                if not path.is_file() or file_hash(path)!=receipt['sha256']:raise ProviderError('OUTPUT_ARTIFACT_CHANGED_NO_RETRY')
                return {'status':'reused','receipt':receipt}
            if row['status'] in {'dispatching','uncertain'}:raise ProviderError('UNCERTAIN_NO_AUTOMATIC_RETRY')
            if row['status']!='approved':raise ProviderError('REQUEST_NOT_APPROVED')
            plan,permit=self.plan_and_permit(row)
            if isinstance(self.transport,HTTPSTransport) and not self.transport.allow_live:raise ProviderError('LIVE_TRANSPORT_DISABLED')
            if not isinstance(self.transport,(MockTransport,HTTPSTransport)):raise ProviderError('UNTRUSTED_TRANSPORT')
            # Fail before writing dispatch intent for a missing/mismatched/expired credential.
            with self.broker.lease(slot,plan.provider,row['job'],plan.fingerprint,self.transport.synthetic):pass
            self.store.db.execute('UPDATE provider_requests SET status=?,synthetic=? WHERE id=?',('dispatching',int(self.transport.synthetic),ref));self.store.db.commit()
            self.store.event(row['job'],'provider','dispatch_intent_saved',{'request':ref,'synthetic':self.transport.synthetic})
            try:
                receipt=execute(plan,self.broker,slot,permit,self.transport,row['job'],
                    consume=lambda result,key:self._commit_result(row,result,self.transport.synthetic,active_key=key))
                return {'status':'complete_mock' if self.transport.synthetic else 'complete_live_unpriced','receipt':receipt}
            except Exception as error:
                code=error.code if isinstance(error,ProviderError) else 'OUTCOME_UNCERTAIN'
                self.store.db.execute('UPDATE provider_requests SET status=?,error=? WHERE id=?',('uncertain',code,ref));self.store.db.commit()
                self.store.event(row['job'],'provider','outcome_uncertain',{'request':ref,'code':code})
                raise ProviderError(code) from None
    def _commit_result(self,row,result,synthetic,active_key=None):
        if self.broker.contains_secret(result.data):raise ProviderError('CREDENTIAL_ECHO_BLOCKED')
        if result.media_type=='text/plain':safe_public_json({'text':result.data.decode()},self.broker)
        name='output.mp3' if result.media_type=='audio/mpeg' else 'output.txt'
        receipt={**result.public(),'request':row['id'],'job':row['job'],'synthetic':synthetic,'file':'provider-output/'+row['id']+'/'+name,
                 'actual_microusd':0 if synthetic else None,'cost_status':'synthetic_zero' if synthetic else 'provider_invoice_unknown',
                 'review':'pending','audio_alignment':'not_generated' if result.media_type=='audio/mpeg' else 'not_applicable'}
        serialized=safe_public_json(receipt,self.broker)
        if active_key and credential_echo([result.data,receipt],active_key):raise ProviderError('CREDENTIAL_ECHO_BLOCKED')
        out=within(self.store.root,'provider-output/'+row['id']);out.mkdir(parents=True,exist_ok=True)
        path=out/name;tmp=out/(name+'.tmp');tmp.write_bytes(result.data);tmp.replace(path)
        write_json(out/'receipt.json',receipt)
        self.store.db.execute('INSERT OR IGNORE INTO provider_receipts VALUES(?,?,?,?)',(row['id'],receipt['actual_microusd'],receipt['cost_status'],now()))
        self.store.db.execute('UPDATE provider_requests SET status=?,receipt=?,error=NULL WHERE id=?',('complete',canonical(receipt),row['id']));self.store.db.commit()
        self.store.event(row['job'],'provider','receipt_saved',{'request':row['id'],'synthetic':synthetic,'actual_microusd':receipt['actual_microusd']})
        return receipt
    def reconcile_mock(self,ref,response):
        with self.store.lock():
            row=self.row(ref)
            if row['status'] not in {'uncertain','dispatching'} or row['synthetic']!=1:raise ProviderError('MOCK_RECONCILIATION_ONLY')
            p=json.loads(row['payload']);result=ADAPTERS[p['provider']].parse(response,self.broker)
            receipt=self._commit_result(row,result,True)
            self.store.event(row['job'],'provider','mock_receipt_reconciled',{'request':ref})
            return receipt
    def public_status(self,ref):
        row=self.row(ref);p=json.loads(row['payload'])
        return {'request':ref,'job':row['job'],'provider':p['provider'],'model':p['model'],'request_hash':p['request_hash'],
                'status':row['status'],'error_code':row['error'],'cap_microusd':row['cap'],'synthetic':bool(row['synthetic']),
                'receipt':json.loads(row['receipt']) if row['receipt'] else None,'live_receipt_retrieval':'not_implemented; unresolved live outcomes stay blocked'}
