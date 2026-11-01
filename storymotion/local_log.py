"""Bounded owned diagnostics: static event codes and allowlisted error classes."""
import logging
from logging.handlers import RotatingFileHandler
import os
import stat
import threading
import time

from .local_state import guard_control, guard_workspace, open_control, validate_open_control, private_directory
from .security import WorkflowError

CODES={'LOCAL_READ_FAILED','LOCAL_WRITE_FAILED','LOCAL_HTTP_FAILED'}
KINDS={'OSError','FileNotFoundError','PermissionError','ValueError','KeyError','TypeError',
       'RuntimeError','Error','DatabaseError','OperationalError','IntegrityError','ProgrammingError',
       'OverflowError','RecursionError','UnicodeError','JSONDecodeError','WorkflowError'}


class OwnedRotatingHandler(RotatingFileHandler):
    def _open(self):
        descriptor=open_control(self.baseFilename,os.O_WRONLY|os.O_CREAT|os.O_APPEND|getattr(os,'O_NOFOLLOW',0),0o600)
        try:
            info=validate_open_control(descriptor,private=True)
            if os.name!='nt' and (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1 or info.st_mode&0o077):
                raise WorkflowError('LOCAL_LOG_UNSAFE')
            return os.fdopen(descriptor,'a',encoding='utf-8')
        except BaseException:
            os.close(descriptor);raise

    def handleError(self,record):
        # Never send logging exceptions, raw values or records to stderr.
        raise WorkflowError('LOCAL_LOG_WRITE_FAILED') from None


class LocalLog:
    def __init__(self,workspace):
        self.root=guard_workspace(workspace,canonical_alias=False)
        self.lock=threading.RLock();self.closed=False;self.failed=False
        self._validate()
        directory=guard_control(self.root,'logs','dir')
        try:private_directory(directory)
        except FileExistsError:pass
        self._validate()
        self.logger=logging.Logger('storymotion.local',level=logging.WARNING)
        self.logger.propagate=False
        self.handler=OwnedRotatingHandler(directory/'local.log',maxBytes=65536,backupCount=2,encoding='utf-8',delay=True)
        formatter=logging.Formatter('%(asctime)s %(message)s',datefmt='%Y-%m-%dT%H:%M:%SZ');formatter.converter=time.gmtime
        self.handler.setFormatter(formatter);self.logger.addHandler(self.handler)

    def _validate(self):
        directory=guard_control(self.root,'logs','dir')
        if os.name=='nt':
            from .windows_native import inspect
            inspect(directory,'dir',private=True)
            for name in ('local.log','local.log.1','local.log.2'):inspect(directory/name,private=True)
            return
        if directory.exists() and directory.stat().st_mode&0o077:raise WorkflowError('LOCAL_LOG_UNSAFE')
        for name in ('local.log','local.log.1','local.log.2'):
            path=guard_control(self.root,'logs/'+name)
            if path.exists() and path.stat().st_mode&0o077:raise WorkflowError('LOCAL_LOG_UNSAFE')

    def warning(self,code,error):
        with self.lock:
            if self.closed or code not in CODES:return False
            try:
                self._validate()
                kind=type(error).__name__
                self.logger.warning('%s %s',code,kind if kind in KINDS else 'Exception')
                return True
            except (OSError,WorkflowError):
                self.failed=True
                return False  # no stderr fallback or unbounded buffer

    def close(self):
        with self.lock:
            if not self.closed:
                self.closed=True;self.logger.removeHandler(self.handler);self.handler.close()
