from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict

from api.support import require_identity
from services.image_canvas_service import image_canvas_service


class ImageCanvasProjectRequest(BaseModel):
    model_config = ConfigDict(extra="allow")


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/image-canvas/projects")
    async def list_image_canvas_projects(authorization: str | None = Header(default=None)):
        identity = require_identity(authorization)
        items = await run_in_threadpool(image_canvas_service.list_projects, identity)
        return {"items": items}

    @router.post("/api/image-canvas/projects")
    async def save_image_canvas_project(body: ImageCanvasProjectRequest, authorization: str | None = Header(default=None)):
        identity = require_identity(authorization)
        item = await run_in_threadpool(image_canvas_service.save_project, identity, body.model_dump(mode="python"))
        return {"item": item}

    @router.delete("/api/image-canvas/projects/{project_id}")
    async def delete_image_canvas_project(project_id: str, authorization: str | None = Header(default=None)):
        identity = require_identity(authorization)
        deleted = await run_in_threadpool(image_canvas_service.delete_project, identity, project_id)
        if not deleted:
            raise HTTPException(status_code=404, detail={"error": "这个画布不存在，可能已经被删除"})
        return {"ok": True}

    return router
