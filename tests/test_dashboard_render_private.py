"""Fresh normal render dispatch under child-process umasks; no native worker."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from storymotion.dashboard import Dashboard
from storymotion.engine import Engine
from storymotion.local_state import private_directory
from storymotion.security import WorkflowError


def close(d):
    d.renders.close();d.clear_keys();d.llm.close();d.reviews.close();d.close_local_log()


def enqueue(d):
    v=d.template('neutral','account-video')['template']['video']
    return d.enqueue(dict(account='neutral',format='account-video',title=v['title'],brief=v['brief'],content=v['script'],caption=v['caption'],provider='local',model='manual',task='text',template_revision=0))['id']


def count(path,table):
    if not path.exists():return 0
    db=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)
    try:return db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
    finally:db.close()


def image(root):
    return {p.relative_to(root).as_posix():{'mode':p.stat().st_mode&0o777,'mtime_ns':p.stat().st_mtime_ns,
            'sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None}
            for p in sorted(root.rglob('*'))}


def start(d,job,engine):
    with patch('storymotion.dashboard_render.require_engine',return_value=None) as ready,patch.object(d.renders,'work') as worker,patch.object(Engine,'run',side_effect=AssertionError('Native execution forbidden')) as native:
        value=d.render_action(job,'render',{'engine':engine})
        for _,thread in list(d.renders.active.values()):thread.join(10);assert not thread.is_alive()
        ready.assert_called_once_with(engine);worker.assert_called_once();native.assert_not_called()
        return value


def probe(mask,root):
    """Only this isolated child owns the mask and every constructed path."""
    mask=int(mask,8);os.umask(mask);root=Path(root).resolve();results=[]
    for engine in ('hyperframes','remotion'):
        d=Dashboard(root/('fresh-'+engine))
        try:
            job=enqueue(d);assert not d.output(job).exists();assert d.job(job)['status']=='queued'
            result=start(d,job,engine);assert result['status']=='started' and result['provider_calls']==0
            out=d.output(job);source=out/('render-input-'+engine+'.json')
            modes=[(d.workspace/'dashboard').stat().st_mode&0o777,out.stat().st_mode&0o777,source.stat().st_mode&0o777]
            assert modes==[0o700,0o700,0o600],modes
            assert len(d.jobs())==1 and d.job(job)['status']=='queued'
            assert d.renders.row(job,engine)['engine_job']==result['engine_job']
            assert count(d.workspace/'renders/jobs.sqlite3','jobs')==1
            with Engine(d.workspace/'renders') as e:
                # create persists intake only; stage rows are created by run.
                assert e.store.status(result['engine_job'])['stages']==[]
            assert not list(d.workspace.rglob('*.mp4'))
            results.append({'case':'fresh','engine':engine,'modes':modes,'jobs_listed':1,'engine_rows':1,'native_stages_executed':0})
        finally:close(d)
        d=Dashboard(root/('retry-'+engine))
        try:
            job=enqueue(d)
            with patch('storymotion.dashboard_render.require_engine',return_value=None),patch.object(Engine,'create',side_effect=WorkflowError('Synthetic planning failure')),patch.object(d.renders,'work') as worker:
                try:d.render_action(job,'render',{'engine':engine})
                except WorkflowError as error:assert str(error)=='Synthetic planning failure'
                else:raise AssertionError('Injected planning failure was not observed')
                worker.assert_not_called()
            assert len(d.jobs())==1 and d.job(job)['status']=='queued'
            assert d.renders.row(job,engine) is None and not d.renders.active
            assert count(d.workspace/'renders/jobs.sqlite3','jobs')==0
            source=d.output(job)/('render-input-'+engine+'.json');assert source.is_file() and source.stat().st_mode&0o777==0o600
            before=source.read_bytes();result=start(d,job,engine);assert result['status']=='started'
            assert source.read_bytes()==before and len(d.jobs())==1
            results.append({'case':'failed_plan_then_retry','engine':engine,'input_retained_private':True,'no_orphan_engine_job_before_retry':True})
        finally:close(d)
        for bad in ('ancestor','job'):
            d=Dashboard(root/('bad-'+bad+'-'+engine))
            try:
                job=enqueue(d);folder=d.workspace/'dashboard' if bad=='ancestor' else d.output(job)
                private_directory(folder);folder.chmod(0o755)  # Test-owned adversarial fixture only.
                before=image(d.workspace)
                with patch('storymotion.dashboard_render.require_engine',return_value=None),patch.object(d.renders,'work') as worker:
                    try:d.render_action(job,'render',{'engine':engine})
                    except WorkflowError as error:assert 'LOCAL_STATE_PERMISSIONS' in str(error)
                    else:raise AssertionError('Existing bad mode was accepted')
                    worker.assert_not_called()
                assert image(d.workspace)==before
                assert not (d.workspace/'renders').exists()
                assert count(d.workspace/'jobs.sqlite3','dashboard_renders')==0
                results.append({'case':'existing_bad_'+bad,'engine':engine,'unchanged':True,'engine_rows':0})
            finally:close(d)
    ambient=root/'ambient-mask-check';ambient.mkdir();(ambient/'file').write_bytes(b'Original synthetic sentinel')
    assert ambient.stat().st_mode&0o777==0o777&~mask
    assert (ambient/'file').stat().st_mode&0o777==0o666&~mask
    return {'umask':oct(mask),'results':results,'ambient_umask_preserved':True,'native_or_provider_calls':0}


def input_image(root):
    """Observe owned fixtures without following links or opening special files."""
    result={}
    for path in [root,*sorted(root.rglob('*'))]:
        info=path.lstat()
        entry={'mode':info.st_mode,'inode':info.st_ino,'device':info.st_dev,
               'mtime_ns':info.st_mtime_ns,'links':info.st_nlink,'size':info.st_size}
        if stat.S_ISLNK(info.st_mode):entry['target']=os.readlink(path)
        elif stat.S_ISREG(info.st_mode):entry['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        result[path.relative_to(root).as_posix()]=entry
    return result


def input_probe(mask,root,cases):
    """Actual queued dispatch, real Engine intake, test-owned paths only."""
    mask=int(mask,8);os.umask(mask);root=Path(root).resolve();results=[]
    for engine in ('hyperframes','remotion'):
        for case in cases:
            d=Dashboard(root/(case+'-'+engine))
            try:
                job=enqueue(d);path=d.output(job)/('render-input-'+engine+'.json')
                private_directory(path.parent)
                target=d.workspace/'owned-target'
                if case in ('private','mode644','mode640','hardlink'):
                    path.write_bytes(b'Synthetic pre-existing derived input sentinel')
                    path.chmod({'mode644':0o644,'mode640':0o640}.get(case,0o600))
                    if case=='hardlink':os.link(path,target)
                elif case in ('symlink','dangling'):
                    if case=='symlink':target.write_bytes(b'Synthetic untouched link target');target.chmod(0o600)
                    path.symlink_to(target)
                elif case=='directory':path.mkdir(mode=0o700)
                elif case=='fifo':os.mkfifo(path,0o600)
                else:raise AssertionError('Unknown test fixture')
                before=input_image(d.workspace);original_create=Engine.create
                with patch('storymotion.dashboard_render.require_engine',return_value=None),patch.object(d.renders,'work') as worker,patch.object(Engine,'create',autospec=True,side_effect=original_create) as intake,patch.object(Engine,'run',side_effect=AssertionError('Native execution forbidden')) as native:
                    error=None;result=None
                    try:result=d.render_action(job,'render',{'engine':engine})
                    except WorkflowError as exc:error=str(exc)
                    for _,thread in list(d.renders.active.values()):thread.join(10);assert not thread.is_alive()
                    after=input_image(d.workspace)
                    native.assert_not_called()
                    row={'case':case,'engine':engine,'error':error,'result':result,
                         'unchanged':after==before,'worker_calls':worker.call_count,'intake_calls':intake.call_count}
                if case=='private':
                    row['valid']=(error is None and result['status']=='started' and
                        row['worker_calls']==1 and row['intake_calls']==1 and
                        path.stat().st_mode&0o777==0o600 and
                        json.loads(path.read_text())==d.renders.video_input(d.job(job)) and
                        count(d.workspace/'renders/jobs.sqlite3','jobs')==1 and
                        d.renders.row(job,engine)['engine_job']==result['engine_job'])
                else:
                    code='LOCAL_STATE_PERMISSIONS' if case in ('mode644','mode640') else 'LOCAL_STATE_UNSAFE'
                    row['valid']=(error is not None and code in error and result is None and
                        row['unchanged'] and row['worker_calls']==0 and row['intake_calls']==0 and
                        not (d.workspace/'renders').exists() and
                        count(d.workspace/'jobs.sqlite3','dashboard_renders')==0 and not d.renders.active)
                row['jobs_still_listed']=len(d.jobs())==1 and d.job(job)['status']=='queued'
                row['valid']=row['valid'] and row['jobs_still_listed']
                results.append(row)
            finally:close(d)
    ambient=root/'ambient';ambient.mkdir();(ambient/'file').write_bytes(b'Synthetic ambient mode check')
    return {'results':results,'ambient_umask_preserved':ambient.stat().st_mode&0o777==0o777&~mask and
            (ambient/'file').stat().st_mode&0o777==0o666&~mask,'native_or_provider_calls':0}


class DashboardRenderPrivateTests(unittest.TestCase):
    def test_fresh_both_engines_and_failures_preserve_private_contract_under_022(self):self.run_probe('022')
    def test_fresh_both_engines_and_failures_preserve_private_contract_under_077(self):self.run_probe('077')

    def run_probe(self,mask):
        with tempfile.TemporaryDirectory(prefix='render-private-') as temporary:
            result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--probe',mask,temporary],cwd=ROOT,text=True,capture_output=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stderr);value=json.loads(result.stdout)
            self.assertEqual(len(value['results']),8);self.assertTrue(value['ambient_umask_preserved'])
            self.assertEqual(value['native_or_provider_calls'],0)


class DashboardRenderInputPrivateTests(unittest.TestCase):
    def run_cases(self,mask,cases):
        with tempfile.TemporaryDirectory(prefix='render-input-private-') as temporary:
            result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--input-probe',mask,temporary,*cases],cwd=ROOT,text=True,capture_output=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stderr);value=json.loads(result.stdout)
            self.assertEqual(len(value['results']),2*len(cases));self.assertTrue(value['ambient_umask_preserved'])
            self.assertEqual(value['native_or_provider_calls'],0)
            for row in value['results']:
                with self.subTest(mask=mask,engine=row['engine'],case=row['case']):self.assertTrue(row['valid'],row)

    def test_existing_private_input_under_022(self):self.run_cases('022',['private'])
    def test_existing_private_input_under_077(self):self.run_cases('077',['private'])
    def test_existing_bad_file_modes_under_022(self):self.run_cases('022',['mode644','mode640'])
    def test_existing_bad_file_modes_under_077(self):self.run_cases('077',['mode644','mode640'])
    def test_existing_link_and_wrong_type_under_022(self):self.run_cases('022',['symlink','dangling','hardlink','directory','fifo'])
    def test_existing_link_and_wrong_type_under_077(self):self.run_cases('077',['symlink','dangling','hardlink','directory','fifo'])


if __name__=='__main__':
    if len(sys.argv)>4 and sys.argv[1]=='--input-probe':print(json.dumps(input_probe(sys.argv[2],sys.argv[3],sys.argv[4:])))
    elif len(sys.argv)==4 and sys.argv[1]=='--probe':print(json.dumps(probe(sys.argv[2],sys.argv[3])))
    else:unittest.main()
