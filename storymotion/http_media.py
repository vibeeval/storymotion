"""Single-range response over already verified immutable MP4 bytes, no file IO."""
import re

def media_slice(raw,header):
    """Return (status, start, stop-exclusive, content-range); invalid ->416."""
    size=len(raw)
    if header is None:return 200,0,size,None
    if not isinstance(header,str) or len(header)>128:return 416,0,0,'bytes */'+str(size)
    match=re.fullmatch(r'bytes=([0-9]{0,20})-([0-9]{0,20})',header,re.IGNORECASE)
    if not match or not size:return 416,0,0,'bytes */'+str(size)
    left,right=match.groups()
    if not left:
        if not right or int(right)==0:return 416,0,0,'bytes */'+str(size)
        start=max(0,size-int(right));stop=size
    else:
        start=int(left);end=int(right) if right else size-1
        if start>=size or end<start:return 416,0,0,'bytes */'+str(size)
        stop=min(size,end+1)
    return 206,start,stop,f'bytes {start}-{stop-1}/{size}'
