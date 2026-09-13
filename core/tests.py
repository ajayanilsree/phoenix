from django.test import TestCase
from django.urls import reverse


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
