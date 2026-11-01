"""Final text-send authorization with inert credentials and offline transports."""
import contextlib
import dataclasses
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from pack_fixture_case import PackFixtureCase
from storymotion.llm_service import LLMService, DemoScriptTransport, golden_fixture
from storymotion.llm_api import LLMMetadataDemo, SYNTHETIC_MODEL_IDS
from storymotion.providers import ADAPTERS, HTTPSTransport, MockTransport, Permit, ProviderError, Response, SecretBroker
from storymotion.provider_runtime import ProviderRuntime
from storymotion.engine import Engine, ROOT
from storymotion.security import WorkflowError, canonical

KEY = 'FAKE_TEXT_FINAL_WIRE_CONTRACT_ONLY'
CONTEXT = {'account': 'sample-mechanism', 'title': 'Final wire contract',
           'brief': 'A synthetic source-bound request.', 'caption': ''}


def offline_connection(events, body=b'{}', on_connect=None, on_write=None, on_headers=None, status=200, location=None):
    """Drive the real urllib handler/do_open path without creating a socket."""
    class Socket:
        def settimeout(self, value):
            if value <= 0: raise AssertionError('write timeout must stay positive')
        def close(self): events.append('socket-closed')
    class Reply:
        status = code = 200
        reason = 'OK'
        def __init__(self):
            self.status = self.code = status
            self.headers = http.client.HTTPMessage(); self.headers['Content-Type'] = 'application/json'
            if location: self.headers['Location'] = location
            self.stream = io.BytesIO(body)
        def __enter__(self): return self
        def __exit__(self, *args): self.close()
        def read1(self, n): return self.stream.read(n)
        def read(self, n): return self.stream.read(n)
        def info(self): return self.headers
        def close(self): events.append('response-closed')
    class Connection:
        auto_open = 1
        debuglevel = 0
        _http_vsn = 11
        def __init__(self, host, timeout=None, **options):
            events.append(('host', host)); self.timeout = timeout; self.sock = None
        def set_debuglevel(self, value): pass
        def set_tunnel(self, *args, **kwargs): raise AssertionError('proxy tunnel forbidden')
        def connect(self):
            events.append('connect'); self.sock = Socket()
            if on_connect: on_connect()
        def request(self, method, selector, body=None, headers=None, *, encode_chunked=False):
            events.append('write')
            if on_write: on_write()
            if self.auto_open != 0: raise AssertionError('implicit reconnect must be disabled')
            self.send(b'synthetic-http-headers')
            if body: self.send(body)
        def send(self, data): events.append('send')
        def getresponse(self):
            events.append('headers')
            if on_headers: on_headers()
            return Reply()
        def close(self):
            events.append('closed')
            if self.sock: self.sock.close(); self.sock = None
    return Connection


class PreparedDemo(DemoScriptTransport):
    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def exchange(self, *args):
        self.entered.set()
        if not self.release.wait(10):
            raise AssertionError('offline transport preparation barrier timeout')
        return super().exchange(*args)


