from unittest.mock import patch

import httpx
import pytest

from apps.social_accounts.error_messages import friendly_publish_error
from providers.exceptions import APIError, PublishError
from providers.instagram import InstagramProvider
from providers.instagram_login import InstagramLoginProvider


@pytest.mark.parametrize("provider", [InstagramProvider, InstagramLoginProvider])
def test_trial_follower_rejection_is_permanent_and_actionable(provider):
    raw = {"error": {"code": 10, "error_subcode": 2207081,
                     "error_user_msg": "private provider detail", "fbtrace_id": "private-trace"}}
    response = httpx.Response(400, json=raw)
    with patch("providers.base.httpx.Client") as client:
        client.return_value.__enter__.return_value.request.return_value = response
        with pytest.raises(PublishError) as caught:
            provider()._request("POST", "https://example.com/media", json={"trial_params": {"graduation_strategy": "MANUAL"}})
        client.return_value.__enter__.return_value.request.assert_called_once()
    assert caught.value.retryable is False
    assert caught.value.raw_response == raw
    message = friendly_publish_error(caught.value)
    assert "follower requirement" in message
    assert "No automatic retry or ordinary-Reel fallback" in message
    assert "private" not in message


@pytest.mark.parametrize("raw", [{"error": {"code": 10, "error_subcode": 999}},
                                 {"error": {"code": 2, "is_transient": True}},
                                 {"error": "invalid"}, []])
def test_other_errors_keep_existing_behavior(raw):
    with patch("providers.base.httpx.Client") as client:
        client.return_value.__enter__.return_value.request.return_value = httpx.Response(400, json=raw)
        with pytest.raises(APIError) as caught:
            InstagramProvider()._request("POST", "https://example.com/media")
    assert caught.value.retryable is True


def test_resumable_preserves_permanent_eligibility_error(tmp_path):
    from unittest.mock import MagicMock
    from providers.instagram_uploads import create_media
    from providers.types import PublishContent, PostType
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    error = PublishError("Trial follower requirement not met.", retryable=False)
    provider = MagicMock()
    provider._request.side_effect = error
    content = PublishContent(post_type=PostType.REEL, media_urls=["https://example.com/video.mp4"],
                             media_files=[str(video)], extra={"instagram_options": {"upload_type": "resumable"}})
    with pytest.raises(PublishError) as caught:
        create_media(provider, "mock-token", content, {"video_url": content.media_urls[0]}, ig_user_id="123")
    assert caught.value is error
    provider._request.assert_called_once()
