"""Stream explicitly selected video uploads without exposing access tokens or retrying uncertain uploads."""

import os
from urllib.parse import urlparse

import httpx

from .exceptions import PublishError


def create_media(provider, token, content, payload, index=0, ig_user_id=None):
    if content.extra.get("instagram_options", {}).get("upload_type") != "resumable" or "video_url" not in payload:
        if ig_user_id is not None:
            return provider._create_container(token, ig_user_id, payload)
        return provider._create_container(token, payload)
    if index >= len(content.media_files):
        raise PublishError("Resumable upload requires the registered local video file.", retryable=False)
    filename = content.media_files[index]
    size = os.path.getsize(filename)
    if not 0 < size <= 300_000_000:
        raise PublishError("Video exceeds the configured 300 MB upload limit.", retryable=False)
    body = {key: value for key, value in payload.items() if key != "video_url"}
    body["upload_type"] = "resumable"
    from .instagram import BASE_URL
    from .instagram_login import API_BASE

    endpoint = f"{BASE_URL}/{ig_user_id}/media" if ig_user_id is not None else f"{API_BASE}/me/media"
    try:
        data = provider._request("POST", endpoint, access_token=token, json=body).json()
        identifier, uri = data.get("id"), data.get("uri")
        parsed = urlparse(uri) if isinstance(uri, str) else None
        if (
            not isinstance(identifier, str)
            or not identifier.isdigit()
            or not parsed
            or parsed.scheme != "https"
            or parsed.hostname != "rupload.facebook.com"
            or parsed.port not in (None, 443)
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/ig-api-upload/")
            or not parsed.path.endswith("/" + identifier)
        ):
            raise ValueError("Unexpected Meta upload endpoint.")
        with open(filename, "rb") as source, httpx.Client(timeout=300, follow_redirects=False) as client:
            response = client.post(
                uri,
                headers={
                    "Authorization": f"OAuth {token}",
                    "offset": "0",
                    "file_size": str(size),
                    "Content-Length": str(size),
                    "Content-Type": "application/octet-stream",
                },
                content=iter(lambda: source.read(1024 * 1024), b""),
            )
            if response.status_code != 200 or response.json().get("success") is not True:
                raise ValueError("Meta did not confirm the video upload.")
        return identifier
    except PublishError:
        raise
    except Exception as exc:
        # Container or upload may exist. Do not let the background runner create another one automatically.
        raise PublishError(
            "Video upload outcome needs reconciliation; no automatic replay.",
            platform=provider.platform_name,
            retryable=False,
        ) from exc
