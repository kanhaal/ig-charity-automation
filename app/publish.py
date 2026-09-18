from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
import time
from pathlib import Path

import cloudinary
import cloudinary.uploader
import requests


@dataclass(frozen=True)
class PublishResult:
    buffer_post_id: str
    media_url: str


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def upload_video(video: Path, slot_id: str) -> str:
    cloudinary.config(
        cloud_name=_required("CLOUDINARY_CLOUD_NAME"),
        api_key=_required("CLOUDINARY_API_KEY"),
        api_secret=_required("CLOUDINARY_API_SECRET"),
        secure=True,
    )

    last_error: Exception | None = None
    for delay in (0, 5, 15, 30, 60):
        if delay:
            time.sleep(delay)
        try:
            result = cloudinary.uploader.upload_large(
                str(video),
                resource_type="video",
                folder="ig-charity-automation",
                public_id=slot_id,
                overwrite=True,
                invalidate=True,
            )
            url = str(result.get("secure_url", "")).strip()
            if not url.startswith("https://"):
                raise RuntimeError("Cloudinary did not return a public HTTPS media URL")
            return url
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Cloudinary upload failed after retries: {last_error}")


def _post_to_buffer(*, media_url: str, caption: str, share_to_feed: bool) -> str:
    token = _required("BUFFER_API_KEY")
    channel_id = _required("BUFFER_CHANNEL_ID")

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post { id text dueAt }
        }
        ... on MutationError { message }
      }
    }
    """
    due_at = (datetime.now(timezone.utc) + timedelta(minutes=8)).isoformat().replace("+00:00", "Z")
    variables = {
        "input": {
            "text": caption,
            "channelId": channel_id,
            "schedulingType": "automatic",
            "mode": "customScheduled",
            "dueAt": due_at,
            "needsApproval": False,
            "saveToDraft": False,
            "aiAssisted": False,
            "assets": [
                {
                    "video": {
                        "url": media_url,
                        "metadata": {"thumbnailOffset": 1200},
                    }
                }
            ],
            "metadata": {
                "instagram": {
                    "type": "reel",
                    "shouldShareToFeed": bool(share_to_feed),
                    "isAiGenerated": False,
                }
            },
        }
    }

    last_error: Exception | None = None
    for delay in (0, 8, 20, 45, 90):
        if delay:
            time.sleep(delay)
        try:
            response = requests.post(
                "https://api.buffer.com",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"query": mutation, "variables": variables},
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("errors"):
                raise RuntimeError(f"Buffer GraphQL error: {payload['errors']}")
            result = (payload.get("data") or {}).get("createPost") or {}
            if result.get("message"):
                raise RuntimeError(f"Buffer rejected the post: {result['message']}")
            post = result.get("post") or {}
            post_id = str(post.get("id", "")).strip()
            if not post_id:
                raise RuntimeError(f"Buffer response did not contain a post id: {payload}")
            return post_id
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Buffer publish failed after retries: {last_error}")


def publish_reel(*, video: Path, slot_id: str, caption: str, share_to_feed: bool) -> PublishResult:
    media_url = upload_video(video, slot_id)
    post_id = _post_to_buffer(
        media_url=media_url,
        caption=caption,
        share_to_feed=share_to_feed,
    )
    return PublishResult(buffer_post_id=post_id, media_url=media_url)