class QueuedTextGateTests(PackFixtureCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='text-final-wire-')
        self.source = {'fingerprint': 'owned-synthetic-text-wire-source'}
        self.patch = patch('storymotion.llm_service.current_execution', side_effect=lambda: self.source['fingerprint'])
        self.patch.start()
        self.transport = PreparedDemo()
        self.s = LLMService(Path(self.temp.name), mode='demo', transport=self.transport)
        self.ref = self.s.connect('openai', KEY)['connection']

    def tearDown(self):
        self.transport.release.set()
        self.s.close()
        self.patch.stop()
        self.temp.cleanup()

    def approved(self):
        request = self.s.preview(self.ref, CONTEXT, 2000, model=SYNTHETIC_MODEL_IDS['openai'])['request']
        self.s.approve(self.ref, request, 2000, True, True)
        return request

    def queued(self, mutate):
        request = self.approved()
        self.s.execute(self.ref, request)
        worker = self.s.threads.get(request)
        try:
            self.assertTrue(self.transport.entered.wait(5))
            mutate(request)
        finally:
            self.transport.release.set()
            if worker:
                worker.join(15)
        self.assertFalse(worker and worker.is_alive())
        return self.s.get(request)

    def no_send(self, result, status='blocked_before_dispatch'):
        self.assertEqual(result['status'], status)
        self.assertEqual(result['dispatch_count'], 0)
        self.assertIsNone(result['artifact'])
        self.assertFalse(self.transport.calls)
        if status != 'cancelled':
            self.assertIsNone(result['approval'])
            self.assertIsNone(result['approved_until'])
        with self.assertRaises(WorkflowError):
            self.s.execute(self.ref, result['request'], False)

    def test_metadata_expiry_after_transport_preparation_has_zero_send(self):
        self.no_send(self.queued(lambda _: self.s.connections[self.ref].update(metadata_until=0)))

    def test_disabled_service_after_transport_preparation_has_zero_send(self):
        self.no_send(self.queued(lambda _: setattr(self.s, 'mode', 'off')))

    def test_model_revocation_after_transport_preparation_has_zero_send(self):
        self.no_send(self.queued(lambda _: self.s.connections[self.ref]['metadata'].update(models=[])))

    def test_lower_model_limit_after_transport_preparation_has_zero_send(self):
        def lower(_):
            self.s.connections[self.ref]['metadata']['models'][0]['max_output_tokens'] = 100
        self.no_send(self.queued(lower))

    def test_execution_source_invalidation_after_preparation_has_zero_send(self):
        self.no_send(self.queued(lambda _: self.source.update(fingerprint='changed-synthetic-source')))

    def test_host_source_context_invalidation_after_preparation_has_zero_send(self):
        def invalidate(_):
            with self.s.db() as db:
                db.execute('INSERT OR REPLACE INTO writing_context_heads VALUES(?,?,?)',
                           ('sources', CONTEXT['account'], '0'*64))
        self.no_send(self.queued(invalidate))

    def test_connection_binding_cannot_change_after_preparation(self):
        self.no_send(self.queued(lambda request: self.s.bindings.update({request:'other-synthetic-connection'})))

    def test_approval_expiry_after_preparation_has_zero_send(self):
        def expire(request):
            with self.s.db() as db:
                db.execute('UPDATE llm_requests SET approved_until=0 WHERE id=?', (request,))
        self.no_send(self.queued(expire))

    def test_claim_budget_cannot_change_between_approval_and_send(self):
        def mutate(request):
            with self.s.db() as db:
                row = db.execute('SELECT approval FROM llm_requests WHERE id=?', (request,)).fetchone()
                approval = json.loads(row[0])
                approval['budget']['maximum_microusd'] = 100
                db.execute('UPDATE llm_requests SET approval=? WHERE id=?', (canonical(approval), request))
        self.no_send(self.queued(mutate))

    def test_durable_claim_rejects_approval_tamper_before_worker_reads_it(self):
        request = self.approved()
        original = self.s._work
        def changed(ref, identity):
            with self.s.db() as db:
                row = db.execute('SELECT approval FROM llm_requests WHERE id=?', (identity,)).fetchone()
                approval = json.loads(row[0]); approval['budget']['maximum_microusd'] = 100
                db.execute('UPDATE llm_requests SET approval=? WHERE id=?', (canonical(approval), identity))
            original(ref, identity)
        self.transport.release.set()
        with patch.object(self.s, '_work', side_effect=changed):
            result = self.s.execute(self.ref, request, False)
        self.no_send(result)

    def test_rights_consent_cannot_change_between_approval_and_send(self):
        def mutate(request):
            with self.s.db() as db:
                row = db.execute('SELECT approval FROM llm_requests WHERE id=?', (request,)).fetchone()
                approval = json.loads(row[0]); approval['rights_confirmed'] = False
                db.execute('UPDATE llm_requests SET approval=? WHERE id=?', (canonical(approval), request))
        self.no_send(self.queued(mutate))

    def test_claim_body_cannot_change_between_approval_and_send(self):
        def mutate(request):
            with self.s.db() as db:
                row = db.execute('SELECT payload FROM llm_requests WHERE id=?', (request,)).fetchone()
                payload = json.loads(row[0])
                payload['context']['brief'] = 'Different synthetic input'
                db.execute('UPDATE llm_requests SET payload=? WHERE id=?', (canonical(payload), request))
        self.no_send(self.queued(mutate))

    def test_disconnect_after_preparation_has_zero_send(self):
        self.no_send(self.queued(lambda _: self.s.disconnect(self.ref)), 'cancelled')

    def test_cancel_after_preparation_has_zero_send(self):
        self.no_send(self.queued(lambda request: self.s.cancel(request)), 'cancelled')

    def test_cleared_credential_after_preparation_has_zero_send(self):
        self.no_send(self.queued(lambda _: self.s.broker.clear()))

    def test_clear_during_source_validation_after_preparation_has_zero_send(self):
        request = self.approved(); entered = threading.Event(); release = threading.Event()
        original = self.s._verify_payload
        def validate(payload):
            result = original(payload)
            if self.transport.entered.is_set():
                entered.set()
                if not release.wait(10): raise AssertionError('validation barrier timeout')
            return result
        with patch.object(self.s, '_verify_payload', side_effect=validate):
            self.s.execute(self.ref, request); worker = self.s.threads[request]
            try:
                self.assertTrue(self.transport.entered.wait(5)); self.transport.release.set()
                self.assertTrue(entered.wait(5)); self.s.broker.clear()
            finally:
                release.set(); worker.join(15)
            self.assertFalse(worker.is_alive())
        self.no_send(self.s.get(request))

    def _cancel_reapprove_stale_worker(self, finish_new_first):
        request = self.approved(); original_transport = self.transport
        fresh_transport = PreparedDemo(); workers = []
        try:
            self.s.execute(self.ref, request); old = self.s.threads[request]; workers.append(old)
            self.assertTrue(original_transport.entered.wait(5))
            self.assertEqual(self.s.cancel(request)['status'], 'cancelled')
            self.s.transport = fresh_transport
            self.assertEqual(self.approved(), request)
            self.s.execute(self.ref, request); fresh = self.s.threads[request]; workers.append(fresh)
            self.assertTrue(fresh_transport.entered.wait(5))
            if finish_new_first:
                fresh_transport.release.set(); fresh.join(15)
                self.assertEqual(self.s.get(request)['status'], 'completed')
            original_transport.release.set(); old.join(15)
            self.assertFalse(old.is_alive())
            if not finish_new_first:
                pending = self.s.get(request)
                self.assertEqual(pending['status'], 'dispatching'); self.assertEqual(pending['dispatch_count'], 0)
                self.assertIsNotNone(pending['approval']); self.assertIs(self.s.threads[request], fresh)
                fresh_transport.release.set(); fresh.join(15)
            self.assertFalse(fresh.is_alive())
            self.assertEqual(self.s.get(request)['status'], 'completed')
            self.assertEqual(self.s.get(request)['dispatch_count'], 1)
            self.assertFalse(original_transport.calls); self.assertEqual(len(fresh_transport.calls), 1)
        finally:
            original_transport.release.set(); fresh_transport.release.set()
            for worker in workers: worker.join(15)

    def test_stale_worker_cannot_clear_reapproved_claim_or_remove_new_thread(self):
        self._cancel_reapprove_stale_worker(False)

    def test_stale_worker_cannot_reclassify_completed_fresh_result(self):
        self._cancel_reapprove_stale_worker(True)

    def test_claim_tokens_are_unique_even_with_frozen_wall_clock(self):
        with patch('storymotion.llm_service.time.time', return_value=time.time()):
            request = self.approved(); first = self.s._claim(self.ref, request)
            self.s.cancel(request); self.assertEqual(self.approved(), request)
            second = self.s._claim(self.ref, request)
        self.assertNotEqual(first, second)

    def test_unspent_expired_dispatch_is_not_reported_as_uncertain(self):
        request = self.approved()
        with self.s.db() as db:
            db.execute("UPDATE llm_requests SET status='dispatching',deadline=0 WHERE id=?", (request,))
        self.no_send(self.s.get(request))

    def test_recovery_requires_new_preview_and_consent_before_one_send(self):
        result = self.queued(lambda _: self.s.connections[self.ref].update(metadata_until=0))
        self.no_send(result)
        self.s.metadata(self.ref)
        request = self.approved()
        self.assertEqual(request, result['request'])
        self.assertEqual(self.s.execute(self.ref, request, False)['status'], 'completed')
        self.assertEqual(len(self.transport.calls), 1)

    def test_error_after_final_gate_retains_uncertain_hold_and_never_retries(self):
        request = self.approved()
        self.transport.release.set()
        self.transport.error = 'TRANSPORT_OUTCOME_UNCERTAIN'
        result = self.s.execute(self.ref, request, False)
        self.assertEqual(result['status'], 'uncertain')
        self.assertEqual(result['dispatch_count'], 1)
        self.assertEqual(len(self.transport.calls), 1)
        with self.assertRaises(ProviderError):
            self.s.execute(self.ref, request, False)
        self.assertEqual(len(self.transport.calls), 1)


