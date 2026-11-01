"""Synthetic final receipt fixture; NOT rendered, decoded or captured video."""
import json
from storymotion.engine import Engine
from storymotion.security import digest,file_hash,write_json
from audio_fixture import source_job,imported


def seed_final(d,account,engine):
    parent=source_job(d,account);child=imported(d,parent)['child_job'];d.prepare(child)
    row=d.job(child);video=d.renders.video_input(row);path=d.output(child)/('render-input-'+engine+'.json');write_json(path,video)
    e=Engine(d.workspace/'renders')
    try:
        ident=e.create(path,render_engine=engine)['job'];e.run(ident,'prepare');out=e.directory(ident);payload=e.payload(ident)
        for name in ['render-1080.mp4','render-mobile.mp4','cover.png','cover-360.png']:
            (out/name).write_bytes(('NOT_MEDIA: synthetic audio final binding '+name).encode())
        write_json(out/'check.json',{'ok':True,'synthetic_test_sentinel':True})
        write_json(out/'browser-evidence.json',{'synthetic_test_sentinel':True,'actual_browser_used':False})
        write_json(out/'render-engine.json',{'engine':engine,'render_sha256':file_hash(out/'render-1080.mp4'),
            'execution_fingerprint':payload['execution']['fingerprint'],'audio_timing_sha256':digest(video['audio_timing']),
            'audio_sha256':payload['audio_sha256'],'synthetic_test_sentinel':True})
        write_json(out/'qa.json',{'technical':'pass','synthetic_test_sentinel':True,'actual_decode':False,
            'media':{n:{'sha256':file_hash(out/n),'full_decode':'pass','synthetic_test_sentinel':True} for n in ['render-1080.mp4','render-mobile.mp4']},
            'audio_source_sha256':payload['audio_sha256'],'audio_timing_sha256':digest(video['audio_timing']),
            'human_review':{'audio_listening':'pending','final_watch':'pending'}})
        e.store.set_stage(ident,'render','complete',{n:file_hash(out/n) for n in ['render-1080.mp4','render-engine.json']})
        e.store.set_stage(ident,'mobile','complete',{'render-mobile.mp4':file_hash(out/'render-mobile.mp4')})
        e.store.set_stage(ident,'qa','complete',{'qa.json':file_hash(out/'qa.json')})
        # Pure hash/ZIP package code; no render/decode stage is invoked.
        files=e.perform('delivery',payload,out);e.store.set_stage(ident,'delivery','complete',{n:file_hash(out/n) for n in files})
        with d.connection() as db:db.execute('INSERT OR REPLACE INTO dashboard_renders VALUES(?,?,?,?,?,?)',(child,engine,ident,'complete',None,1))
        return parent,child,ident,out,payload
    finally:e.store.db.close()
