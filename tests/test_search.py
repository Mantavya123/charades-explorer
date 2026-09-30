import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from explorer.loader import load_dataset
from explorer.search import Filters, facets, parse_terms, search
from explorer.server import make_handler

FIXTURES = Path(__file__).parent / "fixtures"


def ids(results):
    return [v.id for v in results]


class SearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = load_dataset(FIXTURES)
        cls.videos = cls.ds.videos

    def run_search(self, **kwargs):
        sort = kwargs.pop("sort", "id")
        return search(self.videos, Filters(**kwargs), sort=sort, limit=100)

    def test_no_filters_returns_everything(self):
        total, results = self.run_search()
        self.assertEqual(total, 5)
        self.assertEqual(ids(results), ["AAA01", "AAA02", "AAA03", "BBB01", "BBB02"])

    def test_keyword_is_case_insensitive_and_matches_action_names(self):
        _, results = self.run_search(q="DRINKING")
        self.assertEqual(ids(results), ["AAA01", "BBB02"])

    def test_all_terms_must_match(self):
        _, results = self.run_search(q="clothes kitchen")
        self.assertEqual(ids(results), ["BBB02"])

    def test_quoted_phrase(self):
        self.assertEqual(parse_terms('"opening a door" fast'), ["opening a door", "fast"])
        _, results = self.run_search(q='"opening a door"')
        self.assertEqual(ids(results), ["AAA02"])

    def test_scene_uses_short_name(self):
        _, results = self.run_search(scene="entryway")
        self.assertEqual(ids(results), ["AAA02"])

    def test_action_code(self):
        _, results = self.run_search(action="c001")
        self.assertEqual(ids(results), ["AAA03", "BBB02"])

    def test_object_split_and_verified(self):
        self.assertEqual(ids(self.run_search(object="Cup")[1]), ["AAA01", "BBB02"])
        self.assertEqual(ids(self.run_search(split="test")[1]), ["BBB01", "BBB02"])
        self.assertNotIn("AAA02", ids(self.run_search(verified=True)[1]))

    def test_length_range(self):
        _, results = self.run_search(min_length=10, max_length=20)
        self.assertEqual(ids(results), ["AAA01", "AAA03", "BBB01"])

    def test_sort_and_pagination(self):
        total, page = search(self.videos, Filters(), sort="longest", limit=2, offset=1)
        self.assertEqual(total, 5)
        self.assertEqual(ids(page), ["AAA03", "BBB01"])

    def test_bad_sort_raises(self):
        with self.assertRaises(ValueError):
            search(self.videos, Filters(), sort="nope")

    def test_from_params_validates_numbers(self):
        f = Filters.from_params({"min_length": "5", "verified": "1", "action": "C001"})
        self.assertEqual((f.min_length, f.verified, f.action), (5.0, True, "c001"))
        with self.assertRaises(ValueError):
            Filters.from_params({"max_length": "ten"})

    def test_facets_count_videos(self):
        fc = facets(self.videos, self.ds.classes)
        kitchen = next(s for s in fc["scenes"] if s["name"] == "Kitchen")
        self.assertEqual(kitchen["count"], 2)
        cup = next(a for a in fc["actions"] if a["code"] == "c003")
        self.assertEqual(cup["count"], 2)


class ServerTest(unittest.TestCase):
    """Runs the real HTTP handler on a random local port."""

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(load_dataset(FIXTURES)))
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as resp:
            return resp.status, resp.headers.get("Content-Type"), resp.read()

    def get_error(self, path):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get(path)
        return ctx.exception.code

    def test_index_page(self):
        status, ctype, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn(b"Charades Explorer", body)

    def test_videos_endpoint_filters(self):
        _, _, body = self.get("/api/videos?q=drinking&limit=1")
        data = json.loads(body)
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["id"], "AAA01")

    def test_video_detail(self):
        data = json.loads(self.get("/api/videos/aaa02")[2])
        self.assertEqual(data["scene_full"].split(" (")[0], "Entryway")
        self.assertEqual(len(data["segments"]), 2)

    def test_meta(self):
        data = json.loads(self.get("/api/meta")[2])
        self.assertEqual(data["stats"]["videos"], 5)
        self.assertIn("actions", data)

    def test_errors(self):
        self.assertEqual(self.get_error("/api/videos?min_length=abc"), 400)
        self.assertEqual(self.get_error("/api/videos/NOPE"), 404)
        self.assertEqual(self.get_error("/../../etc/passwd"), 404)


if __name__ == "__main__":
    unittest.main()
