from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

import services.protocol.conversation as conversation_module
from services.protocol.conversation import ConversationRequest, ImageOutput, stream_image_outputs_with_pool


class ImageEmptyResultRetryTests(unittest.TestCase):
    def setUp(self):
        self.previous_values = {
            "image_empty_result_retry_enabled": conversation_module.config.data.get("image_empty_result_retry_enabled"),
            "image_pool_failover_enabled": conversation_module.config.data.get("image_pool_failover_enabled"),
            "image_pool_max_attempts": conversation_module.config.data.get("image_pool_max_attempts"),
            "image_account_failure_cooldown_secs": conversation_module.config.data.get("image_account_failure_cooldown_secs"),
            "image_poll_timeout_secs": conversation_module.config.data.get("image_poll_timeout_secs"),
            "image_unaccepted_task_timeout_secs": conversation_module.config.data.get("image_unaccepted_task_timeout_secs"),
            "image_stalled_result_timeout_secs": conversation_module.config.data.get("image_stalled_result_timeout_secs"),
        }

    def tearDown(self):
        for key, previous_value in self.previous_values.items():
            if previous_value is None:
                conversation_module.config.data.pop(key, None)
            else:
                conversation_module.config.data[key] = previous_value

    def test_retries_once_after_empty_image_result(self):
        conversation_module.config.data["image_empty_result_retry_enabled"] = True
        conversation_module.config.data["image_pool_failover_enabled"] = True
        conversation_module.config.data["image_pool_max_attempts"] = 2
        stream_calls: list[str] = []

        def fake_backend(access_token: str):
            return SimpleNamespace(access_token=access_token)

        def fake_stream(backend, request, index, total):
            stream_calls.append(backend.access_token)
            if len(stream_calls) == 1:
                yield ImageOutput(kind="progress", model=request.model, index=index, total=total)
                return
            yield ImageOutput(
                kind="result",
                model=request.model,
                index=index,
                total=total,
                data=[{"b64_json": "image-data"}],
            )

        with (
            mock.patch.object(conversation_module.account_service, "get_available_access_token", side_effect=["token-1", "token-2"]),
            mock.patch.object(conversation_module.account_service, "mark_image_result") as mark_result,
            mock.patch.object(conversation_module, "OpenAIBackendAPI", side_effect=fake_backend),
            mock.patch.object(conversation_module, "stream_image_outputs", side_effect=fake_stream),
        ):
            outputs = list(stream_image_outputs_with_pool(ConversationRequest(prompt="cat", model="gpt-image-2")))

        self.assertEqual(stream_calls, ["token-1", "token-2"])
        self.assertTrue(any(output.kind == "result" for output in outputs))
        mark_result.assert_has_calls([mock.call("token-1", False), mock.call("token-2", True)])

    def test_does_not_retry_empty_image_result_when_disabled(self):
        conversation_module.config.data["image_empty_result_retry_enabled"] = False

        def fake_stream(_backend, request, index, total):
            yield ImageOutput(kind="progress", model=request.model, index=index, total=total)

        with (
            mock.patch.object(conversation_module.account_service, "get_available_access_token", return_value="token-1"),
            mock.patch.object(conversation_module.account_service, "mark_image_result") as mark_result,
            mock.patch.object(conversation_module, "OpenAIBackendAPI", return_value=SimpleNamespace(access_token="token-1")),
            mock.patch.object(conversation_module, "stream_image_outputs", side_effect=fake_stream),
        ):
            outputs = list(stream_image_outputs_with_pool(ConversationRequest(prompt="cat", model="gpt-image-2")))

        self.assertFalse(any(output.kind == "result" for output in outputs))
        mark_result.assert_called_once_with("token-1", False)

    def test_transient_failure_fails_over_to_next_account(self):
        conversation_module.config.data["image_pool_failover_enabled"] = True
        conversation_module.config.data["image_pool_max_attempts"] = 2
        conversation_module.config.data["image_account_failure_cooldown_secs"] = 30
        stream_calls: list[str] = []

        def fake_backend(access_token: str):
            return SimpleNamespace(access_token=access_token)

        def fake_stream(backend, request, index, total):
            stream_calls.append(backend.access_token)
            if backend.access_token == "token-1":
                raise RuntimeError("upstream connection reset")
            yield ImageOutput(
                kind="result",
                model=request.model,
                index=index,
                total=total,
                data=[{"b64_json": "image-data"}],
            )

        with (
            mock.patch.object(conversation_module.account_service, "get_available_access_token", side_effect=["token-1", "token-2"]),
            mock.patch.object(conversation_module.account_service, "mark_image_result") as mark_result,
            mock.patch.object(conversation_module.account_service, "cooldown_image_token") as cooldown_token,
            mock.patch.object(conversation_module, "OpenAIBackendAPI", side_effect=fake_backend),
            mock.patch.object(conversation_module, "stream_image_outputs", side_effect=fake_stream),
        ):
            outputs = list(stream_image_outputs_with_pool(ConversationRequest(prompt="cat", model="gpt-image-2")))

        self.assertEqual(stream_calls, ["token-1", "token-2"])
        self.assertTrue(any(output.kind == "result" for output in outputs))
        mark_result.assert_has_calls([mock.call("token-1", False), mock.call("token-2", True)])
        cooldown_token.assert_called_once_with("token-1")

    def test_transient_failure_does_not_failover_when_disabled(self):
        conversation_module.config.data["image_pool_failover_enabled"] = False
        conversation_module.config.data["image_pool_max_attempts"] = 2

        def fake_stream(_backend, _request, _index, _total):
            raise RuntimeError("upstream connection reset")

        with (
            mock.patch.object(conversation_module.account_service, "get_available_access_token", return_value="token-1"),
            mock.patch.object(conversation_module.account_service, "mark_image_result") as mark_result,
            mock.patch.object(conversation_module.account_service, "cooldown_image_token") as cooldown_token,
            mock.patch.object(conversation_module, "OpenAIBackendAPI", return_value=SimpleNamespace(access_token="token-1")),
            mock.patch.object(conversation_module, "stream_image_outputs", side_effect=fake_stream),
        ):
            with self.assertRaises(conversation_module.ImageGenerationError):
                list(stream_image_outputs_with_pool(ConversationRequest(prompt="cat", model="gpt-image-2")))

        mark_result.assert_called_once_with("token-1", False)
        cooldown_token.assert_not_called()

    def test_image_quota_limit_message_marks_limited_and_fails_over(self):
        conversation_module.config.data["image_pool_failover_enabled"] = True
        conversation_module.config.data["image_pool_max_attempts"] = 2
        stream_calls: list[str] = []
        limit_message = (
            "You've hit the free plan limit for image generation requests. "
            "You can create more images when the limit resets in 11 hours and 13 minutes."
        )

        def fake_backend(access_token: str):
            return SimpleNamespace(access_token=access_token)

        def fake_stream(backend, request, index, total):
            stream_calls.append(backend.access_token)
            if backend.access_token == "token-1":
                yield ImageOutput(kind="message", model=request.model, index=index, total=total, text=limit_message)
                return
            yield ImageOutput(
                kind="result",
                model=request.model,
                index=index,
                total=total,
                data=[{"b64_json": "image-data"}],
            )

        with (
            mock.patch.object(conversation_module.account_service, "get_available_access_token", side_effect=["token-1", "token-2"]),
            mock.patch.object(conversation_module.account_service, "mark_image_result") as mark_result,
            mock.patch.object(conversation_module.account_service, "mark_image_limited") as mark_limited,
            mock.patch.object(conversation_module, "OpenAIBackendAPI", side_effect=fake_backend),
            mock.patch.object(conversation_module, "stream_image_outputs", side_effect=fake_stream),
        ):
            outputs = list(stream_image_outputs_with_pool(ConversationRequest(prompt="cat", model="gpt-image-2")))

        self.assertEqual(stream_calls, ["token-1", "token-2"])
        self.assertTrue(any(output.kind == "result" for output in outputs))
        self.assertEqual(mark_limited.call_args.args[0], "token-1")
        self.assertIsNotNone(mark_limited.call_args.args[1])
        mark_result.assert_called_once_with("token-2", True)

    def test_stream_uses_stalled_timeout_after_async_accept(self):
        conversation_module.config.data["image_pool_failover_enabled"] = True
        conversation_module.config.data["image_pool_max_attempts"] = 3
        conversation_module.config.data["image_poll_timeout_secs"] = 120
        conversation_module.config.data["image_stalled_result_timeout_secs"] = 45
        captured_timeouts: list[float | None] = []

        class FakeBackend:
            def resolve_conversation_image_urls(self, conversation_id, file_ids, sediment_ids, poll=True, poll_timeout_secs=None):
                captured_timeouts.append(poll_timeout_secs)
                return []

        events = [
            {"type": "conversation.event", "raw": {"type": "conversation_async_status"}, "conversation_id": "conv-1"},
            {"type": "conversation.event", "raw": {"type": "message_stream_complete"}, "conversation_id": "conv-1"},
        ]
        with mock.patch.object(conversation_module, "conversation_events", return_value=iter(events)):
            list(conversation_module.stream_image_outputs(FakeBackend(), ConversationRequest(prompt="cat", model="gpt-image-2")))

        self.assertEqual(captured_timeouts, [45])

    def test_stream_uses_short_timeout_when_image_task_not_accepted(self):
        conversation_module.config.data["image_pool_failover_enabled"] = True
        conversation_module.config.data["image_pool_max_attempts"] = 3
        conversation_module.config.data["image_poll_timeout_secs"] = 120
        conversation_module.config.data["image_unaccepted_task_timeout_secs"] = 12
        captured_timeouts: list[float | None] = []

        class FakeBackend:
            def resolve_conversation_image_urls(self, conversation_id, file_ids, sediment_ids, poll=True, poll_timeout_secs=None):
                captured_timeouts.append(poll_timeout_secs)
                return []

        events = [
            {"type": "conversation.event", "raw": {"type": "message_stream_complete"}, "conversation_id": "conv-1"},
        ]
        with mock.patch.object(conversation_module, "conversation_events", return_value=iter(events)):
            list(conversation_module.stream_image_outputs(FakeBackend(), ConversationRequest(prompt="cat", model="gpt-image-2")))

        self.assertEqual(captured_timeouts, [12])

    def test_empty_image_result_raises_after_max_attempts(self):
        conversation_module.config.data["image_empty_result_retry_enabled"] = True
        conversation_module.config.data["image_pool_failover_enabled"] = True
        conversation_module.config.data["image_pool_max_attempts"] = 1

        def fake_stream(_backend, request, index, total):
            yield ImageOutput(kind="progress", model=request.model, index=index, total=total)

        with (
            mock.patch.object(conversation_module.account_service, "get_available_access_token", return_value="token-1"),
            mock.patch.object(conversation_module.account_service, "mark_image_result") as mark_result,
            mock.patch.object(conversation_module.account_service, "cooldown_image_token") as cooldown_token,
            mock.patch.object(conversation_module, "OpenAIBackendAPI", return_value=SimpleNamespace(access_token="token-1")),
            mock.patch.object(conversation_module, "stream_image_outputs", side_effect=fake_stream),
        ):
            with self.assertRaises(conversation_module.ImageGenerationError):
                list(stream_image_outputs_with_pool(ConversationRequest(prompt="cat", model="gpt-image-2")))

        mark_result.assert_called_once_with("token-1", False)
        cooldown_token.assert_called_once_with("token-1")


if __name__ == "__main__":
    unittest.main()
