"""Compatibility gates only; source tests do not establish native acceptance."""
import platform
import re
import sys

from .security import WorkflowError


def platform_status():
    system, machine = platform.system(), platform.machine()
    architecture = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'x64', 'AMD64': 'x64'}.get(machine)
    libc = platform.libc_ver() if system == 'Linux' else ('', '')
    windows = system=='Windows' and architecture=='x64' and sys.maxsize>2**32 and sys.getwindowsversion().major>=10 if sys.platform=='win32' else False
    supported = windows or architecture is not None and (system == 'Darwin' or (system == 'Linux' and libc[0] == 'glibc' and bool(re.fullmatch(r'\d+\.\d+(?:\.\d+)*', str(libc[1])))))
    return {'supported': supported, 'platform': system, 'architecture': architecture or machine,
            'libc': {'name': libc[0], 'version': libc[1]}, 'locking': 'Windows LockFileEx' if windows else 'POSIX fcntl',
            'native_acceptance': 'unverified',
            'error': None if supported else 'PLATFORM_UNSUPPORTED: macOS arm64/x64, Linux glibc arm64/x64 or Windows 10/11 x64 required; Windows requires a local NTFS workspace.'}


def require_platform():
    status = platform_status()
    if not status['supported']:
        raise WorkflowError(status['error'])
    return status
