"""Scoped AI-assisted first run. Standard library only; no provider or credential access."""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))


def prerequisites():
    problems=[]
    from storymotion.platform_support import platform_status
    compatibility=platform_status();system=compatibility['platform'];machine=compatibility['architecture']
    if sys.version_info[:2]<(3,9):problems.append('PYTHON_REQUIRED: Python3.9 veya sonrası gerekir; bu araç Python kurmaz.')
    if not compatibility['supported']:problems.append(compatibility['error'])
    node=shutil.which('node');npm=shutil.which('npm');version=None
    if not node:problems.append('NODE_REQUIRED: nodejs.org üzerinden Node22.23.2–22.x gerekir; OS kurulumu otomatik yapılmaz.')
    else:
        try:
            value=subprocess.run([node,'--version'],capture_output=True,text=True,timeout=10,check=True,
                                 env={'PATH':os.environ.get('PATH','')}).stdout.strip()
            match=re.fullmatch(r'v(\d+)\.(\d+)\.(\d+)',value)
            if match and (22,23,2)<=tuple(map(int,match.groups()))<(23,0,0):version=value
            else:problems.append('NODE_VERSION: Kilitli paket Node22.23.2–22.x ister; global motor veya farklı sürümle devam edilmez.')
        except (OSError,subprocess.SubprocessError):problems.append('NODE_UNAVAILABLE: Node sürümü okunamadı; PATH ve kurulumu kontrol edin.')
    if not npm:problems.append('NPM_REQUIRED: Node ile gelen npm bulunamadı; bu araç global paket kurmaz.')
    return {'ok':not problems,'platform':system,'architecture':machine,'compatibility':compatibility,'node':version,'npm_present':bool(npm),'errors':problems,'network':False}


def scope_paths():
    # Only this package's dedicated mutable directories are touched. Do not
    # repair links, delete locks or search the rest of the customer's disk.
    for name in ['node_modules','.runtime','work','work/ai-smoke','work/first-studio']:
        if (ROOT/name).is_symlink():raise ValueError('LINKED_CONTROL_PATH: Ayrı normal yazılabilir proje klasörü kullanın; bağlantı izlenmedi.')
    from storymotion.local_state import guard_project_scope
    guard_project_scope(ROOT)


def preflight(engine='hyperframes'):
    from storymotion.install_policy import dependency_plan,owner_terms
    p=prerequisites();terms=owner_terms(ROOT)
    if p['ok']:scope_paths()
    if not p['ok']:return {'ok':False,'prerequisites':p,'runtime':None,'owner_terms':terms,
                          'customer_release_ready':terms.get('customer_release_ready',False),
            'source_install_ready':terms['ready'] is True,
                          'next':'Önkoşulları kullanıcıyla çözün; sudo veya güvenlik ayarı kullanmayın.'}
    from storymotion.runtime import doctor
    d=doctor(engine);plan=dependency_plan(engine,root=ROOT)
    return {'ok':d['ok'],'prerequisites':p,'runtime':d,'install_plan':plan,'owner_terms':terms,
            'customer_release_ready':terms.get('customer_release_ready',False),
            'source_install_ready':terms['ready'] is True,
            'next':None if d['ok'] and terms['ready'] and plan['dependency_graph_ready'] else 'Read install_plan and owner_terms blockers before requesting downloads.','provider_calls':0}


def require_ready(engine='hyperframes'):
    state=preflight(engine)
    if not state['ok']:raise ValueError('RUNTIME_NOT_READY: Önce python3 tools/first_run.py preflight çalıştırın; kurulumu otomatik başlatmadım.')
    return state


def install(allow_downloads=False,engine='hyperframes',accepted_eula_sha256=None):
    from storymotion.install_policy import dependency_plan,require_owner_terms
    state=preflight(engine)
    if not state['prerequisites']['ok']:return state
    if not state['ok'] and not allow_downloads:raise ValueError('INSTALL_PERMISSION_REQUIRED: Sabit resmi bağımlılıkları indirme ve kurulum betiklerini çalıştırma yetkisi gerekir; yetki varsa --allow-downloads kullanın.')
    consent=require_owner_terms(ROOT,accepted_eula_sha256)
    plan=dependency_plan(engine,root=ROOT)
    if not plan['dependency_graph_ready']:raise ValueError('DEPENDENCY_PLAN_BLOCKED: '+','.join(plan['blockers']))
    if state['ok']:return {'ok':True,'action':'reuse_ready_runtime','network':False,'provider_calls':0,'owner_terms':consent,'install_plan':plan}
    from storymotion.runtime import setup
    result=setup(if_needed=True,engine=engine)
    return {'ok':result['ok'],'action':result['setup'],'provider_calls':0,'owner_terms':consent,'install_plan':plan,
            'resume':'npm stage reused only with matching successful npm receipt and pinned package checks'}


