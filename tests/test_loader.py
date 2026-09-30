import tempfile
import unittest
from pathlib import Path

from explorer.loader import DatasetNotFound, load_dataset, short_scene

FIXTURES = Path(__file__).parent / "fixtures"


class LoaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = load_dataset(FIXTURES)

    def test_loads_both_splits(self):
        self.assertEqual(len(self.ds.videos), 5)
        self.assertEqual(self.ds.stats()["splits"], {"train": 3, "test": 2})

    def test_parses_fields(self):
        v = self.ds.by_id["AAA01"]
        self.assertEqual(v.scene, "Kitchen")
        self.assertEqual(v.quality, 6)
        self.assertTrue(v.verified)
        self.assertEqual(v.length, 12.4)
        self.assertEqual(v.objects, ["cup", "table"])
        self.assertEqual(len(v.descriptions), 2)
        # Quoted field containing a comma survives CSV parsing.
        self.assertEqual(v.script, "A person takes a cup, then drinks from it.")

    def test_parses_action_triplets_with_class_names(self):
        actions = self.ds.by_id["AAA01"].actions
        self.assertEqual([(a.code, a.name, a.start, a.end) for a in actions], [
            ("c002", "Taking a cup from somewhere", 0.0, 4.5),
            ("c003", "Drinking from a cup", 3.0, 12.0),
        ])

    def test_blank_values_become_none(self):
        v = self.ds.by_id["AAA02"]
        self.assertIsNone(v.quality)
        self.assertFalse(v.verified)

    def test_unknown_class_falls_back_to_code(self):
        names = [a.name for a in self.ds.by_id["AAA02"].actions]
        self.assertEqual(names, ["Opening a door", "c999"])

    def test_video_without_actions(self):
        v = self.ds.by_id["BBB01"]
        self.assertEqual(v.actions, [])
        self.assertEqual(v.summary_dict()["num_actions"], 0)

    def test_malformed_action_is_skipped_with_warning(self):
        v = self.ds.by_id["BBB02"]
        self.assertEqual([a.code for a in v.actions], ["c001", "c003"])
        self.assertTrue(any("BBB02" in w for w in self.ds.warnings))

    def test_short_scene_strips_explanation(self):
        self.assertEqual(self.ds.by_id["AAA02"].scene_short, "Entryway")
        self.assertEqual(short_scene("Closet / Walk-in closet / Spear closet"),
                         "Closet / Walk-in closet / Spear closet")

    def test_search_text_includes_labels(self):
        text = self.ds.by_id["AAA01"].search_text
        for needle in ("drinking from a cup", "c003", "table", "kitchen", "coffee"):
            self.assertIn(needle, text)

    def test_missing_data_dir_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DatasetNotFound):
                load_dataset(Path(tmp))


if __name__ == "__main__":
    unittest.main()
