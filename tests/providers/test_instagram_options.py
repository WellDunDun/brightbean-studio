from unittest.mock import MagicMock

import pytest

from providers.exceptions import PublishError
from providers.instagram import InstagramProvider
from providers.instagram_login import InstagramLoginProvider
from providers.instagram_options import validate
from providers.types import PostType, PublishContent


@pytest.mark.parametrize("cls", [InstagramProvider, InstagramLoginProvider])
def test_reel_options_reach_meta(cls):
    provider = cls({"client_id": "test", "client_secret": "test"})
    provider._get_ig_user_id = MagicMock(return_value="123")
    provider._create_container = MagicMock(return_value="456")
    provider._wait_for_container = MagicMock()
    provider._publish_container = MagicMock(return_value="published")
    options = {
        "share_to_feed": False,
        "thumb_offset": 1200,
        "audio_name": "Demo",
        "collaborators": ["danielpetro.dev"],
        "is_ai_generated": True,
    }
    provider.publish_post(
        "token",
        PublishContent(
            post_type=PostType.REEL, media_urls=["https://example.org/demo.mp4"], extra={"instagram_options": options}
        ),
    )
    payload = provider._create_container.call_args.args[-1]
    assert all(payload[key] == value for key, value in options.items())


@pytest.mark.parametrize("cls", [InstagramProvider, InstagramLoginProvider])
def test_mixed_carousel_uses_registered_types_and_image_alt(cls):
    provider = cls({"client_id": "test", "client_secret": "test"})
    provider._get_ig_user_id = MagicMock(return_value="123")
    provider._create_container = MagicMock(return_value="456")
    provider._wait_for_container = MagicMock()
    provider._publish_container = MagicMock(return_value="published")
    provider.publish_post(
        "token",
        PublishContent(
            post_type=PostType.CAROUSEL,
            media_urls=["https://example.org/one?signed=1", "https://example.org/two?signed=1"],
            extra={
                "_instagram_media_types": ["image", "video"],
                "instagram_options": {"is_ai_generated": True, "media_options": [{"alt_text": "A real diagram"}, {}]},
            },
        ),
    )
    payloads = [call.args[-1] for call in provider._create_container.call_args_list]
    assert payloads[0]["alt_text"] == "A real diagram"
    assert "is_ai_generated" not in payloads[0]
    assert payloads[1]["media_type"] == "VIDEO"
    assert payloads[2]["is_ai_generated"] is True
    assert "alt_text" not in payloads[2]


@pytest.mark.parametrize(
    "option",
    [
        {"unknown": True},
        {"share_to_feed": "false"},
        {"thumb_offset": -1},
        {"thumb_offset": True},
        {"cover_url": "http://localhost/a.jpg"},
        {"cover_url": "https://example.org/c.jpg", "thumb_offset": 0},
        {"collaborators": ["one", "two", "three", "four"]},
        {"is_poll_duration_extended": True},
        {"media_options": [{"alt_text": "not video alt"}]},
        {"user_tags": []},
        {"location_id": "123"},
        {"is_paid_partnership": True},
        {"branded_content_sponsor_ids": ["123"]},
        {"is_comment_prompt_used": True},
        {"poll_attachment": {"option_a": "one", "option_b": "two"}},
    ],
)
def test_invalid_or_unavailable_options_fail_before_network(option):
    provider = InstagramLoginProvider({"client_id": "test", "client_secret": "test"})
    provider._create_container = MagicMock()
    with pytest.raises(PublishError) as error:
        provider.publish_post(
            "token",
            PublishContent(
                post_type=PostType.REEL, media_urls=["https://example.org/a.mp4"], extra={"instagram_options": option}
            ),
        )
    assert error.value.retryable is False
    provider._create_container.assert_not_called()


def test_facebook_only_capabilities_validate_complete_payload():
    options = {
        "location_id": "123",
        "is_paid_partnership": True,
        "branded_content_sponsor_ids": ["123", "456"],
        "poll_attachment": {"option_a": "Yes", "option_b": "No"},
        "is_poll_duration_extended": True,
        "media_options": [
            {
                "alt_text": "diagram",
                "user_tags": [{"username": "danielpetro.dev", "x": 0.4, "y": 0.5}],
                "product_tags": [{"product_id": "123", "x": 0.4, "y": 0.5}],
            }
        ],
    }
    assert validate(options, ["image"], "image", connection="instagram", caption="Question") == options


def test_twenty_item_carousel_and_invalid_count():
    validate({}, ["image"] * 20, "carousel")
    with pytest.raises(ValueError):
        validate({}, ["image"] * 21, "carousel")


def test_story_never_silently_discards_caption():
    with pytest.raises(ValueError):
        validate({}, ["video"], "story", connection="instagram", caption="not sent")
    validate({}, ["video"], "story", connection="instagram")


def test_story_engine_empty_media_metadata_is_allowed_on_facebook():
    validate({"media_options": [{}], "upload_type": "resumable"}, ["video"], "story", connection="instagram")


def test_single_reel_tags_are_not_lost():
    from providers.instagram_options import container_options

    content = PublishContent(
        post_type=PostType.REEL,
        media_urls=["https://example.org/v.mp4"],
        extra={"instagram_options": {"media_options": [{"user_tags": [{"username": "creator"}]}]}},
    )
    assert container_options(content, "instagram")["user_tags"] == [{"username": "creator"}]