class TransportFinalTextGateTests(unittest.TestCase):
    def setUp(self):
        self.plan = ADAPTERS['openai'].build('synthetic-text-model', 'Synthetic contract input.', 32)
        self.permit = Permit(self.plan.fingerprint, 'synthetic-job', 2, 1, time.time()+60, 'Synthetic consent')
        self.key = b'INERT_TEXT_WIRE_CONTRACT_CREDENTIAL'

    def test_http_gate_runs_after_verified_connect_before_any_request_write(self):
        events = []
        valid = {'value': True}
        @contextlib.contextmanager
        def gate(*args):
            events.append('gate')
            if not valid['value']:
                raise ProviderError('SYNTHETIC_FINAL_INVALIDATION')
            yield
        permit = dataclasses.replace(self.permit, send_gate=gate)
        connection = offline_connection(events, on_connect=lambda: valid.update(value=False))
        with patch('storymotion.providers.http.client.HTTPSConnection', connection):
            with self.assertRaisesRegex(ProviderError, 'FINAL_INVALIDATION'):
                HTTPSTransport(True).exchange(self.plan, self.key, permit, 'synthetic-job')
        self.assertLess(events.index('connect'), events.index('gate'))
        self.assertNotIn('write', events); self.assertIn('closed', events)

    def test_expired_permit_during_preparation_never_opens(self):
        clock = {'now': time.time()}
        permit = dataclasses.replace(self.permit, expires_at=clock['now']+1)
        calls = []
        class Opener:
            def open(self, *args, **kwargs):
                calls.append('open')
                raise AssertionError('expired request must never open')
        def prepare(*args):
            clock['now'] += 2
            return Opener()
        with patch('storymotion.providers.time.time', side_effect=lambda: clock['now']), patch('urllib.request.build_opener', side_effect=prepare):
            with self.assertRaisesRegex(ProviderError, 'EXPIRY'):
                HTTPSTransport(True).exchange(self.plan, self.key, permit, 'synthetic-job')
        self.assertFalse(calls)

    def test_final_gate_is_released_before_response_headers_and_body(self):
        state = {'gate': False}
        observed = []
        @contextlib.contextmanager
        def gate(*args):
            state['gate'] = True
            try:
                yield
            finally:
                state['gate'] = False
        connection = offline_connection([], on_connect=lambda: observed.append(('connect', state['gate'])),
            on_write=lambda: observed.append(('write', state['gate'])),
            on_headers=lambda: observed.append(('headers', state['gate'])))
        permit = dataclasses.replace(self.permit, send_gate=gate)
        with patch('storymotion.providers.http.client.HTTPSConnection', connection):
            HTTPSTransport(True).exchange(self.plan, self.key, permit, 'synthetic-job')
        self.assertEqual(observed, [('connect', False), ('write', True), ('headers', False)])

    def test_live_transport_disabled_during_preparation_never_opens(self):
        calls = []
        transport = HTTPSTransport(True)
        class Opener:
            def open(self, *args, **kwargs):
                calls.append('open')
                raise AssertionError('disabled transport must never open')
        def prepare(*args):
            transport.allow_live = False
            return Opener()
        with patch('urllib.request.build_opener', side_effect=prepare):
            with self.assertRaisesRegex(ProviderError, 'DISABLED'):
                transport.exchange(self.plan, self.key, self.permit, 'synthetic-job')
        self.assertFalse(calls)

    def test_broker_clear_or_expiry_after_connect_prevents_request_write(self):
        for action in ('clear', 'expire'):
            with self.subTest(action=action):
                broker = SecretBroker(real_intake_enabled=True); events = []
                slot = broker.put('openai', 'synthetic-job', self.plan.fingerprint, self.key.decode())
                @contextlib.contextmanager
                def gate(*args):
                    with broker.send_lease(slot, 'openai', 'synthetic-job', self.plan.fingerprint, False):
                        yield
                def invalidate():
                    if action == 'clear': broker.clear(slot)
                    else: broker._slots[slot]['expires'] = 0
                connection = offline_connection(events, on_connect=invalidate)
                try:
                    with patch('storymotion.providers.http.client.HTTPSConnection', connection):
                        with self.assertRaisesRegex(ProviderError, 'CREDENTIAL_EXPIRED'):
                            HTTPSTransport(True).exchange(self.plan, self.key, dataclasses.replace(self.permit, send_gate=gate), 'synthetic-job')
                    self.assertNotIn('write', events); self.assertIn('closed', events)
                finally: broker.clear()

    def test_broker_clear_serializes_with_connected_request_write_only(self):
        broker = SecretBroker(real_intake_enabled=True); events = []; started = threading.Event(); done = threading.Event(); threads = []
        slot = broker.put('openai', 'synthetic-job', self.plan.fingerprint, self.key.decode())
        @contextlib.contextmanager
        def gate(*args):
            with broker.send_lease(slot, 'openai', 'synthetic-job', self.plan.fingerprint, False): yield
        def clear():
            started.set(); broker.clear(slot); done.set()
        def writing():
            thread = threading.Thread(target=clear); threads.append(thread); thread.start()
            self.assertTrue(started.wait(2)); self.assertFalse(done.wait(.05))
        def headers():
            self.assertTrue(done.wait(2))
        try:
            connection = offline_connection(events, on_write=writing, on_headers=headers)
            with patch('storymotion.providers.http.client.HTTPSConnection', connection):
                HTTPSTransport(True).exchange(self.plan, self.key, dataclasses.replace(self.permit, send_gate=gate), 'synthetic-job')
            self.assertEqual(events.count('write'), 1); self.assertTrue(done.is_set())
        finally:
            for thread in threads: thread.join(2)
            broker.clear()

    def test_real_handler_disables_environment_proxies_and_refuses_redirect(self):
        events = []
        connection = offline_connection(events, status=302, location='https://other.invalid/next')
        with patch.dict('os.environ', {'HTTPS_PROXY':'https://untrusted-proxy.invalid','https_proxy':'https://untrusted-proxy.invalid'}), patch('storymotion.providers.http.client.HTTPSConnection', connection):
            with self.assertRaisesRegex(ProviderError, 'REDIRECT_BLOCKED'):
                HTTPSTransport(True).exchange(self.plan, self.key, self.permit, 'synthetic-job')
        self.assertEqual(events.count('connect'), 1); self.assertEqual(events.count('write'), 1)
        self.assertIn(('host', 'api.openai.com'), events)


