import unittest
from unittest.mock import patch

from engine import ShoppingTask
from llm import interpret, merge_model_result


class ModelInterpretationTests(unittest.TestCase):
    def test_model_understands_chinese_budget_word(self):
        previous = ShoppingTask()
        raw = {"categories": ["耳机"], "budget": 900,
               "preferences": ["降噪"], "exclusions": ["入耳"]}
        task = merge_model_result(previous, "九百元左右，降噪耳机不要入耳", raw)
        self.assertEqual(task.budget, 900)
        self.assertEqual(task.categories, ["耳机"])
        self.assertIn("入耳", task.exclusions)

    def test_explicit_budget_overrides_model(self):
        raw = {"categories": ["耳机"], "budget": 1500,
               "preferences": ["无线"], "exclusions": []}
        task = merge_model_result(ShoppingTask(), "预算改为 900 元，耳机", raw)
        self.assertEqual(task.budget, 900)

    def test_interpret_uses_model_response(self):
        raw = {"categories": ["鼠标"], "budget": 300,
               "preferences": ["办公"], "exclusions": []}
        with patch("llm._request_model", return_value=raw):
            task = interpret(ShoppingTask(), "三百元以内的办公鼠标")
        self.assertEqual(task.budget, 300)
        self.assertEqual(task.categories, ["鼠标"])


if __name__ == "__main__":
    unittest.main()
