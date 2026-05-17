from __future__ import annotations

import base64
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.ai as ai_module
import services.protocol.openai_v1_image_edit as image_edit_module
from services.protocol.conversation import ImageOutput


AUTH_HEADERS = {"Authorization": "Bearer chatgpt2api"}
PNG_BYTES = b"\x89PNG\r\n\x1a\nreverse"
PNG_B64 = base64.b64encode(PNG_BYTES).decode("ascii")


class FakeLoggedCall:
    def __init__(self, *_args, **_kwargs):
        pass

    async def run(self, handler, payload, *_args, **_kwargs):
        return handler(payload)

    def log(self, *_args, **_kwargs):
        pass


class ImageReversePromptTests(unittest.TestCase):
    def test_v1_image_edits_can_return_text_for_reverse_prompt(self):
        captured_payload = {}

        def fake_handle(payload):
            captured_payload.update(payload)
            return {
                "created": 1,
                "data": [],
                "message": "一张电影感的城市夜景，霓虹灯，雨后街道，高细节。",
            }

        app = FastAPI()
        with (
            mock.patch.object(ai_module, "check_request", return_value=None),
            mock.patch.object(ai_module, "LoggedCall", FakeLoggedCall),
            mock.patch.object(ai_module.openai_v1_image_edit, "handle", side_effect=fake_handle),
        ):
            app.include_router(ai_module.create_router())
            client = TestClient(app)
            response = client.post(
                "/v1/images/edits",
                headers=AUTH_HEADERS,
                json={
                    "model": "gpt-image-2",
                    "prompt": "给出这个图片的提示词？",
                    "image": {"data": f"data:image/png;base64,{PNG_B64}", "filename": "input.png"},
                    "response_format": "url",
                    "message_as_error": False,
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["message"], "一张电影感的城市夜景，霓虹灯，雨后街道，高细节。")
        self.assertEqual(captured_payload["model"], "gpt-image-2")
        self.assertEqual(captured_payload["prompt"], "给出这个图片的提示词？")
        self.assertEqual(captured_payload["message_as_error"], False)
        self.assertEqual(captured_payload["images"][0], (PNG_BYTES, "input.png", "image/png"))

    def test_image_edit_handler_allows_text_message_when_requested(self):
        captured = {}

        def fake_stream(request):
            captured["message_as_error"] = request.message_as_error
            yield ImageOutput(
                kind="message",
                model=request.model,
                index=1,
                total=1,
                text="一张柔和自然光下的肖像照，真实摄影风格。",
            )

        with mock.patch.object(image_edit_module, "stream_image_outputs_with_pool", side_effect=fake_stream):
            result = image_edit_module.handle({
                "prompt": "给出这个图片的提示词？",
                "images": [(PNG_BYTES, "input.png", "image/png")],
                "model": "gpt-image-2",
                "message_as_error": False,
            })

        self.assertFalse(captured["message_as_error"])
        self.assertEqual(result["data"], [])
        self.assertEqual(result["message"], "一张柔和自然光下的肖像照，真实摄影风格。")


if __name__ == "__main__":
    unittest.main()