class HttpServiceFinalTextGateTests(PackFixtureCase):
    def test_stubbed_http_service_records_one_authorized_send_and_reuses_receipt(self):
        class Metadata(LLMMetadataDemo):
            synthetic = False
            def list_models(self, provider, key):
                return super().list_models(provider, b'FAKE_METADATA_CONTRACT_ONLY')
        with tempfile.TemporaryDirectory(prefix='text-http-success-') as directory, patch('storymotion.llm_service.current_execution', return_value='synthetic-http-source'):
            service = LLMService(directory, mode='live', metadata_client=Metadata(), transport=HTTPSTransport(True))
            try:
                ref = service.connect('openai', 'INERT_TEXT_HTTP_CONTRACT_CREDENTIAL')['connection']
                request = service.preview(ref, CONTEXT, 2000, model=SYNTHETIC_MODEL_IDS['openai'])['request']
                service.approve(ref, request, 2000, True, True, {'max_usd':'.02','estimate_usd':'.01',
                    'quote_source':'Synthetic test quote, not market pricing','verified_by_user':True})
                body = canonical({'id':'synthetic-http-result','status':'completed','output':[{'type':'message',
                    'content':[{'type':'output_text','text':canonical(golden_fixture(CONTEXT['account']))}]}],
                    'usage':{'input_tokens':1,'output_tokens':1}}).encode()
                events = []
                connection = offline_connection(events, body=body)
                with patch('storymotion.providers.http.client.HTTPSConnection', connection):
                    result = service.execute(ref, request, False)
                    reused = service.execute(ref, request, False)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(result['dispatch_count'], 1)
                self.assertEqual(reused['artifact'], result['artifact'])
                self.assertEqual(events.count('write'), 1)
                self.assertEqual(events.count('connect'), 1)
                self.assertFalse(result['artifact']['synthetic'])
                self.assertIsNone(result['artifact']['actual_cost_usd'])
            finally:
                service.close()

    def test_service_metadata_invalidation_during_real_transport_preparation_is_blocked(self):
        # Exercise the actual urllib assembly path with an inert metadata client
        # and connected-HTTPS stub. No socket, real key or provider is used.
        class Metadata(LLMMetadataDemo):
            synthetic = False
            def list_models(self, provider, key):
                # The inherited fixture intentionally rejects non-FAKE input.
                # Supply its own inert fixture token, never forward a real key.
                return super().list_models(provider, b'FAKE_METADATA_CONTRACT_ONLY')
        with tempfile.TemporaryDirectory(prefix='text-http-final-') as directory, patch('storymotion.llm_service.current_execution', return_value='synthetic-http-source'):
            service = LLMService(directory, mode='live', metadata_client=Metadata(), transport=HTTPSTransport(True))
            try:
                ref = service.connect('openai', 'INERT_TEXT_HTTP_CONTRACT_CREDENTIAL')['connection']
                request = service.preview(ref, CONTEXT, 2000, model=SYNTHETIC_MODEL_IDS['openai'])['request']
                service.approve(ref, request, 2000, True, True, {'max_usd':'.02','estimate_usd':'.01',
                    'quote_source':'Synthetic test quote, not market pricing','verified_by_user':True})
                events = []
                connection = offline_connection(events, on_connect=lambda:service.connections[ref].update(metadata_until=0))
                with patch('storymotion.providers.http.client.HTTPSConnection', connection):
                    result = service.execute(ref, request, False)
                self.assertEqual(result['status'], 'blocked_before_dispatch')
                self.assertEqual(result['dispatch_count'], 0)
                self.assertIsNone(result['approval'])
                self.assertIn('connect', events); self.assertNotIn('write', events); self.assertIn('closed', events)
            finally:
                service.close()


