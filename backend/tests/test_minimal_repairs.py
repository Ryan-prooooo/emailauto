import importlib
import os
import sys
import asyncio
import unittest
from pathlib import Path
from typing import Annotated, get_args, get_origin
from unittest import mock


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class ChatRouteContractTests(unittest.TestCase):
    def test_chat_session_routes_are_registered(self) -> None:
        from app.api.routes_chat import router

        route_signatures = {
            (route.path, tuple(sorted(route.methods or [])))
            for route in router.routes
        }

        self.assertIn(("/chat/sessions", ("GET",)), route_signatures)
        self.assertIn(("/chat/sessions", ("POST",)), route_signatures)
        self.assertIn(("/chat/resume", ("POST",)), route_signatures)

    def test_chat_interrupt_returns_confirmation_payload(self) -> None:
        from langgraph.errors import GraphInterrupt

        from app.api.routes_chat import chat
        from app.api.schemas import ChatMessageRequest

        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return []

        class FakeDB:
            def query(self, *_args, **_kwargs):
                return FakeQuery()

            def add(self, *_args, **_kwargs):
                return None

            def commit(self):
                return None

        interrupt_payload = {
            "type": "confirmation",
            "title": "确认发送邮件",
            "message": "请确认",
            "draft_content": "draft body",
        }
        fake_agent = mock.Mock()
        fake_agent.chat.side_effect = GraphInterrupt(interrupt_payload)

        with mock.patch("app.agents.graph.email_agent.get_supervisor_agent", return_value=fake_agent):
            response = asyncio.run(
                chat(ChatMessageRequest(message="帮我回复这封邮件"), db=FakeDB())
            )

        self.assertEqual(response.status, "interrupted")
        self.assertEqual(response.interrupt["type"], "confirmation")
        self.assertTrue(response.thread_id)

    def test_get_chat_session_restores_pending_interrupt(self) -> None:
        from datetime import datetime

        from app.api.routes_chat import get_chat_session

        class FakeMessage:
            def __init__(self):
                self.role = "user"
                self.content = "draft me a reply"
                self.created_at = datetime(2026, 4, 27, 16, 0, 0)

        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def all(self):
                return [FakeMessage()]

        class FakeDB:
            def query(self, *_args, **_kwargs):
                return FakeQuery()

        fake_agent = mock.Mock()
        fake_agent.get_pending_interrupt.return_value = {
            "type": "confirmation",
            "title": "确认发送邮件",
            "message": "请确认",
            "draft_content": "draft body",
        }

        with mock.patch("app.agents.graph.email_agent.get_supervisor_agent", return_value=fake_agent):
            response = asyncio.run(get_chat_session("session-1", db=FakeDB()))

        self.assertEqual(response.status, "interrupted")
        self.assertEqual(response.thread_id, "email-session-1")
        self.assertEqual(response.interrupt["draft_content"], "draft body")


class SettingsCompatibilityTests(unittest.TestCase):
    def test_debug_release_value_does_not_break_settings_import(self) -> None:
        original_module = sys.modules.pop("app.core.config", None)

        try:
            with mock.patch.dict(os.environ, {"DEBUG": "release"}, clear=False):
                module = importlib.import_module("app.core.config")

            self.assertIsInstance(module.settings.DEBUG, bool)
            self.assertFalse(module.settings.DEBUG)
        finally:
            sys.modules.pop("app.core.config", None)
            if original_module is not None:
                sys.modules["app.core.config"] = original_module


class EventRouteContractTests(unittest.TestCase):
    def test_event_delete_route_is_registered(self) -> None:
        from app.api.routes_core import router

        route_signatures = {
            (route.path, tuple(sorted(route.methods or [])))
            for route in router.routes
        }

        self.assertIn(("/events/{event_id}", ("DELETE",)), route_signatures)

    def test_delete_event_returns_success_payload(self) -> None:
        from app.api.routes_core import delete_event

        class FakeEvent:
            def __init__(self, event_id: str) -> None:
                self.id = event_id

        class FakeQuery:
            def __init__(self, event: FakeEvent | None) -> None:
                self._event = event
                self.deleted = False

            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return self._event

            def delete(self):
                self.deleted = True
                self._event = None
                return 1

        class FakeDB:
            def __init__(self) -> None:
                self.query_obj = FakeQuery(FakeEvent("event-1"))
                self.committed = False

            def query(self, *_args, **_kwargs):
                return self.query_obj

            def commit(self):
                self.committed = True

        fake_db = FakeDB()
        response = asyncio.run(delete_event("event-1", db=fake_db))

        self.assertEqual(response, {"success": True, "event_id": "event-1"})
        self.assertTrue(fake_db.query_obj.deleted)
        self.assertTrue(fake_db.committed)


