"""Windows x64/NTFS primitives. No permission repair or shell command execution.

Ancestor handles deny delete sharing while guarded operations run. Reparse
points, network volumes, alternate streams and ambiguous DOS names are refused.
Windows API access is lazy so the POSIX implementation remains independent.
"""
import contextlib
import ctypes as C
from ctypes import wintypes as W
import errno
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import subprocess
import sys
import uuid

from .security import WorkflowError


def fail(code='WINDOWS_PATH_UNSAFE'):
    raise WorkflowError(code)


def component(name):
    if (not isinstance(name,str) or not name or name in {'.','..'} or name.endswith((' ','.'))
            or re.search(r'[<>:"/\\|?*\x00-\x1f]',name) or re.search(r'~[0-9]',name)
            or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?',name)):
        fail()
    return name


def local_path(path):
    raw=str(path)
    if any(part in {'.','..'} for part in raw.replace('\\','/').split('/')[1:]):fail()
    value=PureWindowsPath(path)
    if not re.fullmatch('[A-Za-z]:',value.drive) or not value.root:fail('WINDOWS_LOCAL_NTFS_REQUIRED')
    for part in value.parts[1:]:component(part)
    return str(value)


class SA(C.Structure):
    _fields_=[('length',W.DWORD),('descriptor',W.LPVOID),('inherit',W.BOOL)]


class INFO(C.Structure):
    _fields_=[('attributes',W.DWORD),('created',W.FILETIME),('accessed',W.FILETIME),('written',W.FILETIME),
              ('volume',W.DWORD),('size_high',W.DWORD),('size_low',W.DWORD),('links',W.DWORD),
              ('index_high',W.DWORD),('index_low',W.DWORD)]


class OVERLAPPED(C.Structure):
    _fields_=[('internal',C.c_size_t),('internal_high',C.c_size_t),('offset',W.DWORD),
              ('offset_high',W.DWORD),('event',W.HANDLE)]


class ACL_SIZE(C.Structure):
    _fields_=[('count',W.DWORD),('used',W.DWORD),('free',W.DWORD)]


class ACE_HEADER(C.Structure):
    _fields_=[('kind',W.BYTE),('flags',W.BYTE),('size',W.WORD)]


class IO_COUNTERS(C.Structure):
    _fields_=[(name,C.c_ulonglong) for name in ('reads','writes','other','read_bytes','write_bytes','other_bytes')]


class JOB_BASIC(C.Structure):
    _fields_=[('process_time',C.c_longlong),('job_time',C.c_longlong),('flags',W.DWORD),
              ('min_working',C.c_size_t),('max_working',C.c_size_t),('active_limit',W.DWORD),
              ('affinity',C.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]


class JOB_LIMIT(C.Structure):
    _fields_=[('basic',JOB_BASIC),('io',IO_COUNTERS),('process_memory',C.c_size_t),
              ('job_memory',C.c_size_t),('peak_process',C.c_size_t),('peak_job',C.c_size_t)]


_API=None

def api():
    global _API
    if _API is not None:return _API
    if sys.platform!='win32' or C.sizeof(C.c_void_p)!=8:fail('WINDOWS_X64_REQUIRED')
    k=C.WinDLL('kernel32',use_last_error=True);a=C.WinDLL('advapi32',use_last_error=True)
    signatures={
        'CreateFileW':(W.HANDLE,[W.LPCWSTR,W.DWORD,W.DWORD,C.POINTER(SA),W.DWORD,W.DWORD,W.HANDLE]),
        'CloseHandle':(W.BOOL,[W.HANDLE]),'GetCurrentProcess':(W.HANDLE,[]),
        'IsWow64Process2':(W.BOOL,[W.HANDLE,C.POINTER(W.WORD),C.POINTER(W.WORD)]),
        'GetFileInformationByHandle':(W.BOOL,[W.HANDLE,C.POINTER(INFO)]),
        'GetVolumeInformationW':(W.BOOL,[W.LPCWSTR,W.LPWSTR,W.DWORD,W.LPVOID,W.LPVOID,W.LPVOID,W.LPWSTR,W.DWORD]),
        'GetDriveTypeW':(W.UINT,[W.LPCWSTR]),
        'CreateDirectoryW':(W.BOOL,[W.LPCWSTR,C.POINTER(SA)]),
        'LockFileEx':(W.BOOL,[W.HANDLE,W.DWORD,W.DWORD,W.DWORD,W.DWORD,C.POINTER(OVERLAPPED)]),
        'UnlockFileEx':(W.BOOL,[W.HANDLE,W.DWORD,W.DWORD,W.DWORD,C.POINTER(OVERLAPPED)]),
        'LocalFree':(W.HANDLE,[W.HANDLE]),
        'CreateJobObjectW':(W.HANDLE,[W.LPVOID,W.LPCWSTR]),
        'SetInformationJobObject':(W.BOOL,[W.HANDLE,C.c_int,W.LPVOID,W.DWORD]),
        'AssignProcessToJobObject':(W.BOOL,[W.HANDLE,W.HANDLE]),
        'TerminateJobObject':(W.BOOL,[W.HANDLE,W.UINT]),
    }
    for name,(result,args) in signatures.items():
        f=getattr(k,name);f.restype=result;f.argtypes=args
    signatures={
        'OpenProcessToken':(W.BOOL,[W.HANDLE,W.DWORD,C.POINTER(W.HANDLE)]),
        'GetTokenInformation':(W.BOOL,[W.HANDLE,C.c_int,W.LPVOID,W.DWORD,C.POINTER(W.DWORD)]),
        'ConvertSidToStringSidW':(W.BOOL,[W.LPVOID,C.POINTER(W.LPWSTR)]),
        'ConvertStringSecurityDescriptorToSecurityDescriptorW':(W.BOOL,[W.LPCWSTR,W.DWORD,C.POINTER(W.LPVOID),W.LPVOID]),
        'GetSecurityInfo':(W.DWORD,[W.HANDLE,C.c_int,W.DWORD,C.POINTER(W.LPVOID),W.LPVOID,C.POINTER(W.LPVOID),W.LPVOID,C.POINTER(W.LPVOID)]),
        'GetAclInformation':(W.BOOL,[W.LPVOID,W.LPVOID,W.DWORD,C.c_int]),
        'GetAce':(W.BOOL,[W.LPVOID,W.DWORD,C.POINTER(W.LPVOID)]),
    }
    for name,(result,args) in signatures.items():
        f=getattr(a,name);f.restype=result;f.argtypes=args
    process_machine=W.WORD();native_machine=W.WORD()
    checked(k.IsWow64Process2(k.GetCurrentProcess(),C.byref(process_machine),C.byref(native_machine)))
    if native_machine.value!=0x8664 or process_machine.value!=0:fail('WINDOWS_NATIVE_X64_REQUIRED')
    _API=(k,a)
    return _API


def checked(value):
    if not value:raise C.WinError(C.get_last_error())
    return value


def sid_text(sid):
    k,a=api();value=W.LPWSTR()
    checked(a.ConvertSidToStringSidW(sid,C.byref(value)))
    try:return value.value
    finally:k.LocalFree(C.cast(value,W.HANDLE))


def current_sid():
    k,a=api();token=W.HANDLE();size=W.DWORD()
    checked(a.OpenProcessToken(k.GetCurrentProcess(),8,C.byref(token)))
    try:
        a.GetTokenInformation(token,1,None,0,C.byref(size))
        if not 0<size.value<=65536:fail('WINDOWS_IDENTITY_UNAVAILABLE')
        data=C.create_string_buffer(size.value)
        checked(a.GetTokenInformation(token,1,data,size,C.byref(size)))
        return sid_text(C.cast(data,C.POINTER(W.LPVOID))[0])
    finally:k.CloseHandle(token)


@contextlib.contextmanager
def security_attributes():
    k,a=api();descriptor=W.LPVOID()
    # Protected inheritable DACL for new paths only. Existing ACLs never change.
    sddl='D:P(A;OICI;FA;;;'+current_sid()+')(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)'
    checked(a.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,C.byref(descriptor),None))
    attributes=SA(C.sizeof(SA),descriptor,False)
    try:yield attributes
    finally:k.LocalFree(descriptor)


def acl(handle,private=False):
    k,a=api();owner=W.LPVOID();dacl=W.LPVOID();descriptor=W.LPVOID()
    error=a.GetSecurityInfo(handle,1,5,C.byref(owner),None,C.byref(dacl),None,C.byref(descriptor))
    if error:raise C.WinError(error)
    try:
        identity=current_sid()
        if not owner or sid_text(owner)!=identity:fail('WINDOWS_OWNER_REQUIRED')
        if not private:return
        if not dacl:fail('WINDOWS_PRIVATE_ACL_REQUIRED')
        info=ACL_SIZE();checked(a.GetAclInformation(dacl,C.byref(info),C.sizeof(info),2))
        if info.count>128:fail('WINDOWS_PRIVATE_ACL_REQUIRED')
        allowed={identity,'S-1-5-18','S-1-5-32-544'}
        owner_access=False
        for index in range(info.count):
            ace=W.LPVOID();checked(a.GetAce(dacl,index,C.byref(ace)))
            header=C.cast(ace,C.POINTER(ACE_HEADER)).contents
            if header.flags&8:continue # inherit-only ACE does not grant this object access
            if header.kind==1:continue # deny ACE cannot expand access
            if header.kind!=0 or header.size<12:fail('WINDOWS_PRIVATE_ACL_REQUIRED')
            mask=C.cast(ace.value+4,C.POINTER(W.DWORD)).contents.value
            subject=sid_text(ace.value+8)
            if mask and subject not in allowed:fail('WINDOWS_PRIVATE_ACL_REQUIRED')
            if subject==identity and mask:owner_access=True
        if not owner_access:fail('WINDOWS_PRIVATE_ACL_REQUIRED')
    finally:k.LocalFree(descriptor)


def handle_info(handle,directory=False,owned=True,private=False):
    k,_=api();info=INFO();checked(k.GetFileInformationByHandle(handle,C.byref(info)))
    if info.attributes&0x400 or bool(info.attributes&0x10)!=directory or (not directory and info.links!=1):fail()
    if owned:acl(handle,private)
    return info


def ntfs(path):
    k,_=api();value=local_path(path);drive=PureWindowsPath(value).anchor;name=C.create_unicode_buffer(32)
    if k.GetDriveTypeW(drive)!=3:fail('WINDOWS_LOCAL_NTFS_REQUIRED')
    checked(k.GetVolumeInformationW(drive,None,0,None,None,None,name,len(name)))
    if name.value.upper()!='NTFS':fail('WINDOWS_LOCAL_NTFS_REQUIRED')


def open_handle(path,directory=False,access=0x20000,creation=3,attributes=None,share=3):
    k,_=api();value=local_path(path)
    flags=0x00200000 | (0x02000000 if directory else 0) # OPEN_REPARSE_POINT, BACKUP_SEMANTICS
    handle=k.CreateFileW(value,access,share,C.byref(attributes) if attributes else None,creation,flags,None)
    if handle==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
    return handle


@contextlib.contextmanager
def ancestors(path):
    """Hold non-reparse parents without delete sharing until operation completes."""
    value=Path(local_path(path));ntfs(value);k,_=api();handles=[]
    try:
        for parent in reversed(value.parents):
            h=open_handle(parent,directory=True);handles.append(h)
            handle_info(h,directory=True,owned=False)
        yield value
    finally:
        for h in reversed(handles):k.CloseHandle(h)


def inspect(path,kind='file',private=False,missing=True):
    k,_=api()
    try:
        with ancestors(path) as target:
            h=open_handle(target,directory=kind=='dir')
            try:
                handle_info(h,directory=kind=='dir',private=private)
                return Path(path).lstat()
            finally:k.CloseHandle(h)
    except FileNotFoundError:
        if missing:return None
        raise


def mkdir(path,exclusive=False):
    path=Path(path)
    if not path.parent.exists():mkdir(path.parent)
    k,_=api()
    with ancestors(path),security_attributes() as sa:
        if not k.CreateDirectoryW(local_path(path),C.byref(sa)):
            error=C.get_last_error()
            if error!=183 or exclusive:raise C.WinError(error)
        inspect(path,'dir',private=True,missing=False)
    return path


def open_fd(path,flags,mode=0o600):
    import msvcrt
    k,_=api();access=0x20000 | (0xC0000000 if flags&os.O_RDWR else 0x40000000 if flags&os.O_WRONLY else 0x80000000)
    creation=1 if flags&os.O_EXCL else 4 if flags&os.O_CREAT else 3
    with ancestors(path),security_attributes() as sa:
        h=open_handle(path,access=access,creation=creation,attributes=sa)
        try:
            handle_info(h,private=True)
            fd=msvcrt.open_osfhandle(h,flags | os.O_BINARY)
        except BaseException:k.CloseHandle(h);raise
    os.set_inheritable(fd,False)
    return fd


def validate_fd(fd,private=False):
    import msvcrt
    handle_info(msvcrt.get_osfhandle(fd),private=private)
    return os.fstat(fd)


@contextlib.contextmanager
def regular(root,relative,maximum,private=False):
    import msvcrt
    target=Path(root)/relative;k,_=api()
    with ancestors(target):
        h=open_handle(target,access=0x80020000,share=1)
        try:handle_info(h,private=private);fd=msvcrt.open_osfhandle(h,os.O_RDONLY|os.O_BINARY)
        except BaseException:k.CloseHandle(h);raise
        with os.fdopen(fd,'rb') as stream:
            before=os.fstat(stream.fileno())
            if not 0<=before.st_size<=maximum:fail('WINDOWS_FILE_BOUND_EXCEEDED')
            yield stream
            after=os.fstat(stream.fileno())
            if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):fail('WINDOWS_FILE_CHANGED')


