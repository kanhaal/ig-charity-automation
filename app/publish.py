from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import time
from urllib.parse import unquote, urlparse

import requests


BUFFER_ENDPOINT = "https://api.buffer.com"


@dataclass(frozen=True)
class PublishResult:
    buffer_post_id: str
    media_url: str


@dataclass(frozen=True)
class BufferTarget:
    organization_id: str
    channel_id: str


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


def resolve_instagram_target(token: str, target_handle: str) -> BufferTarget:
    configured = os.getenv("BUFFER_CHANNEL_ID", "").strip()

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
    instagram_channels: list[tuple[str, dict]] = []

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
                instagram_channels.append((org_id, channel))

    usable = [
        (org_id, channel)
        for org_id, channel in instagram_channels
        if not channel.get("isDisconnected") and not channel.get("isLocked")
    ]
    if not usable:
        raise RuntimeError(
            "No usable Instagram channel is connected to Buffer. "
            f"Connect @{target_handle} in Buffer first."
        )

    if configured:
        for org_id, channel in usable:
            if str(channel.get("id", "")).strip() == configured:
                return BufferTarget(org_id, configured)
        raise RuntimeError(
            "BUFFER_CHANNEL_ID is set but does not match a usable connected "
            "Instagram channel."
        )

    def matches(channel: dict) -> bool:
        names = {
            _normalise_handle(channel.get("name")),
            _normalise_handle(channel.get("displayName")),
        }
        link = _normalise_handle(channel.get("externalLink"))
        return target in names or (target and target in link)

    matched = [
        (org_id, channel)
        for org_id, channel in usable
        if matches(channel)
    ]

    if len(matched) == 1:
        org_id, channel = matched[0]
        return BufferTarget(org_id, str(channel["id"]))

    if not matched and len(usable) == 1:
        org_id, channel = usable[0]
        return BufferTarget(org_id, str(channel["id"]))

    available = ", ".join(
        str(channel.get("name") or channel.get("displayName") or channel.get("id"))
        for _, channel in usable
    )
    raise RuntimeError(
        f"Could not uniquely identify @{target_handle} in Buffer. "
        f"Connected Instagram channels: {available}. "
        "Set BUFFER_CHANNEL_ID only if you intentionally need to override auto-detection."
    )


def resolve_instagram_channel_id(token: str, target_handle: str) -> str:
    return resolve_instagram_target(token, target_handle).channel_id


def _slot_matches_asset_url(source: str, slot_id: str) -> bool:
    if not source:
        return False
    try:
        path = unquote(urlparse(source).path)
    except ValueError:
        return False
    filename = path.rsplit("/", 1)[-1]
    return filename == f"{slot_id}.mp4"


def _find_existing_post_id(
    token: str,
    target: BufferTarget,
    slot_id: str,
) -> str | None:
    query = """
    query RecentPosts($input: PostsInput!) {
      posts(
        first: 30
        input: $input
      ) {
        edges {
          node {
            id
            status
            assets {
              source
            }
          }
        }
      }
    }
    """
    variables = {
        "input": {
            "organizationId": target.organization_id,
            "filter": {
                "channelIds": [target.channel_id],
                "status": ["scheduled", "sending", "sent"],
            },
            "sort": [{"field": "createdAt", "direction": "desc"}],
        }
    }
    data = _buffer_request(token, query, variables)

    for edge in ((data.get("posts") or {}).get("edges") or []):
        node = edge.get("node") or {}
        for asset in node.get("assets") or []:
            if _slot_matches_asset_url(str(asset.get("source", "")), slot_id):
                post_id = str(node.get("id", "")).strip()
                if post_id:
                    return post_id

    return None


def _normalise_cloudinary_url(raw: str) -> str:
    value = raw.strip()
    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {"\"", "'"}
    ):
        value = value[1:-1].strip()

    # Cloudinary's dashboard often presents this as a shell assignment:
    # CLOUDINARY_URL=cloudinary://....
    # GitHub Secrets should ideally contain only the value, but accepting the
    # full assignment makes setup much less error-prone.
    if value.startswith("CLOUDINARY_URL="):
        value = value.split("=", 1)[1].strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"\"", "'"}
        ):
            value = value[1:-1].strip()

    if not value.startswith("cloudinary://"):
        raise RuntimeError(
            "CLOUDINARY_URL is invalid. It must contain a value beginning "
            "with 'cloudinary://'. You may paste either that value directly "
            "or the full CLOUDINARY_URL=cloudinary://... assignment."
        )

    return value


def upload_video(video: Path, slot_id: str) -> str:
    # Sanitize before importing Cloudinary: its SDK reads CLOUDINARY_URL at
    # import time, so an accidentally pasted 'CLOUDINARY_URL=...' assignment
    # would otherwise crash before we could correct it.
    os.environ["CLOUDINARY_URL"] = _normalise_cloudinary_url(
        _required("CLOUDINARY_URL")
    )

    import cloudinary
    import cloudinary.uploader

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
    slot_id: str,
) -> str:
    token = _required("BUFFER_API_KEY")
    target = resolve_instagram_target(token, instagram_handle)

    existing = _find_existing_post_id(token, target, slot_id)
    if existing:
        return existing

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

    due_at = (
        datetime.now(timezone.utc) + timedelta(minutes=8)
    ).isoformat().replace("+00:00", "Z")

    variables = {
        "input": {
            "text": caption,
            "channelId": target.channel_id,
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

    # Creation itself is not blindly retried. After a transport failure we first
    # query Buffer for this exact slot's Cloudinary filename, preventing a lost
    # HTTP response from creating duplicate Reels on the next attempt.
    for delay in (0, 8, 20, 45):
        if delay:
            time.sleep(delay)

        try:
            data = _buffer_request(token, mutation, variables)
        except requests.RequestException as exc:
            last_error = exc
            try:
                existing = _find_existing_post_id(token, target, slot_id)
            except Exception:
                existing = None
            if existing:
                return existing
            continue

        result = data.get("createPost") or {}
        if result.get("message"):
            raise RuntimeError(f"Buffer rejected the post: {result['message']}")

        post = result.get("post") or {}
        post_id = str(post.get("id", "")).strip()
        if not post_id:
            raise RuntimeError(
                f"Buffer response did not contain a post id: {data}"
            )

        return post_id

    try:
        existing = _find_existing_post_id(token, target, slot_id)
    except Exception:
        existing = None
    if existing:
        return existing

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
        slot_id=slot_id,
    )
    return PublishResult(
        buffer_post_id=post_id,
        media_url=media_url,
    )
