"""Internal job-contained launcher. Parent releases one byte after job assignment."""
import subprocess
import sys

if __name__=='__main__':
    if sys.platform!='win32' or len(sys.argv)<2 or sys.stdin.buffer.read(1)!=b'G':sys.exit(2)
    try:sys.exit(subprocess.call(sys.argv[1:],stdin=subprocess.DEVNULL,shell=False))
    except OSError:sys.exit(126)
