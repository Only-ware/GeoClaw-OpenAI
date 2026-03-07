from __future__ import annotations

import os
import unittest

from geoclaw_qgis.ai import ExternalAIConfig, compress_context


class TestAIProviderAndContext(unittest.TestCase):
    def test_context_compression_for_long_text(self) -> None:
        text = ("风险与建议\n" * 4000).strip()
        out = compress_context(text, max_chars=2000)
        self.assertTrue(out.compressed)
        self.assertGreater(out.original_chars, out.output_chars)
        self.assertLessEqual(out.output_chars, 2000)
        self.assertIn("Context compressed", out.text)

    def test_openai_provider_from_legacy_env(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["GEOCLAW_AI_PROVIDER"] = "openai"
            os.environ["GEOCLAW_OPENAI_BASE_URL"] = "https://api.openai.com/v1"
            os.environ["GEOCLAW_OPENAI_API_KEY"] = "sk-test"
            os.environ["GEOCLAW_OPENAI_MODEL"] = "gpt-4.1-mini"
            cfg = ExternalAIConfig.from_env()
            self.assertEqual(cfg.provider, "openai")
            self.assertEqual(cfg.model, "gpt-4.1-mini")
            self.assertTrue(cfg.base_url.startswith("https://api.openai.com"))
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_qwen_provider_from_provider_env(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["GEOCLAW_AI_PROVIDER"] = "qwen"
            os.environ["GEOCLAW_QWEN_API_KEY"] = "qwen-test-key"
            cfg = ExternalAIConfig.from_env()
            self.assertEqual(cfg.provider, "qwen")
            self.assertEqual(cfg.model, "qwen-plus")
            self.assertIn("dashscope.aliyuncs.com", cfg.base_url)
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_gemini_provider_from_provider_env(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["GEOCLAW_AI_PROVIDER"] = "gemini"
            os.environ["GEOCLAW_GEMINI_API_KEY"] = "gemini-test-key"
            cfg = ExternalAIConfig.from_env()
            self.assertEqual(cfg.provider, "gemini")
            self.assertEqual(cfg.model, "gemini-2.0-flash")
            self.assertIn("generativelanguage.googleapis.com", cfg.base_url)
        finally:
            os.environ.clear()
            os.environ.update(old)


if __name__ == "__main__":
    unittest.main()
