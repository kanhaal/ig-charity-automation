from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
import time
from pathlib import Path

import cloudinary
import cloudinary.uploader
import requests


BUFFER_ENDPOINT = "https://api.buffer.com"


@dataclass(frozen=True)
class PublishResult:
    buffer_post_id: str
    media_url: str


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def _buffer_request(token: str, query: str, variables: dict | None = None) -> dict:
    response = requests.post(
        BUFFER_ENDPOINT,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables or {}},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"Buffer GraphQL error: {payload['errors']}")
    return payload.get("data") or {}


def _normalise_handle(value: str | None) -> str:
    return (value or "").strip().lower().replace("@", "").rstrip("/")


def resolve_instagram_channel_id(token: str, target_handle: str) -> str:
    configured = os.getenv("BUFFER_CHANNEL_ID", "").strip()
    if configured:
        return configured

    org_data = _buffer_request(
        token,
        """
        query GetOrganizations {
          account {
            organizations { id name }
          }
        }
        """,
    )
    organizations = ((org_data.get("account") or {}).get("organizations") or [])
    if not organizations:
        raise RuntimeError("Buffer account has no organization available")

    target = _normalise_handle(target_handle)
    instagram_channels: list[dict] = []
    for org in organizations:
        org_id = str(org.get("id", "")).strip()
        if not org_id:
            continue
        data = _buffer_request(
            token,
            """
            query GetChannels($organizationId: OrganizationId!) {
              channels(input: { organizationId: $organizationId }) {
                id
                name
                displayName
                service
                externalLink
                isDisconnected
                isLocked
                isQueuePaused
              }
            }
            """,
            {"organizationId": org_id},
        )
        for channel in data.get("channels") or []:
            if str(channel.get("service", "")).lower() == "instagram":
                instagram_channels.append(channel)

    usable = [
        channel
        for channel in instagram_channels
        if not channel.get("isDisconnected") and not channel.get("isLocked")
    ]
    if not usable:
        raise RuntimeError(
            "No usable Instagram channel is connected to Buffer. "
            "Connect @kiaraprmd in Buffer first."
        )

    def matches(channel: dict) -> bool:
        names = {
            _normalise_handle(channel.get("name")),
            _normalise_handle(channel.get("displayName")),
        }
        link = _normalise_handle(channel.get("externalLink"))
        return target in names or (target and target in link)

    matched = [channel for channel in usable if matches(channel)]
    if len(matched) == 1:
        return str(matched[0]["id"])
    if not matched and len(usable) == 1:
        return str(usable[0]["id"])

    available = ", ".join(
        str(channel.get("name") or channel.get("displayName") or channel.get("id"))
        for channel in usable
    )
    raise RuntimeError(
        f"Could not uniquely identify @{target_handle} in Buffer. "
        f"Connected Instagram channels: {available}. "
        "Set BUFFER_CHANNEL_ID only if you intentionally need to override auto-detection."
    )


def upload_video(video: Path, slot_id: str) -> str:
    _required("CLOUDINARY_URL")
    cloudinary.config(secure=True)

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


def _post_to_buffer(
    *,
    media_url: str,
    caption: str,
    share_to_feed: bool,
    instagram_handle: str,
) -> str:
    token = _required("BUFFER_API_KEY")
    channel_id = resolve_instagram_channel_id(token, instagram_handle)

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
            data = _buffer_request(token, mutation, variables)
            result = data.get("createPost") or {}
            if result.get("message"):
                raise RuntimeError(f"Buffer rejected the post: {result['message']}")
            post = result.get("post") or {}
            post_id = str(post.get("id", "")).strip()
            if not post_id:
                raise RuntimeError(f"Buffer response did not contain a post id: {data}")
            return post_id
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Buffer publish failed after retries: {last_error}")


def publish_reel(
    *,
    video: Path,
    slot_id: str,
    caption: str,
    share_to_feed: bool,
    instagram_handle: str,
) -> PublishResult:
    media_url = upload_video(video, slot_id)
    post_id = _post_to_buffer(
        media_url=media_url,
        caption=caption,
        share_to_feed=share_to_feed,
        instagram_handle=instagram_handle,
    )
    return PublishResult(buffer_post_id=post_id, media_url=media_url)