def smoke(prepare_only=False,engine='hyperframes'):
    from storymotion.install_policy import selected_engines,REMOTION_NOTICE
    require_ready(engine)
    from storymotion.engine import Engine,STAGES
    from storymotion.security import file_hash
    runs=[]
    engines=selected_engines(engine)
    for engine in engines:
        e=Engine(ROOT/'work/ai-smoke')
        try:
            job=e.create(ROOT/'fixtures/turkish-font-smoke.json',render_engine=engine)['job'];out=e.directory(job)
            before={n:{'sha256':file_hash(out/n),'mtime_ns':(out/n).stat().st_mtime_ns} for n in ['render-1080.mp4','render-mobile.mp4'] if (out/n).is_file()}
            e.run(job,'prepare' if prepare_only else 'delivery')
            statuses={x['name']:x['status'] for x in e.store.status(job)['stages']}
            files={n:{'sha256':file_hash(out/n),'mtime_ns':(out/n).stat().st_mtime_ns} for n in ['render-1080.mp4','render-mobile.mp4'] if (out/n).is_file()}
            if not prepare_only:
                qa=json.loads((out/'qa.json').read_text())
                if qa['technical']!='pass' or not all(v['full_decode']=='pass' for v in qa['media'].values()):raise ValueError('SMOKE_DECODE_FAILED: QA kaydını inceleyin; otomatik tekrar yok.')
                if set(statuses)!=set(STAGES) or any(s!='complete' for s in statuses.values()):raise ValueError('SMOKE_INCOMPLETE: İş tamamlanmadı; aynı komut mevcut stage kayıtlarıyla devam eder.')
            runs.append({'engine':engine,'job':job,'output':'work/ai-smoke/'+job,'stage_status':statuses,'files':files,'before':before,'same_completed_outputs':bool(before) and before==files})
        finally:e.close()
    return {'ok':True,'scope':'prepare_only_no_MP4' if prepare_only else '3s silent synthetic MP4 and full decode for selected engines',
            'runs':runs,'license_notice':REMOTION_NOTICE if 'remotion' in engines else None,'provider_calls':0,'human_acceptance':'incomplete','publication_ready':False}


def start(port=4402,engine='hyperframes'):
    require_ready(engine)
    from storymotion.dashboard import make_server
    from storymotion import __version__
    server=make_server(ROOT/'work/first-studio',port=port,llm_mode='off',elevenlabs_mode='off')
    print(json.dumps({'version':__version__,'url':getattr(server,'dashboard_url','http://127.0.0.1:'+str(server.server_address[1])),'workspace':'work/first-studio','llm':'off','elevenlabs':'off','stop':'Bu terminalde Ctrl+C'},ensure_ascii=False),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Bu kaynak kopyası için güvenli anahtarsız ilk kullanım; mevcut önizlemeleri değiştirmez.')
    from storymotion.install_policy import ENGINES
    sub=parser.add_subparsers(dest='command',required=True);commands={}
    for name in ('preflight','install','smoke','start'):
        commands[name]=sub.add_parser(name);commands[name].add_argument('--engine',choices=ENGINES,default='hyperframes')
    commands['install'].add_argument('--allow-downloads',action='store_true')
    commands['install'].add_argument('--license-sha256','--accept-eula-sha256',dest='accept_eula_sha256',metavar='LICENSE_SHA256',help='Provide the exact SHA256 of the reviewed source LICENSE. This checks the license file identity, not acceptance of an additional contract. --accept-eula-sha256 is a compatibility alias; source-integrity and separate download gates remain enforced.')
    commands['smoke'].add_argument('--prepare-only',action='store_true');commands['start'].add_argument('--port',type=int,default=4402)
    args=parser.parse_args(argv)
    try:
        if args.command=='start':
            if not 1024<=args.port<=65535:raise ValueError('PORT_RANGE: 1024–65535 arasında boş port seçin; başka süreci durdurmayın.')
            start(args.port,args.engine);return 0
        value=preflight(args.engine) if args.command=='preflight' else install(args.allow_downloads,args.engine,args.accept_eula_sha256) if args.command=='install' else smoke(args.prepare_only,args.engine)
        print(json.dumps(value,ensure_ascii=False,indent=2));return 0 if value['ok'] else 2
    except KeyboardInterrupt:
        print(json.dumps({'ok':False,'error':'INTERRUPTED: Aynı komuttan önce tamamlanmış kurulum/iş durumunu kontrol edin.'},ensure_ascii=False));return 130
    except Exception as error:
        from storymotion.security import WorkflowError
        message=str(error) if isinstance(error,(ValueError,WorkflowError)) else 'LOCAL_OPERATION_FAILED: Yerel işlem tamamlanmadı. Mevcut sonucu inceleyin; sudo, izin genişletme veya kör tekrar yok.'
        print(json.dumps({'ok':False,'error':message},ensure_ascii=False));return 2


if __name__=='__main__':sys.exit(main())
