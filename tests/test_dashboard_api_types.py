"""Narrow public signatures resolve on Python3.9 without annotation coercion."""
import inspect
from pathlib import Path
import typing
import unittest

from storymotion.dashboard import Dashboard,Handler,LocalDashboardServer,make_server
from storymotion.dashboard_routes import json_get,JsonGetResponse


class DashboardAnnotationTests(unittest.TestCase):
    def test_route_forward_reference_resolves_with_explicit_dashboard_namespace(self):
        # TYPE_CHECKING imports avoid a runtime Dashboard <-> route cycle.
        hints=typing.get_type_hints(json_get,localns={'Dashboard':Dashboard})
        self.assertIs(hints['dashboard'],Dashboard);self.assertIs(hints['path'],str)
        self.assertIs(hints['ui_revision'],str);self.assertEqual(hints['return'],JsonGetResponse)
        self.assertEqual(set(hints),{'dashboard','path','ui_revision','current_provenance','capabilities','return'})

    def test_transport_and_server_public_parameters_have_precise_primitive_and_mode_types(self):
        self.assertEqual(typing.get_type_hints(Handler.send),{'status':int,'value':object,'return':type(None)})
        self.assertEqual(typing.get_type_hints(Handler.headers_for),{'mime':str,'length':int,'return':type(None)})
        hints=typing.get_type_hints(make_server)
        self.assertEqual(hints['workspace'],typing.Union[str,Path]);self.assertEqual(hints['hf'],typing.Optional[typing.Union[str,Path]])
        self.assertIs(hints['port'],int);self.assertIs(hints['return'],LocalDashboardServer)
        self.assertEqual(typing.get_args(hints['elevenlabs_mode']),('off','demo','live'))
        self.assertEqual(hints['elevenlabs_mode'],hints['llm_mode'])

    def test_existing_call_defaults_and_keyword_only_route_inputs_are_unchanged(self):
        params=inspect.signature(make_server).parameters
        self.assertEqual({name:p.default for name,p in params.items()},
                         {'workspace':'work','port':4397,'hf':None,'elevenlabs_mode':'off','llm_mode':'off'})
        params=inspect.signature(json_get).parameters
        self.assertEqual(tuple(params),('dashboard','path','ui_revision','current_provenance','capabilities'))
        for name in ('ui_revision','current_provenance','capabilities'):
            self.assertIs(params[name].kind,inspect.Parameter.KEYWORD_ONLY)
            self.assertIs(params[name].default,inspect.Parameter.empty)
