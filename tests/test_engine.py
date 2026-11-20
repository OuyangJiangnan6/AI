import unittest

from engine import ShoppingTask, recommend, update_task


class ShoppingPlannerTests(unittest.TestCase):
    def test_multiturn_budget_and_exclusion(self):
        task = update_task(ShoppingTask(), "预算 1500 元，通勤降噪耳机")
        task = update_task(task, "不要入耳，预算改为 900 元")
        result = recommend(task)
        self.assertEqual(task.budget, 900)
        self.assertEqual(task.categories, ["耳机"])
        self.assertIn("入耳", task.exclusions)
        self.assertEqual(result["status"], "ok")
        self.assertLessEqual(result["bundles"][0]["total"], 900)
        self.assertNotIn("入耳", result["bundles"][0]["items"][0]["features"])

    def test_bundle_respects_total_budget(self):
        task = update_task(ShoppingTask(), "预算 1200 元，耳机和键盘，图书馆学习")
        result = recommend(task)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["bundles"][0]["items"]), 2)
        self.assertTrue(all(bundle["total"] <= 1200 for bundle in result["bundles"]))

    def test_infeasible_budget_explained(self):
        task = update_task(ShoppingTask(), "预算 100 元，耳机和键盘")
        result = recommend(task)
        self.assertEqual(result["status"], "over_budget")
        self.assertGreater(result["minimum"], 100)

    def test_asks_for_missing_information(self):
        self.assertEqual(recommend(ShoppingTask())["status"], "need_category")
        task = update_task(ShoppingTask(), "想买鼠标")
        self.assertEqual(recommend(task)["status"], "need_budget")


if __name__ == "__main__":
    unittest.main()
