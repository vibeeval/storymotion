"""One owned native worker across the normal and family render services."""
import threading
import uuid
from .security import WorkflowError


class WorkerStart:
    """Atomically admit the owned target or permanently close its entry gate.

    A start() exception says nothing about target entry. Once admitted, only
    that target's existing completion path can relinquish its service ownership.
    Aborting before admission also fences a delayed native-thread bootstrap.
    """
    def __init__(self,target,args):
        self.target=target;self.args=args;self.lock=threading.Lock()
        self.entered=threading.Event();self.aborted=False

    def run(self):
        with self.lock:
            if self.aborted or self.entered.is_set():return
            self.entered.set()
        self.target(*self.args)

    def abort_before_entry(self):
        with self.lock:
            if self.entered.is_set():return False
            self.aborted=True;return True


def join_owned(thread, timeout):
    if getattr(thread,'_storymotion_start_unconfirmed',False) and thread.ident is None:
        raise WorkflowError('DASHBOARD_BACKGROUND_WORK_ACTIVE: Worker startup is unconfirmed; workspace ownership is retained')
    if thread is not threading.current_thread():thread.join(timeout)


def require_settled_start(active):
    if any(getattr(owned[1],'_storymotion_start_unconfirmed',False) for owned in active):
        raise WorkflowError('DASHBOARD_BACKGROUND_WORK_ACTIVE: Worker completion is unconfirmed; workspace ownership is retained')


class RenderSlot:
    def __init__(self):
        self.lock = threading.Lock()
        self.current = None

    def claim(self, owner):
        with self.lock:
            if self.current is not None:
                return None
            token = uuid.uuid4().hex
            self.current = (token, owner)
            return token

    def release(self, token):
        with self.lock:
            if self.current is not None and self.current[0] == token:
                self.current = None
