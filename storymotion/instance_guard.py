"""One active official dashboard server per canonical local POSIX workspace.

The kernel lock is authoritative, not file presence or a PID. Never unlink the
lock inode: a persistent empty file is safe after a normal or abrupt exit.
"""
import errno
import os
import stat
from pathlib import Path
from .security import WorkflowError
from .local_state import guard_workspace, private_directory, validate_open_control, open_control


class WorkspaceInstance:
    def __init__(self,workspace):
        # Initial aliases deliberately share one canonical instance identity.
        self.root=Path(workspace).resolve();self.path=self.root/'.dashboard-instance.lock';self.fd=None;self.pid=None
    def acquire(self):
        if self.fd is not None:return self
        try:from . import file_lock as fcntl
        except ImportError:raise WorkflowError('DASHBOARD_INSTANCE_GUARD_REQUIRES_LOCAL_POSIX') from None
        fd=None
        try:
            # The instance lock's own O_NOFOLLOW/fstat checks below preserve its
            # public error contract; validate all other DB/sidecar controls first.
            guard_workspace(self.root,canonical_alias=False,skip=('.dashboard-instance.lock',))
            private_directory(self.root)
            guard_workspace(self.root,canonical_alias=False,skip=('.dashboard-instance.lock',))
            fd=open_control(self.path,os.O_CREAT|os.O_RDWR|getattr(os,'O_CLOEXEC',0)|getattr(os,'O_NOFOLLOW',0),0o600)
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or (os.name!='nt' and info.st_uid!=os.getuid()):raise WorkflowError('DASHBOARD_INSTANCE_LOCK_FILE_INVALID')
            validate_open_control(fd,private=True)
            os.set_inheritable(fd,False)
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as ex:
                if ex.errno in {errno.EAGAIN,errno.EACCES}:raise WorkflowError('DASHBOARD_WORKSPACE_IN_USE: Bu workspace için başka dashboard etkin; ikinci sunucu açılmadı') from None
                raise
            self.fd=fd;self.pid=os.getpid();return self
        except Exception as ex:
            if fd is not None:os.close(fd)
            if isinstance(ex,WorkflowError):raise
            raise WorkflowError('DASHBOARD_INSTANCE_GUARD_UNAVAILABLE: Güvenilir yerel kilit alınamadı; sunucu açılmadı') from None
    def close(self):
        if self.fd is None:return
        fd=self.fd;self.fd=None
        try:
            if os.getpid()==self.pid:
                from . import file_lock as fcntl
                fcntl.flock(fd,fcntl.LOCK_UN)
        finally:os.close(fd)
    def __enter__(self):return self.acquire()
    def __exit__(self,*args):self.close()