def read(root,relative,maximum,private=False):
    with regular(root,relative,maximum,private) as stream:
        raw=stream.read(maximum+1)
        if len(raw)>maximum:fail('WINDOWS_FILE_BOUND_EXCEEDED')
        return raw


def write(path,raw,exclusive=False):
    path=Path(path);mkdir(path.parent)
    with ancestors(path):
        inspect(path,private=True)
        target=path if exclusive else path.parent/('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
        fd=open_fd(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL)
        try:
            with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            if not exclusive:
                inspect(path,private=True)
                os.replace(target,path)
        finally:
            if not exclusive:target.unlink(missing_ok=True)


LOCK_SH=1;LOCK_EX=2;LOCK_NB=4;LOCK_UN=8

def flock(fd,operation):
    import msvcrt
    k,_=api();h=msvcrt.get_osfhandle(fd.fileno() if hasattr(fd,'fileno') else fd);overlap=OVERLAPPED()
    result=k.UnlockFileEx(h,0,1,0,C.byref(overlap)) if operation==LOCK_UN else k.LockFileEx(h,(2 if operation&LOCK_EX else 0)|(1 if operation&LOCK_NB else 0),0,1,0,C.byref(overlap))
    if not result:
        error=C.get_last_error()
        if error in (33,158):raise BlockingIOError(errno.EAGAIN,'Workspace lock is held')
        raise C.WinError(error)


def scan_project(root):
    root=Path(root);inspect(root,'dir',missing=False);budget=[0]
    def visit(folder,relative):
        if len(relative)>128:fail('LOCAL_STATE_SCAN_LIMIT')
        with ancestors(folder):
            k,_=api();h=open_handle(folder,directory=True)
            try:
                handle_info(h,directory=True)
                signature=lambda v:(v.st_dev,v.st_ino,v.st_size,v.st_mtime_ns,v.st_ctime_ns,v.st_nlink,v.st_mode)
                before=signature(folder.stat());rows=[]
                for entry in folder.iterdir():
                    budget[0]+=1
                    if budget[0]>200000:fail('LOCAL_STATE_SCAN_LIMIT')
                    info=entry.lstat();kind='dir' if stat.S_ISDIR(info.st_mode) else 'file'
                    inspect(entry,kind,missing=False);rows.append((entry,kind,signature(info)))
                    parts=relative+(entry.name,)
                    if kind=='dir' and parts not in {('.runtime','chrome'),('.runtime','probe','stages')}:
                        visit(entry,parts)
                for entry,kind,original in rows:
                    if signature(inspect(entry,kind,missing=False))!=original:fail('WINDOWS_PATH_CHANGED')
                if signature(folder.stat())!=before:fail('WINDOWS_PATH_CHANGED')
            finally:k.CloseHandle(h)
    for name in ('node_modules','optional/remotion/node_modules','work','.runtime'):
        inspect(root/name,'dir')
    for name in ('work','.runtime'):
        if (root/name).exists():visit(root/name,(name,))
    return root


def extract(rows,destination,scope):
    destination=Path(destination)
    with ancestors(destination):
        mkdir(destination,exclusive=True)
        for parts,directory,raw,_ in rows:
            for name in parts:component(name)
            target=destination.joinpath(*parts)
            if directory:mkdir(target)
            else:write(target,raw,exclusive=True)
    return destination


def npm_command(argv):
    import shutil
    if str(argv[0]).lower() not in {'npm','npm.cmd'}:return [str(x) for x in argv]
    node=shutil.which('node.exe');npm=Path(node).parent/'node_modules/npm/bin/npm-cli.js' if node else None
    if not npm or not npm.is_file():fail('WINDOWS_NODE_NPM_REQUIRED')
    return [node,str(npm),*[str(x) for x in argv[1:]]]


def launch(argv,**kwargs):
    """Payload waits on stdin until its helper is assigned to our kill-on-close job."""
    k,_=api();job=checked(k.CreateJobObjectW(None,None));limits=JOB_LIMIT();limits.basic.flags=0x2000
    process=None
    try:
        checked(k.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)))
        helper=Path(__file__).resolve().parents[1]/'tools/windows_child.py'
        process=subprocess.Popen([sys.executable,'-X','utf8','-B',str(helper),*npm_command(argv)],stdin=subprocess.PIPE,
                                 creationflags=subprocess.CREATE_NO_WINDOW,**kwargs)
        checked(k.AssignProcessToJobObject(job,int(process._handle)))
        process.stdin.write(b'G');process.stdin.flush();process.stdin.close();process.stdin=None
        process._storymotion_job=job
        return process
    except BaseException:
        if process is not None:process.kill();process.communicate(timeout=5)
        k.CloseHandle(job);raise


def close_job(process,terminate=False):
    k,_=api();job=getattr(process,'_storymotion_job',None)
    if job is None:return
    process._storymotion_job=None
    try:
        if terminate:checked(k.TerminateJobObject(job,1))
    finally:k.CloseHandle(job)
