"""Kernel-backed workspace locks; persistent lock files are never removed."""
import os
if os.name=='nt':
    from .windows_native import flock, LOCK_EX, LOCK_NB, LOCK_UN, LOCK_SH
else:
    from fcntl import flock, LOCK_EX, LOCK_NB, LOCK_UN, LOCK_SH
