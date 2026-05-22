from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from api.support import require_identity
from services.image_conversation_service import image_conversation_service


class ImageConversationRequest(BaseModel):
    model_config = ConfigDict(extra="allow")


class ImageConversationBatchRequest(BaseModel):
    items: list[dict[str, object]] = Field(default_factory=list)


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/image-conversations")
    async def list_image_conversations(authorization: str | None = Header(default=None)):
        identity = require_identity(authorization)
        items = await run_in_threadpool(image_conversation_service.list_conversations, identity)
        return {"items": items}

    @router.post("/api/image-conversations")
    async def save_image_conversation(body: ImageConversationRequest, authorization: str | None = Header(default=None)):
        identity = require_identity(authorization)
        item = await run_in_threadpool(image_conversation_service.save_conversation, identity, body.model_dump(mode="python"))
        return {"item": item}

    @router.post("/api/image-conversations/batch")
    async def save_image_conversations(body: ImageConversationBatchRequest, authorization: str | None = Header(default=None)):
        identity = require_identity(authorization)
        items = await run_in_threadpool(image_conversation_service.save_conversations, identity, body.items)
        return {"items": items}

    @router.delete("/api/image-conversations/{conversation_id}")
    async def delete_image_conversation(conversation_id: str, authorization: str | None = Header(default=None)):
        identity = require_identity(authorization)
        deleted = await run_in_threadpool(image_conversation_service.delete_conversation, identity, conversation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail={"error": "image conversation not found"})
        return {"ok": True}

    @router.delete("/api/image-conversations")
    async def clear_image_conversations(authorization: str | None = Header(default=None)):
        identity = require_identity(authorization)
        deleted = await run_in_threadpool(image_conversation_service.clear_conversations, identity)
        return {"ok": True, "deleted": deleted}

    return router
