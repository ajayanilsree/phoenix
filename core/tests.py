from django.test import TestCase
from django.urls import reverse
import json
from pathlib import Path


class SecuritySurfaceTests(TestCase):
    def test_sensitive_paths_are_not_exposed(self):
        for path in ["/.env", "/.git/config", "/.aws/credentials", "/.git-credentials"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_public_catalogue_and_robots_remain_available(self):
        self.assertEqual(self.client.get(reverse("robots_txt")).status_code, 200)
        self.assertEqual(self.client.get(reverse("robots_txt")).headers["Content-Type"], "text/plain")
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        self.assertEqual(self.client.get(reverse("shop")).status_code, 200)

    def test_pwa_resources_are_public_and_valid(self):
        manifest = self.client.get(reverse("manifest_webmanifest"))
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(manifest.headers["Content-Type"], "application/manifest+json")
        payload = json.loads(manifest.content)
        self.assertEqual(payload["display"], "standalone")
        self.assertEqual(payload["start_url"], "/")
        self.assertEqual(self.client.get(reverse("service_worker")).status_code, 200)
        self.assertTrue((Path(__file__).resolve().parent.parent / "static" / "pwa" / "icon-192.png").is_file())
        self.assertTrue((Path(__file__).resolve().parent.parent / "static" / "pwa" / "icon-512.png").is_file())
