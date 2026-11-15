"""Validated Instagram container options. No arbitrary Graph API forwarding."""

import json
import re
from urllib.parse import urlparse

FACEBOOK_ONLY = frozenset(
    {
        "user_tags",
        "product_tags",
        "location_id",
        "is_paid_partnership",
        "poll_attachment",
        "is_poll_duration_extended",
        "is_comment_prompt_used",
        "branded_content_sponsor_ids",
    }
)
PARENT = frozenset(
    {
        "share_to_feed",
        "thumb_offset",
        "cover_url",
        "collaborators",
        "location_id",
        "audio_name",
        "is_ai_generated",
        "is_paid_partnership",
        "poll_attachment",
        "is_poll_duration_extended",
        "is_comment_prompt_used",
        "branded_content_sponsor_ids",
    }
)
CHILD = frozenset({"alt_text", "user_tags", "product_tags"})
REEL_ONLY = frozenset({"share_to_feed", "thumb_offset", "cover_url", "audio_name"})
BOOLS = frozenset(
    {"share_to_feed", "is_ai_generated", "is_paid_partnership", "is_poll_duration_extended", "is_comment_prompt_used"}
)


def validate(options, media_types, post_type, *, connection="instagram_login", caption=""):
    if not isinstance(options, dict) or set(options) - (PARENT | {"media_options", "upload_type"}):
        raise ValueError("Unknown Instagram publishing option.")
    if not media_types or any(t not in ("image", "video") for t in media_types):
        raise ValueError("Instagram requires registered image or video media.")
    if post_type not in ("image", "reel", "story", "carousel"):
        raise ValueError("Unknown Instagram format.")
    if post_type == "carousel":
        if not 2 <= len(media_types) <= 20:
            raise ValueError("A carousel requires 2 to 20 media items.")
    elif (
        len(media_types) != 1
        or (post_type == "reel" and media_types != ["video"])
        or (post_type == "image" and media_types != ["image"])
    ):
        raise ValueError("The selected format does not match the registered media.")
    if len(caption) > 2200:
        raise ValueError("Instagram captions cannot exceed 2200 characters.")
    if post_type == "story":
        if connection == "instagram_login":
            raise ValueError("Stories are not enabled on this Instagram Login connection; verify eligibility first.")
        if caption or set(options) - {"media_options", "upload_type"} or any(options.get("media_options", [])):
            raise ValueError("Stories require an empty API caption and no feed options.")
    for key, value in options.items():
        if key in FACEBOOK_ONLY and connection != "instagram":
            raise ValueError(f"{key} requires Facebook Login and applicable Meta permissions.")
        if key in REEL_ONLY and post_type != "reel":
            raise ValueError(f"{key} is only supported for Reels.")
        if key in BOOLS and type(value) is not bool:
            raise ValueError(f"{key} must be a boolean.")
    if "thumb_offset" in options and (type(options["thumb_offset"]) is not int or options["thumb_offset"] < 0):
        raise ValueError("thumb_offset must be a nonnegative number of milliseconds.")
    if "cover_url" in options:
        parsed = urlparse(options["cover_url"]) if isinstance(options["cover_url"], str) else None
        if not parsed or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("A Reel cover must have a public HTTPS image URL.")
        if "thumb_offset" in options:
            raise ValueError("Choose a custom cover or a video-frame offset, not both.")
    if "audio_name" in options and (
        not isinstance(options["audio_name"], str) or not 1 <= len(options["audio_name"]) <= 255
    ):
        raise ValueError("Original audio name must contain 1 to 255 characters.")
    if "location_id" in options and not re.fullmatch(r"[0-9]+", str(options["location_id"])):
        raise ValueError("Location must be a Facebook location Page ID.")
    for key, maximum in [("collaborators", 3), ("branded_content_sponsor_ids", 2)]:
        if key in options:
            values = options[key]
            if (
                not isinstance(values, list)
                or not 1 <= len(values) <= maximum
                or len(set(map(str, values))) != len(values)
            ):
                raise ValueError(f"{key} requires 1 to {maximum} distinct identifiers.")
            pattern = r"[A-Za-z0-9_.]{1,30}" if key == "collaborators" else r"[0-9]+"
            if any(not isinstance(v, str) or not re.fullmatch(pattern, v) for v in values):
                raise ValueError(f"Invalid {key} identifier.")
    poll = options.get("poll_attachment")
    if poll is not None:
        if (
            not isinstance(poll, dict)
            or set(poll) - {"option_a", "option_b", "option_c", "option_d"}
            or not {"option_a", "option_b"} <= set(poll)
        ):
            raise ValueError("Poll needs option_a and option_b, with optional option_c and option_d.")
        if (
            any(not isinstance(v, str) or not 1 <= len(v) <= 25 for v in poll.values())
            or len(json.dumps(poll).encode()) > 200
            or ("option_d" in poll and "option_c" not in poll)
        ):
            raise ValueError("Invalid poll options or poll size.")
        if not caption or options.get("is_comment_prompt_used"):
            raise ValueError("A poll needs a caption and cannot also be a comment prompt.")
    if "is_poll_duration_extended" in options and poll is None:
        raise ValueError("Extended poll duration requires a poll.")
    if options.get("is_comment_prompt_used") and not caption:
        raise ValueError("A comment prompt requires a caption.")
    if "upload_type" in options and options["upload_type"] not in ("resumable", "url"):
        raise ValueError("Unknown video upload method.")
    if options.get("upload_type") == "resumable" and "video" not in media_types:
        raise ValueError("Resumable upload requires video.")
    children = options.get("media_options", [{} for _ in media_types])
    if not isinstance(children, list) or len(children) != len(media_types):
        raise ValueError("Media options must match the exact media order.")
    for child, kind in zip(children, media_types, strict=True):
        if not isinstance(child, dict) or set(child) - CHILD:
            raise ValueError("Unknown per-media option.")
        for key in child:
            if key in FACEBOOK_ONLY and connection != "instagram":
                raise ValueError(f"{key} requires Facebook Login and applicable Meta permissions.")
        if "alt_text" in child and (
            kind != "image" or not isinstance(child["alt_text"], str) or len(child["alt_text"]) > 1000
        ):
            raise ValueError("Alt text supports images only, up to 1000 characters.")
        for key, identifier in [("user_tags", "username"), ("product_tags", "product_id")]:
            if key not in child:
                continue
            tags = child[key]
            if not isinstance(tags, list) or not 1 <= len(tags) <= 20:
                raise ValueError(f"{key} requires 1 to 20 tags.")
            for tag in tags:
                allowed = {identifier, "x", "y"}
                if not isinstance(tag, dict) or set(tag) - allowed or not isinstance(tag.get(identifier), str):
                    raise ValueError(f"Invalid {key} tag.")
                pattern = r"[A-Za-z0-9_.]{1,30}" if identifier == "username" else r"[0-9]+"
                if not re.fullmatch(pattern, tag[identifier]):
                    raise ValueError(f"Invalid {key} identifier.")
                if kind == "image" and not {"x", "y"} <= set(tag):
                    raise ValueError("Image tags need x and y coordinates.")
                if kind == "video" and ("x" in tag or "y" in tag):
                    raise ValueError("Video tags cannot have image coordinates.")
                if any(type(tag[k]) not in (int, float) or not 0 <= tag[k] <= 1 for k in ("x", "y") if k in tag):
                    raise ValueError("Tag coordinates must be between 0 and 1.")
    return json.loads(json.dumps(options, allow_nan=False))


def media_types(content):
    if "_instagram_media_types" in content.extra:
        return content.extra["_instagram_media_types"]
    return ["video" if urlparse(url).path.lower().endswith((".mp4", ".mov")) else "image" for url in content.media_urls]


def container_options(content, connection, *, index=None):
    kinds = media_types(content)
    post_type = content.post_type.value
    if post_type not in ("image", "reel", "story", "carousel"):
        post_type = "carousel" if len(kinds) > 1 else ("reel" if kinds == ["video"] else "image")
    options = validate(
        content.extra.get("instagram_options", {}), kinds, post_type, connection=connection, caption=content.text
    )
    if (
        "thumb_offset" in options
        and content.video_duration_sec
        and options["thumb_offset"] >= content.video_duration_sec * 1000
    ):
        raise ValueError("Cover frame must be before the end of the video.")
    if index is not None:
        return options.get("media_options", [{} for _ in kinds])[index].copy()
    result = {k: v for k, v in options.items() if k in PARENT}
    if post_type in ("image", "reel"):
        result.update(options.get("media_options", [{}])[0])
    return result
