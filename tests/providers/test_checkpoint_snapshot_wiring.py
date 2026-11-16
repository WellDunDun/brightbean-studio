import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from apps.analytics.tasks import _write_account_snapshot, _write_post_snapshot


class SnapshotWiringTests(unittest.TestCase):
    def test_account_snapshot_never_runs_post_checkpoint_logic(self):
        with patch("apps.analytics.models.AccountInsightsSnapshot.objects") as rows, \
             patch("apps.analytics.trial_checkpoints.is_tracked", side_effect=AssertionError("post-only check")):
            count = _write_account_snapshot(object(), {"reach": 10}, datetime.now().date())
        self.assertEqual(count, 1)
        rows.update_or_create.assert_called_once()

    def test_post_writer_preserves_previous_checkpoint_in_the_actual_write(self):
        published = datetime(2026, 11, 16, 19, 15, tzinfo=timezone.utc)
        previous = {"trial_checkpoints": {"24h": {"captured_at": "first", "counts": {"reach": 1}}}}
        post = type("PostFixture", (), {"objects": MagicMock()})()
        post.pk = "fixture"
        post.published_at = published
        with patch("apps.analytics.models.PostInsightsSnapshot.objects") as rows, \
             patch("apps.analytics.trial_checkpoints.is_tracked", return_value=True), \
             patch("apps.analytics.tasks.timezone.now", return_value=published + timedelta(hours=48)):
            rows.filter.return_value.order_by.return_value.first.return_value = SimpleNamespace(raw=previous)
            count = _write_post_snapshot.__wrapped__(post, {"reach": 10}, published.date(),
                    raw={"insights": {"reach": 10}})
        self.assertEqual(count, 1)
        saved = rows.update_or_create.call_args.kwargs["defaults"]["raw"]["trial_checkpoints"]
        self.assertEqual(saved["24h"], previous["trial_checkpoints"]["24h"])
        self.assertEqual(saved["48h"]["counts"]["reach"], 10)
        post.objects.select_for_update.return_value.get.assert_called_once_with(pk="fixture")

    def test_explicit_instagram_zero_is_retained_but_missing_watch_is_unknown(self):
        from apps.analytics.tasks import _post_metrics_to_dict
        from providers.types import PostMetrics
        result = _post_metrics_to_dict(PostMetrics(extra={"raw_insights": {"views": 0, "reach": 0},
                     "insight_errors": {"profile_visits": "unsupported"}}), "instagram")
        self.assertEqual(result["views"], 0)
        self.assertEqual(result["reach"], 0)
        self.assertNotIn("avg_watch_ms", result)
        self.assertNotIn("profile_visits", result)
