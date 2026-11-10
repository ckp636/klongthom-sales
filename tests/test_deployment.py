import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def test_only_allowlisted_static_assets_are_built(self):
        config = json.loads((ROOT / "vercel.json").read_text())
        static = {build["src"] for build in config["builds"] if build["use"] == "@vercel/static"}
        self.assertEqual(static, {"index.html", "app.html", "support.js"})
        self.assertNotIn("headers", config)
        self.assertNotIn("cleanUrls", config)
        self.assertTrue(any(route.get("status") == 404 for route in config["routes"]))

    def test_dependencies_and_native_asgi_entrypoint(self):
        requirements = (ROOT / "requirements.txt").read_text()
        self.assertIn("fastapi==", requirements)
        self.assertIn("pymssql==", requirements)
        self.assertNotIn("-r ", "\n".join(line for line in requirements.splitlines() if not line.lstrip().startswith("#")))
        entry = (ROOT / "api/index.py").read_text()
        self.assertIn("from app.main import app", entry)
        self.assertNotIn("Mangum", entry)

    def test_daily_retention_schedule(self):
        config = json.loads((ROOT / "vercel.json").read_text())
        self.assertEqual(config["crons"], [{"path": "/api/maintenance/photos/cleanup", "schedule": "0 0 * * *"}])
