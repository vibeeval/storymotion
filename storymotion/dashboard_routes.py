"""JSON GET payload selection after Handler authentication and path checks.

Transport, locks, downloads, writes and exception handling belong to Handler.
The tuple marks a matched route even when its service payload is None.
"""
from typing import TYPE_CHECKING,Callable,Mapping,Optional,Tuple

if TYPE_CHECKING:
    from .dashboard import Dashboard

JsonGetResponse=Optional[Tuple[int,object]]


def json_get(dashboard:'Dashboard',path:str,*,ui_revision:str,
             current_provenance:Callable[[],Mapping[str,object]],
             capabilities:Callable[[object],object])->JsonGetResponse:
    if path=='/api/catalog':
        return 200,{'catalog':dashboard.catalog,'providers':dashboard.providers,
                    'elevenlabs':dashboard.eleven.config(),'llm':dashboard.llm.config(),'ui_revision':ui_revision,
                    'capabilities':capabilities(dashboard.llm.registry),
                    'runtime_execution_fingerprint':dashboard.runtime_execution,
                    'source_current':dashboard.runtime_execution==current_provenance()['fingerprint']}
    if path=='/api/template-families':return 200,dashboard.template_studio.catalog()
    for prefix,kind in (('/api/reference-catalog/','references'),('/api/style-gallery/','styles')):
        if path.startswith(prefix):
            from .source_catalog import catalog
            return 200,catalog(dashboard,kind,path[len(prefix):])
    if path=='/api/jobs':return 200,{'jobs':dashboard.jobs()}
    if path.startswith('/api/writing-contexts/'):
        from .writing_context import ident
        account=ident(path[len('/api/writing-contexts/'):])
        return 200,dashboard.llm.contexts.state(account)
    if path=='/api/workflows':
        from .workflow_state import workflow_status
        dashboard.assert_runtime_current()
        return 200,workflow_status()
    if path=='/api/keys':return 200,dashboard.key_status()
    if path=='/api/worker':return 200,{'active':dashboard.worker_lock.locked(),'last_result':dashboard.last_worker_result}
    return None
