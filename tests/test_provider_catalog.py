from pack_fixture_case import PackFixtureCase
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from storymotion.provider_catalog import (AdapterRegistration,CapabilityRegistry,ConnectionBinding,Endpoint,QueryParameter,
    build_registry,builtin_registry,load_catalog,public_capabilities,REMOTE_PROOF,LOCAL_PROOF)
from storymotion.providers import ADAPTERS,PROVIDERS
from storymotion.security import WorkflowError


class ProviderCatalogTests(PackFixtureCase):
    def test_legacy_plan_catalog_preserves_job_ids_without_false_adapter_or_model_claims(self):
        root=Path(__file__).resolve().parents[1]
        catalog=json.loads((root/'catalog/providers.json').read_text())
        rows={r['id']:r for r in catalog['providers']}
        for provider in ('openai','anthropic','gemini','openrouter'):
            self.assertIn(provider,ADAPTERS);self.assertEqual(rows[provider]['state'],REMOTE_PROOF)
            self.assertIn('metadata',rows[provider]['selection_scope'].lower())
        self.assertEqual(rows['openai']['models'][0]['id'],'model-selection-pending')
        self.assertNotIn('gpt-'+'6.1-sol',json.dumps(catalog))
        self.assertEqual(rows['openrouter']['models'][0]['id'],'model-id-pending')
        self.assertEqual(rows['anthropic']['models'][0]['id'],'model-selection-pending')
        self.assertFalse(catalog['live_calls_enabled'])
        self.assertNotIn('youtube',json.dumps(catalog).lower());self.assertNotIn('carousel',json.dumps(catalog).lower())

    def test_only_present_actual_adapters_are_registered(self):
        registry=build_registry(ADAPTERS,local_renderers=())
        self.assertEqual(set(registry.supported('text')),{'openai','anthropic','gemini','openrouter'})
        missing=build_registry({k:v for k,v in ADAPTERS.items() if k!='openai'},local_renderers=())
        row=next(r for r in public_capabilities(missing) if r['provider']=='openai' and r['capability']=='text')
        self.assertFalse(row['adapter_registered']);self.assertFalse(row['selectable']);self.assertIsNone(row['ui_target'])
        self.assertEqual(build_registry({},local_renderers=()).supported('text'),())

    def test_planned_media_cannot_be_selected_or_dispatched(self):
        registry=build_registry(ADAPTERS,local_renderers=())
        rows=public_capabilities(registry);planned=[r for r in rows if r['status']=='planned']
        self.assertTrue(planned)
        for row in planned:
            self.assertFalse(row['adapter_registered']);self.assertFalse(row['selectable']);self.assertFalse(row['dispatch_enabled'])
            self.assertIsNone(row['ui_target']);self.assertEqual(row['models'],[]);self.assertIsNone(row['limits'])
            with self.assertRaises(WorkflowError):registry.get(row['provider'],row['capability'])
        self.assertTrue(all(r['live_verified'] is False for r in rows))

    def test_builtin_post_endpoints_match_actual_adapter_plans(self):
        registry=build_registry(ADAPTERS,local_renderers=())
        for provider in ['openai','anthropic','gemini','openrouter']:
            model='vendor/model' if provider=='openrouter' else 'synthetic-model'
            plan=ADAPTERS[provider].build(model,'Synthetic contract prompt',100)
            self.assertEqual(registry.validate_endpoint(provider,'text','POST',plan.url).provider,provider)
        plan=ADAPTERS['elevenlabs'].build('synthetic-model','Synthetic speech text','synthetic-voice')
        registry.validate_endpoint('elevenlabs','voice','POST',plan.url)

    def test_fixed_metadata_pagination_shapes(self):
        registry=build_registry(ADAPTERS,local_renderers=())
        cases=[('openai','https://api.openai.com/v1/models'),
            ('anthropic','https://api.anthropic.com/v1/models?limit=100'),
            ('anthropic','https://api.anthropic.com/v1/models?limit=100&after_id=synthetic-cursor'),
            ('gemini','https://generativelanguage.googleapis.com/v1beta/models?pageSize=100&pageToken=synthetic%2Fcursor%3D'),
            ('openrouter','https://openrouter.ai/api/v1/models?offset=400&limit=100')]
        for provider,url in cases:registry.validate_endpoint(provider,'text','GET',url)
        registry.validate_endpoint('elevenlabs','voice','GET','https://api.elevenlabs.io/v2/voices?page_size=100&include_total_count=false&next_page_token=synthetic')
        for provider,url in [('anthropic','https://api.anthropic.com/v1/models?limit=100&limit=100'),
            ('openrouter','https://openrouter.ai/api/v1/models?offset=500&limit=100'),
            ('gemini','https://generativelanguage.googleapis.com/v1beta/models?pageSize=999')]:
            with self.subTest(url=url),self.assertRaises(WorkflowError):registry.validate_endpoint(provider,'text','GET',url)

    def test_request_data_cannot_change_endpoint_or_add_credential_query(self):
        registry=build_registry(ADAPTERS,local_renderers=())
        urls=['http://api.openai.com/v1/responses','https://api.openai.com.evil.test/v1/responses',
            'https://api.openai.com@evil.test/v1/responses','https://api.openai.com:443/v1/responses',
            'https://api.openai.com/v1/responses?api_key=synthetic','https://api.openai.com/v1/responses#',
            'https://api.openai.com/v1/../responses','https://api.openai.com/v1/%72esponses','https://api.openai.com/v1/responses\\other']
        for url in urls:
            with self.subTest(url=url),self.assertRaises(WorkflowError):registry.validate_endpoint('openai','text','POST',url)
        for url in ['https://generativelanguage.googleapis.com/v1beta/models/../../evil:generateContent',
            'https://generativelanguage.googleapis.com/v1beta/models/a%2Fb:generateContent',
            'https://generativelanguage.googleapis.com/v1beta/models/'+('a'*121)+':generateContent']:
            with self.assertRaises(WorkflowError):registry.validate_endpoint('gemini','text','POST',url)

    def test_provider_and_capability_connections_never_fallback(self):
        registry=build_registry(ADAPTERS,local_renderers=())
        good=ConnectionBinding('openai','text','openai:text','synthetic-session-a')
        registry.assert_connection('openai','text',good)
        for binding in [ConnectionBinding('anthropic','text','anthropic:text','synthetic-session-b'),
            ConnectionBinding('openai','image_generation','openai:image_generation','synthetic-session-c'),
            ConnectionBinding('openai','text','anthropic:text','synthetic-session-d')]:
            with self.assertRaises(WorkflowError):registry.assert_connection('openai','text',binding)
        with self.assertRaises(WorkflowError):registry.validate_endpoint('anthropic','text','POST','https://api.openai.com/v1/responses')

    def test_new_provider_and_capability_need_no_global_enum_change(self):
        self.assertNotIn('synthetic_vendor',PROVIDERS)
        registry=CapabilityRegistry()
        registration=AdapterRegistration('synthetic_vendor','depth_map','synthetic_vendor:depth_map',
            (Endpoint('POST','https://api.synthetic-vendor.example','/v1/depth/{item}'),),category='image',name='Synthetic host fixture')
        registry.register(registration)
        self.assertEqual(registry.supported('depth_map'),('synthetic_vendor',))
        registry.validate_endpoint('synthetic_vendor','depth_map','POST','https://api.synthetic-vendor.example/v1/depth/item-1')
        row=next(r for r in public_capabilities(registry) if r['provider']=='synthetic_vendor')
        self.assertTrue(row['adapter_registered']);self.assertFalse(row['dispatch_enabled']);self.assertIsNone(row['ui_target'])
        self.assertNotIn('synthetic_vendor',PROVIDERS)

    def test_json_is_not_registration_and_cannot_replace_host_endpoint(self):
        registry=CapabilityRegistry()
        with self.assertRaises(WorkflowError):registry.register({'provider':'openai','endpoint':'https://evil.test'})
        registration=AdapterRegistration('host_fixture','text','host_fixture:text',(Endpoint('POST','https://api.host-fixture.example','/v1/text'),))
        registry.register(registration)
        with self.assertRaises(WorkflowError):registry.register(registration)
        tampered=load_catalog();tampered['providers'][0]['enabled']=True
        original=Path.read_text
        def read(path,*args,**kwargs):return json.dumps(tampered) if path.name=='capabilities.json' else original(path,*args,**kwargs)
        with patch.object(Path,'read_text',read),self.assertRaises(WorkflowError):load_catalog()

    def test_local_render_is_separate_and_has_no_key_or_endpoint(self):
        registry=builtin_registry({},local_renderers=('hyperframes','remotion'))
        self.assertEqual(registry.supported('animation_render'),('hyperframes','remotion'))
        self.assertEqual(LOCAL_PROOF,'implemented_local_runtime_unverified')
        for row in public_capabilities(registry):
            if row['execution']=='local':
                self.assertIsNone(row['credential_scope']);self.assertEqual(row['ui_target'],'render')
                self.assertEqual(row['status'],LOCAL_PROOF);self.assertFalse(row['live_verified']);self.assertFalse(row['dispatch_enabled'])
        with self.assertRaises(WorkflowError):registry.validate_endpoint('remotion','animation_render','POST','https://api.example.test')

    def test_invalid_host_registrations_fail_closed(self):
        for origin in ['http://api.example.test','https://api.example.test:bad','https://user@api.example.test','https://api.example.test/path','https://api.example.test?']:
            with self.subTest(origin=origin),self.assertRaises(WorkflowError):Endpoint('POST',origin,'/v1/text')
        with self.assertRaises(WorkflowError):QueryParameter('api_key','cursor')
        with self.assertRaises(WorkflowError):AdapterRegistration('host_fixture','text','other:scope',(Endpoint('POST','https://api.example.test','/v1/text'),))


if __name__=='__main__':unittest.main()