class IntentRoutingContractTests(unittest.TestCase):
    def test_single_intent_routes_return_multi_intent_labels(self) -> None:
        from app.agents.graph.email_agent import _route_intent
        from app.agents.graph.state import MultiIntentType

        self.assertEqual(
            _route_intent({"intents": ["query"]}),
            MultiIntentType.QUERY_ONLY.value,
        )
        self.assertEqual(
            _route_intent({"intents": ["general"]}),
            MultiIntentType.GENERAL_ONLY.value,
        )
        self.assertEqual(
            _route_intent({"intents": ["meeting"]}),
            MultiIntentType.MEETING_ONLY.value,
        )

    def test_empty_intents_route_to_unknown_label(self) -> None:
        from app.agents.graph.email_agent import _route_intent
        from app.agents.graph.state import MultiIntentType

        self.assertEqual(
            _route_intent({"intents": []}),
            MultiIntentType.UNKNOWN.value,
        )


class FinalStateExtractionTests(unittest.TestCase):
    def test_extract_final_state_prefers_top_level_final_response(self) -> None:
        from app.agents.graph.email_agent import _extract_final_state

        result = {
            "messages": [{"role": "user", "content": "查看我最近的安排"}],
            "intents": ["query"],
            "final_response": "事件列表：\n- 明天下午 3 点 周会",
            "execution_status": "completed",
        }

        self.assertEqual(_extract_final_state(result), result)


class LangGraphStateReducerTests(unittest.TestCase):
    def test_parallel_state_keys_use_annotated_reducers(self) -> None:
        from app.agents.graph.state import EmailAgentState

        for key in ("agent_outputs", "executed_nodes", "execution_status"):
            annotation = EmailAgentState.__annotations__[key]
            self.assertIs(get_origin(annotation), Annotated)
            self.assertGreaterEqual(len(get_args(annotation)), 2)


class ReplyAgentNullSafetyTests(unittest.TestCase):
    def test_reply_agent_handles_missing_summarizer_data(self) -> None:
        from app.agents.graph.nodes import reply_agent_node

        class FakeResult:
            success = True
            raw_output = "draft body"
            error = ""

        class FakeRegistry:
            def execute(self, *_args, **_kwargs):
                return FakeResult()

        class FakeEmail:
            id = 123
            sender = "sender@example.com"
            subject = "Subject"

        class FakeQuery:
            def order_by(self, *_args, **_kwargs):
                return self

            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return FakeEmail()

        class FakeDB:
            def query(self, *_args, **_kwargs):
                return FakeQuery()

            def close(self):
                return None

        state = {
            "action_params": {"tone": "professional"},
            "agent_outputs": {"summarizer": {"success": True, "data": None, "error": ""}},
        }

        with mock.patch("app.agents.graph.nodes.get_registry", return_value=FakeRegistry()):
            with mock.patch("langgraph.types.interrupt", return_value=None):
                with mock.patch("app.db.SessionLocal", return_value=FakeDB()):
                    result = reply_agent_node(state)

        self.assertEqual(result["execution_status"], "interrupted")
        self.assertEqual(result["pending_draft"]["email_id"], 123)
        self.assertEqual(result["agent_outputs"]["reply"]["draft_content"], "draft body")

    def test_reply_agent_handles_null_action_params(self) -> None:
        from app.agents.graph.nodes import reply_agent_node

        class FakeResult:
            success = True
            raw_output = "draft body"
            error = ""

        class FakeRegistry:
            def execute(self, *_args, **_kwargs):
                return FakeResult()

        class FakeEmail:
            id = 456
            sender = "sender@example.com"
            subject = "Subject"

        class FakeQuery:
            def order_by(self, *_args, **_kwargs):
                return self

            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return FakeEmail()

        class FakeDB:
            def query(self, *_args, **_kwargs):
                return FakeQuery()

            def close(self):
                return None

        state = {
            "action_params": None,
            "agent_outputs": {},
        }

        with mock.patch("app.agents.graph.nodes.get_registry", return_value=FakeRegistry()):
            with mock.patch("langgraph.types.interrupt", return_value=None):
                with mock.patch("app.db.SessionLocal", return_value=FakeDB()):
                    result = reply_agent_node(state)

        self.assertEqual(result["execution_status"], "interrupted")
        self.assertEqual(result["pending_draft"]["email_id"], 456)


if __name__ == "__main__":
    unittest.main()
