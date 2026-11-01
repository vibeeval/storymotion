"""Production panel/gallery replay of genuine Handler state/request fixtures."""
import json
import os
from pathlib import Path
import subprocess
import unittest
from html.parser import HTMLParser

import test_taxonomy as backend
from storymotion.template_families import capabilities

ROOT=Path(__file__).resolve().parents[1]


class TaxonomyUiTests(unittest.TestCase):
    def test_real_handler_fixtures_replay_through_production_scripts(self):
        client=backend.TaxonomyHttpTests();client.setUp()
        try:
            a0=client.state();b0=client.state('studio-b');topic=a0['topics'][0]
            select={'account':'neutral','niche':topic['niche'],'topic':topic['id'],'expected_revision':a0['revision']}
            code,a1,_=client.request('select',select);self.assertEqual(code,200,a1)
            spec=json.loads((ROOT/'fixtures/template-families.json').read_text())['families']['kinetic-grid'][0]['spec']
            prepare={'account':'neutral','engine':'hyperframes','spec':spec,'claims':[],
                     'planning':{**a1['selection'],'revision':a1['revision']}}
            code,prepared,_=client.request('',prepare,path='/api/template-families/prepare');self.assertEqual(code,200,prepared)
            create_niche={'account':'neutral','kind':'niche','name':'UI Draft Niche','expected_revision':a1['revision']}
            code,niche,_=client.request('create',create_niche);self.assertEqual(code,200,niche)
            create_topic={'account':'neutral','kind':'topic','name':'UI Draft Topic','niche':niche['item']['id'],'expected_revision':niche['state']['revision']}
            code,new_topic,_=client.request('create',create_topic);self.assertEqual(code,200,new_topic)
            custom_select={'account':'neutral','niche':niche['item']['id'],'topic':new_topic['item']['id'],'expected_revision':new_topic['state']['revision']}
            code,a4,_=client.request('select',custom_select);self.assertEqual(code,200,a4)
            clear={'account':'neutral','niche':None,'topic':None,'expected_revision':a4['revision']}
            code,a5,_=client.request('select',clear);self.assertEqual(code,200,a5)
            wrong_parent_request={'account':'neutral','kind':'topic','name':create_topic['name'],'niche':a1['selection']['niche'],'expected_revision':a5['revision']}
            code,wrong_parent,_=client.request('create',wrong_parent_request);self.assertEqual(code,200,wrong_parent)
            duplicate_request={'account':'neutral','kind':'niche','name':'  ui draft niche  ','expected_revision':wrong_parent['state']['revision']}
            code,duplicate,_=client.request('create',duplicate_request);self.assertEqual(code,200,duplicate)
            unicode_request={'account':'neutral','kind':'niche','name':'Straße','expected_revision':duplicate['state']['revision']}
            code,unicode_created,_=client.request('create',unicode_request);self.assertEqual(code,200,unicode_created)
            unicode_duplicate_request={'account':'neutral','kind':'niche','name':'  STRASSE  ','expected_revision':unicode_created['state']['revision']}
            code,unicode_duplicate,_=client.request('create',unicode_duplicate_request);self.assertEqual(code,200,unicode_duplicate)
            fixtures={'a0':a0,'a1':a1,'b0':b0,'a4':a4,'a5':a5,'selectRequest':select,'prepareRequest':prepare,'prepared':prepared,
                      'createNicheRequest':create_niche,'createdNiche':niche,'createTopicRequest':create_topic,
                      'createdTopic':new_topic,'customSelectRequest':custom_select,'clearRequest':clear,
                      'wrongParent':wrong_parent,'duplicateRequest':duplicate_request,'duplicate':duplicate,
                      'unicodeDuplicateRequest':unicode_duplicate_request,'unicodeBeforeDuplicate':unicode_created['state'],'unicodeDuplicate':unicode_duplicate}
            value={'catalog':capabilities(),'html':(ROOT/'dashboard/index.html').read_text(),
                   'source':(ROOT/'dashboard/template-families.js').read_text(),
                   'panel':(ROOT/'dashboard/taxonomy-panel.js').read_text(),'fixtures':fixtures}
            result=subprocess.run(['node',str(ROOT/'tests/taxonomy_ui_probe.mjs')],input=json.dumps(value),capture_output=True,text=True,cwd=ROOT,
                                  timeout=120,env={'PATH':os.environ.get('PATH',''),'DO_NOT_TRACK':'1'})
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            report=json.loads(result.stdout);self.assertEqual(report['failures'],[]);self.assertEqual(len(report['passed']),17)
        finally:client.doCleanups()

    def test_accessible_labels_scoped_layout_and_no_executable_dom_sinks(self):
        class Parser(HTMLParser):
            def __init__(self):super().__init__();self.ids={};self.labels=set()
            def handle_starttag(self,tag,attrs):
                values=dict(attrs)
                if 'id' in values:
                    if values['id'] in self.ids:raise AssertionError('Duplicate DOM ID')
                    self.ids[values['id']]=(tag,values)
                if tag=='label':self.labels.add(values.get('for'))
        text=(ROOT/'dashboard/index.html').read_text();p=Parser();p.feed(text)
        for key in ('taxonomy-niche','taxonomy-topic','taxonomy-niche-name','taxonomy-topic-name'):
            self.assertIn(key,p.labels);self.assertIn(key,p.ids)
        self.assertEqual(p.ids['taxonomy-status'][1]['aria-live'],'polite');self.assertEqual(p.ids['taxonomy-status'][1]['role'],'status')
        self.assertIn('hidden',p.ids['taxonomy-panel'][1])
        self.assertLess(text.index('src="/taxonomy-panel.js"'),text.index('src="/template-families.js"'))
        source=(ROOT/'dashboard/taxonomy-panel.js').read_text()
        for token in ('innerHTML','outerHTML','insertAdjacentHTML','localStorage','sessionStorage','eval(','new Function'):
            self.assertNotIn(token,source)
        self.assertIn('.taxonomy-panel input,.taxonomy-panel select{min-width:0;max-width:100%;width:100%}',(ROOT/'dashboard/style.css').read_text())