class RuntimeFinalTextGateTests(PackFixtureCase):
    def test_revoked_runtime_approval_during_transport_preparation_has_zero_send(self):
        class PreparedMock(MockTransport):
            mutate = None
            def exchange(self, *args):
                if self.mutate:
                    self.mutate(); self.mutate = None
                return super().exchange(*args)
        with tempfile.TemporaryDirectory(prefix='runtime-text-wire-') as directory:
            engine = Engine(Path(directory)/'work')
            broker = SecretBroker()
            response = Response(200, 'application/json', canonical({'id':'synthetic-result','status':'completed',
                'output':[{'type':'message','content':[{'type':'output_text','text':'Safe synthetic output.'}]}]}).encode())
            transport = PreparedMock(response)
            runtime = ProviderRuntime(Path(directory)/'work', broker, transport)
            try:
                job = engine.create(ROOT/'tests/fixtures/examples/sample-mechanism.json')['job']
                plan = ADAPTERS['openai'].build('synthetic-runtime-model', 'Contract input only.', 32)
                request = runtime.prepare(job, plan, '.01', 'Synthetic quote')['request']
                runtime.approve(request, '.02', 'Synthetic consent')
                slot = broker.put('openai', job, plan.fingerprint, KEY, synthetic=True)
                def expire():
                    runtime.store.db.execute('UPDATE provider_requests SET expires=0 WHERE id=?', (request,))
                    runtime.store.db.commit()
                transport.mutate = expire
                with self.assertRaises(ProviderError):
                    runtime.run(request, slot)
                self.assertEqual(runtime.row(request)['status'], 'blocked_before_dispatch')
                self.assertIsNone(runtime.row(request)['cap'])
                self.assertFalse(transport.calls)
                # Explicit preparation resets only the unspent intent; budget
                # approval is required again rather than silently retrying it.
                runtime.prepare(job, plan, '.01', 'Synthetic quote')
                with self.assertRaisesRegex(ProviderError, 'NOT_APPROVED'):
                    runtime.run(request, slot)
                self.assertFalse(transport.calls)
            finally:
                runtime.close(); broker.clear(); engine.close()
