from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

import services.protocol.conversation as conversation_module
from services.protocol.conversation import ConversationRequest, ImageOutput, stream_image_outputs_with_pool


class ImageEmptyResultRetryTests(unittest.TestCase):
    def setUp(self):
        self.previous_value = conversation_module.config.data.get("image_empty_result_retry_enabled")

    def tearDown(self):
        if self.previous_value is None:
            conversation_module.config.data.pop("image_empty_result_retry_enabled", None)
        else:
            conversation_module.config.data["image_empty_result_retry_enabled"] = self.previous_value

    def test_retries_once_after_empty_image_result(self):
        conversation_module.config.data["image_empty_result_retry_enabled"] = True
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


if __name__ == "__main__":
    unittest.main()
