from unittest.mock import MagicMock, patch

import pytest

from providers.exceptions import PublishError
from providers.instagram_login import InstagramLoginProvider
from providers.instagram_uploads import create_media
from providers.types import PostType, PublishContent


def test_resumable_stream_uses_returned_meta_endpoint(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"video-bytes")
    provider = InstagramLoginProvider({"client_id": "id", "client_secret": "secret"})
    provider._request = MagicMock()
    provider._request.return_value.json.return_value = {
        "id": "123",
        "uri": "https://rupload.facebook.com/ig-api-upload/v25.0/123",
    }
    content = PublishContent(
        post_type=PostType.REEL, media_files=[str(video)], extra={"instagram_options": {"upload_type": "resumable"}}
    )
    with patch("providers.instagram_uploads.httpx.Client") as client:
        response = client.return_value.__enter__.return_value.post

        def uploaded(*args, **kwargs):
            assert b"".join(kwargs["content"]) == b"video-bytes"
            return result

        result = MagicMock(status_code=200)
        result.json.return_value = {"success": True}
        response.side_effect = uploaded
        response.return_value.status_code = 200
        response.return_value.json.return_value = {"success": True}
        assert (
            create_media(
                provider, "test-token", content, {"media_type": "REELS", "video_url": "https://example.org/v.mp4"}
            )
            == "123"
        )
        body = provider._request.call_args.kwargs["json"]
        assert body == {"media_type": "REELS", "upload_type": "resumable"}
        assert response.call_args.kwargs["headers"]["offset"] == "0"
        assert response.call_args.kwargs["headers"]["file_size"] == "11"


@pytest.mark.parametrize(
    "uri",
    [
        "https://evil.example/ig-api-upload/v25.0/123",
        "https://rupload.facebook.com.evil/ig-api-upload/v25.0/123",
        "http://rupload.facebook.com/ig-api-upload/v25.0/123",
        "https://rupload.facebook.com/ig-api-upload/v25.0/456",
    ],
)
def test_untrusted_upload_endpoint_never_receives_token(tmp_path, uri):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"video")
    provider = InstagramLoginProvider({"client_id": "id", "client_secret": "secret"})
    provider._request = MagicMock()
    provider._request.return_value.json.return_value = {"id": "123", "uri": uri}
    content = PublishContent(media_files=[str(video)], extra={"instagram_options": {"upload_type": "resumable"}})
    with patch("providers.instagram_uploads.httpx.Client") as client, pytest.raises(PublishError) as exc:
        create_media(provider, "token", content, {"video_url": "https://example.org/v.mp4"})
    assert exc.value.retryable is False
    client.assert_not_called()
