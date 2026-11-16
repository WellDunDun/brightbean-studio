import unittest
from datetime import datetime, timedelta, timezone
from apps.analytics.trial_checkpoints import due, retain


class TrialCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.post = 'fixture-trial-post'
        self.published = datetime(2026, 11, 16, 17, 30, tzinfo=timezone.utc)

    def capture(self, hours, previous=None, raw=None, errors=None):
        return retain(self.post, self.published, raw or {'insights': {'reach': 0}}, previous or {}, self.published + timedelta(hours=hours), errors or {}, tracked=True)

    def test_first_capture_survives_later_daily_updates(self):
        first = self.capture(24)
        later = self.capture(27, first, {'insights': {'reach': 999}})
        self.assertEqual(first['trial_checkpoints']['24h'], later['trial_checkpoints']['24h'])
        both = self.capture(48, later)
        self.assertEqual(set(both['trial_checkpoints']), {'24h', '48h'})
        all_three = self.capture(168, both)
        self.assertEqual(set(all_three['trial_checkpoints']), {'24h', '48h', '7d'})

    def test_before_due_or_missed_windows_are_not_relabelled(self):
        self.assertEqual(self.capture(23)['trial_checkpoints'], {})
        self.assertEqual(self.capture(31)['trial_checkpoints'], {})
        self.assertFalse(due(self.post, self.published, {}, self.published + timedelta(hours=31), tracked=True))

    def test_due_once_and_failed_metrics_do_not_become_zeros(self):
        now = self.published + timedelta(hours=48)
        self.assertTrue(due(self.post, self.published, {}, now, tracked=True))
        captured = self.capture(48, raw={'insights': {'reach': 10, 'ig_reels_avg_watch_time': 0}}, errors={'ig_reels_avg_watch_time': 'unsupported'})
        self.assertEqual(captured['trial_checkpoints']['48h']['counts'], {'reach': 10})
        self.assertFalse(due(self.post, self.published, captured, now, tracked=True))

    def test_other_accounts_and_unpublished_posts_unchanged(self):
        raw = {'insights': {'reach': 3}}
        self.assertEqual(retain('other', self.published, raw, {}, self.published, {}), raw)
        self.assertFalse(due(self.post, None, {}, self.published))
