"""Fixed bounded template preparations; no network, native render or provider."""
import json
import threading
from .engine import Engine
from .family_receipts import record_receipt
from .family_jobs import read_owned
from .local_state import guard_private, guard_workspace
from .security import WorkflowError,digest,write_json
from .template_families import capabilities,fields,make_brief

class TemplateStudio:
    def __init__(self,dashboard):
        self.dashboard=dashboard
        self.lock=threading.RLock()
        from .family_jobs import FamilyJobs
        self.history=FamilyJobs(self)

    def catalog(self):
        return capabilities()

    def field_action(self,operation,data):
        from .template_fields import action
        return action(self,operation,data)

    def prepare(self,data):
        self.dashboard.clean(data)
        fields(data,{'account','spec','engine'},{'claims','source_revision','canon_revision','planning'})
        if data['engine'] not in ('hyperframes','remotion'):raise WorkflowError('TEMPLATE_ENGINE_REQUIRED')
        claims=data.get('claims',[])
        binding=self.dashboard.llm.contexts.bind(data['account'],data.get('source_revision'),data.get('canon_revision')) if claims or data.get('source_revision') is not None or data.get('canon_revision') is not None else None
        subject=self.dashboard.taxonomy.bind(data['account'],data['planning']) if 'planning' in data else None
        brief=make_brief(data['account'],data['spec'],subject=subject,claims=claims,production_context=binding)
        with self.dashboard.revision_lock,self.lock:
            self.dashboard.clean(brief)
            self.dashboard.assert_runtime_current()
            if binding is not None:self.dashboard.llm.contexts.assert_current(data['account'],binding)
            if 'planning' in data and self.dashboard.taxonomy.bind(data['account'],data['planning'])!=subject:
                raise WorkflowError('TAXONOMY_SELECTION_CHANGED')
            root=guard_workspace(self.dashboard.workspace,canonical_alias=False)
            folder=guard_private(root,'family-inputs','dir');folder.mkdir(mode=0o700,exist_ok=True)
            source=guard_private(root,'family-inputs/'+digest(brief)+'.json')
            if source.exists():
                if json.loads(source.read_text())!=brief:raise WorkflowError('TEMPLATE_INPUT_CHANGED')
            else:write_json(source,brief)
            workspace=guard_private(root,'family-renders','dir')
            with Engine(workspace,self.dashboard.hf) as engine:
                job=engine.create(source,render_engine=data['engine'])['job']
                engine.run(job,'prepare')
                with engine.store.lock():
                    payload=engine.payload(job);self.history.clean(payload)
                    stage=engine.store.stage(job,'prepare')
                    manifest,_=self.history.verified(engine.store.root,job,payload,stage)
                    source_bytes=read_owned(root,source.relative_to(root).as_posix(),1024*1024)
                    if json.loads(source_bytes)!=payload['brief']:raise WorkflowError('TEMPLATE_INPUT_CHANGED')
                    record_receipt(root,job,payload,source_bytes,manifest)
            return {'job':job,'account':data['account'],'family':brief['template_family']['id'],
                    'engine':data['engine'],'status':'prepare_only','manifest':manifest,
                    'actual_render':False,'provider_calls':0,'publication_acceptance':'pending',
                    'workspace_relative':'family-renders',
                    'ref':{'kind':'family','account':data['account'],'id':job},
                    'detail_url':'/api/family-jobs/'+data['account']+'/'+job}
