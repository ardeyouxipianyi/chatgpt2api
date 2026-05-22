from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from services.config import DATA_DIR


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: object, default: str = "") -> str:
    return str(value or default).strip()


def _number(value: object, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if number == number and number not in {float("inf"), float("-inf")} else fallback


def _owner_id(identity: dict[str, object]) -> str:
    return _clean(identity.get("id")) or "anonymous"


def _new_id() -> str:
    return uuid.uuid4().hex


def _normalize_reference_image(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None
    data_url = _clean(raw.get("dataUrl"))
    if not data_url:
        return None
    return {
        "name": _clean(raw.get("name"), "reference.png"),
        "type": _clean(raw.get("type"), "image/png"),
        "dataUrl": data_url,
    }


def _normalize_stored_image(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None
    image_id = _clean(raw.get("id")) or _new_id()
    status = _clean(raw.get("status"))
    if status not in {"loading", "success", "error"}:
        status = "success" if _clean(raw.get("b64_json")) or _clean(raw.get("url")) else "loading"
    image: dict[str, object] = {
        "id": image_id,
        "status": status,
    }
    for key in ("taskId", "b64_json", "url", "revised_prompt", "error"):
        value = raw.get(key)
        if isinstance(value, str) and value:
            image[key] = value
    return image


def _normalize_turn(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None
    now = _now_iso()
    images = [
        image
        for item in raw.get("images", [])
        if (image := _normalize_stored_image(item)) is not None
    ] if isinstance(raw.get("images"), list) else []
    reference_images = [
        image
        for item in raw.get("referenceImages", [])
        if (image := _normalize_reference_image(item)) is not None
    ] if isinstance(raw.get("referenceImages"), list) else []
    status = _clean(raw.get("status"))
    if status not in {"queued", "generating", "success", "error"}:
        if any(image.get("status") == "loading" for image in images):
            status = "generating"
        elif any(image.get("status") == "error" for image in images):
            status = "error"
        else:
            status = "success"
    mode = _clean(raw.get("mode"))
    return {
        "id": _clean(raw.get("id")) or _new_id(),
        "prompt": str(raw.get("prompt") or ""),
        "model": _clean(raw.get("model"), "gpt-image-2"),
        "mode": "edit" if mode == "edit" else "generate",
        "referenceImages": reference_images,
        "count": max(1, int(_number(raw.get("count"), len(images) or 1))),
        "size": _clean(raw.get("size")),
        "images": images,
        "createdAt": _clean(raw.get("createdAt"), now),
        "status": status,
        **({"error": _clean(raw.get("error"))} if _clean(raw.get("error")) else {}),
        "promptDeleted": raw.get("promptDeleted") is True,
        "resultsDeleted": raw.get("resultsDeleted") is True,
    }


def _normalize_conversation(raw: object, owner_id: str) -> dict[str, object]:
    source = raw if isinstance(raw, dict) else {}
    now = _now_iso()
    turns = [
        turn
        for item in source.get("turns", [])
        if (turn := _normalize_turn(item)) is not None
    ] if isinstance(source.get("turns"), list) else []
    if not turns:
        legacy_turn = _normalize_turn({
            "id": source.get("id"),
            "prompt": source.get("prompt"),
            "model": source.get("model"),
            "mode": source.get("mode"),
            "referenceImages": source.get("referenceImages"),
            "count": source.get("count"),
            "size": source.get("size"),
            "images": source.get("images"),
            "createdAt": source.get("createdAt"),
            "status": source.get("status"),
            "error": source.get("error"),
        })
        if legacy_turn is not None:
            turns = [legacy_turn]
    updated_at = _clean(source.get("updatedAt")) or _clean(turns[-1].get("createdAt") if turns else None, now)
    return {
        "owner_id": owner_id,
        "id": _clean(source.get("id")) or _new_id(),
        "title": str(source.get("title") or ""),
        "createdAt": _clean(source.get("createdAt"), _clean(turns[0].get("createdAt") if turns else None, now)),
        "updatedAt": updated_at,
        "turns": turns,
    }


def _public_conversation(conversation: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in conversation.items() if key != "owner_id"}


class ImageConversationService:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items = self._load()

    def _load(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        raw_items = raw.get("conversations") if isinstance(raw, dict) else raw
        if not isinstance(raw_items, list):
            return {}
        conversations: dict[str, dict[str, object]] = {}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            owner = _clean(item.get("owner_id"))
            if not owner:
                continue
            conversation = _normalize_conversation(item, owner)
            conversations[f"{owner}:{conversation['id']}"] = conversation
        return conversations

    def _save_locked(self) -> None:
        items = sorted(self._items.values(), key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps({"conversations": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(self.path)

    def reload(self) -> None:
        with self._lock:
            self._items = self._load()

    def list_conversations(self, identity: dict[str, object]) -> list[dict[str, object]]:
        owner = _owner_id(identity)
        with self._lock:
            items = [_public_conversation(item) for item in self._items.values() if item.get("owner_id") == owner]
        return sorted(items, key=lambda item: str(item.get("updatedAt") or ""), reverse=True)

    def save_conversation(self, identity: dict[str, object], conversation: dict[str, object]) -> dict[str, object]:
        owner = _owner_id(identity)
        normalized = _normalize_conversation(conversation, owner)
        normalized["updatedAt"] = _clean(conversation.get("updatedAt") if isinstance(conversation, dict) else None, _now_iso())
        with self._lock:
            self._items[f"{owner}:{normalized['id']}"] = normalized
            self._save_locked()
        return _public_conversation(normalized)

    def save_conversations(self, identity: dict[str, object], conversations: list[dict[str, object]]) -> list[dict[str, object]]:
        owner = _owner_id(identity)
        saved: list[dict[str, object]] = []
        with self._lock:
            for conversation in conversations:
                normalized = _normalize_conversation(conversation, owner)
                normalized["updatedAt"] = _clean(conversation.get("updatedAt"), _now_iso())
                self._items[f"{owner}:{normalized['id']}"] = normalized
                saved.append(_public_conversation(normalized))
            self._save_locked()
        return sorted(saved, key=lambda item: str(item.get("updatedAt") or ""), reverse=True)

    def delete_conversation(self, identity: dict[str, object], conversation_id: str) -> bool:
        owner = _owner_id(identity)
        key = f"{owner}:{_clean(conversation_id)}"
        with self._lock:
            if key not in self._items:
                return False
            self._items.pop(key, None)
            self._save_locked()
            return True

    def clear_conversations(self, identity: dict[str, object]) -> int:
        owner = _owner_id(identity)
        with self._lock:
            keys = [key for key, item in self._items.items() if item.get("owner_id") == owner]
            for key in keys:
                self._items.pop(key, None)
            self._save_locked()
        return len(keys)


image_conversation_service = ImageConversationService(DATA_DIR / "image_conversations.json")
