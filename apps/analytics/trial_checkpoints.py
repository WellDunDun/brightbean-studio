"""Read-only metric checkpoints for the three owner-selected Trial Reels."""
WINDOWS = (("24h", 86400, 21600), ("48h", 172800, 21600), ("7d", 604800, 86400))


def due(post_id, published_at, previous, now, *, tracked=False):
    if not tracked or not published_at:
        return False
    age = (now - published_at).total_seconds()
    saved = (previous or {}).get("trial_checkpoints", {})
    return any(target <= age <= target + tolerance and label not in saved
               for label, target, tolerance in WINDOWS)


def retain(post_id, published_at, raw, previous, now, errors, *, tracked=False):
    result = dict(raw or {})
    if not tracked or not published_at:
        return result
    saved = dict((previous or {}).get("trial_checkpoints", {}))
    age = (now - published_at).total_seconds()
    values, fields = result.get("insights", {}), result.get("fields", {})
    counts = {k: v for k, v in values.items() if k not in (errors or {})
              and type(v) in (int, float) and v >= 0}
    for source, target in (("like_count", "likes"), ("comments_count", "comments")):
        if target not in counts and type(fields.get(source)) is int and fields[source] >= 0:
            counts[target] = fields[source]
    if counts:
        for label, target, tolerance in WINDOWS:
            if target <= age <= target + tolerance and label not in saved:
                saved[label] = {"captured_at": now.isoformat(), "age_seconds": int(age),
                                "counts": counts, "source": "Meta authenticated media insights"}
    result["trial_checkpoints"] = saved
    return result


def is_tracked(post):
    from apps.settings_manager.models import WorkspaceSetting
    setting = WorkspaceSetting.objects.filter(workspace_id=post.post.workspace_id,
        key="fieldnotes.trial_checkpoint_posts").first()
    return bool(setting and isinstance(setting.value, list) and str(post.pk) in setting.value)
