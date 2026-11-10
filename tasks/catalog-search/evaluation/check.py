import os
import sys
import unittest
sys.path.insert(0, os.environ["BENCH_WORKSPACE"])
import catalog

class CatalogTests(unittest.TestCase):
    def test_search_case_and_order(self):
        items = ["Apple", "pear", "Pineapple"]
        self.assertEqual(catalog.search(items, "APP"), ["Apple", "Pineapple"])
        self.assertEqual(items, ["Apple", "pear", "Pineapple"])
    def test_empty_and_no_match(self):
        self.assertEqual(catalog.search(["a", "b"], ""), ["a", "b"])
        self.assertEqual(catalog.search(["a"], "z"), [])

if __name__ == "__main__":
    unittest.main()
