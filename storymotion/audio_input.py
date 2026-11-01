"""Bounded local audio containers; never let an import select a playlist demuxer.

Header checks are not codec/decoder security guarantees. Runtime still probes and
fully decodes with a fixed demuxer, file-only protocol and disabled MOV references.
"""
from pathlib import Path
from .security import WorkflowError


def _boxes(data,start,end):
    while start<end:
        if end-start<8:raise WorkflowError('Invalid bounded M4A box header')
        size=int.from_bytes(data[start:start+4],'big');kind=data[start+4:start+8];header=8
        if size==1:
            if end-start<16:raise WorkflowError('Invalid M4A extended box')
            size=int.from_bytes(data[start+8:start+16],'big');header=16
        if size==0:size=end-start
        if size<header or start+size>end:raise WorkflowError('M4A box escapes approved local file')
        yield kind,start+header,start+size
        start+=size


def _m4a(data):
    containers={b'moov',b'trak',b'mdia',b'minf',b'dinf',b'stbl',b'edts',b'mvex',b'moof',b'traf',b'udta'}
    count=[0];references=[0]
    def walk(start,end,depth=0):
        if depth>12:raise WorkflowError('M4A nesting exceeds bounded import')
        for kind,a,b in _boxes(data,start,end):
            count[0]+=1
            if count[0]>10000:raise WorkflowError('M4A box count exceeds bounded import')
            if kind in {b'rdrf',b'rmra',b'rmda'}:raise WorkflowError('Reference movie is not one approved audio file')
            if kind==b'dref':
                if b-a<8:raise WorkflowError('Invalid M4A data references')
                entries=list(_boxes(data,a+8,b))
                if int.from_bytes(data[a+4:a+8],'big')!=len(entries) or not entries:raise WorkflowError('Invalid M4A data reference count')
                for typ,x,y in entries:
                    # Only the standard self-contained URL entry, without a URL.
                    if typ!=b'url ' or y-x!=4 or data[x:x+4]!=b'\x00\x00\x00\x01':
                        raise WorkflowError('External M4A data reference rejected before media tools')
                    references[0]+=1
            elif kind in containers:walk(a,b,depth+1)
    top=list(_boxes(data,0,len(data)))
    if not {b'ftyp',b'moov',b'mdat'}<={k for k,_,_ in top}:raise WorkflowError('Self-contained M4A ftyp/moov/mdat required')
    ftyp=next(data[a:b] for k,a,b in top if k==b'ftyp')
    if len(ftyp)<8 or ftyp[:4] not in {b'M4A ',b'isom',b'iso2',b'mp41',b'mp42'}:raise WorkflowError('Unsupported bounded M4A brand')
    walk(0,len(data))
    if not references[0]:raise WorkflowError('Explicit self-contained M4A reference required')


def _wav(data):
    if len(data)<44 or data[:4]!=b'RIFF' or data[8:12]!=b'WAVE' or int.from_bytes(data[4:8],'little')+8!=len(data):
        raise WorkflowError('WAV import requires one complete local RIFF/WAVE container')
    pos=12;seen=set()
    while pos<len(data):
        if len(data)-pos<8:raise WorkflowError('Truncated WAV chunk')
        kind=data[pos:pos+4];size=int.from_bytes(data[pos+4:pos+8],'little');end=pos+8+size
        if end>len(data):raise WorkflowError('WAV chunk escapes approved file')
        if kind in {b'fmt ',b'data'}:
            if kind in seen or size==0:raise WorkflowError('Ambiguous or empty WAV audio chunk')
            seen.add(kind)
        if kind==b'fmt ' and (size<16 or int.from_bytes(data[pos+8:pos+10],'little') not in {1,3}):
            raise WorkflowError('Bounded WAV import supports PCM/IEEE float, not external/unknown formats')
        pos=end+(size%2)
    if pos!=len(data) or not {b'fmt ',b'data'}<=seen:raise WorkflowError('Complete WAV format/data chunks required')


def approved_audio_options(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or not 100<=p.stat().st_size<=12*1024*1024:raise WorkflowError('One bounded local audio file required')
    data=p.read_bytes();suffix=p.suffix.lower()
    if suffix=='.wav':_wav(data);demuxer='wav'
    elif suffix=='.m4a':_m4a(data);demuxer='mov'
    elif suffix=='.mp3':
        sync=len(data)>3 and data[0]==255 and data[1]&224==224 and data[1]&6!=0 and data[2]&240 not in {0,240} and data[2]&12!=12
        if not (data.startswith(b'ID3') or sync):raise WorkflowError('MP3/ID3 header required before restricted decode')
        demuxer='mp3'
    else:raise WorkflowError('Audio import supports bounded WAV/MP3/M4A containers only')
    options=['-protocol_whitelist','file','-f',demuxer]
    if demuxer=='mov':options+=['-enable_drefs','0','-use_absolute_path','0']
    return options
