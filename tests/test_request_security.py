import unittest

from request_security import is_safe_mutation_request


class RequestSecurityTests(unittest.TestCase):
    def test_allows_same_origin_mutations(self):
        self.assertTrue(is_safe_mutation_request(
            "http://127.0.0.1:8000", "http://127.0.0.1:8000", "same-origin"
        ))

    def test_allows_only_local_vite_origins_for_development(self):
        self.assertTrue(is_safe_mutation_request(
            "http://localhost:5173", "http://127.0.0.1:8000", "cross-site"
        ))
        self.assertTrue(is_safe_mutation_request(
            "http://127.0.0.1:5173", "http://127.0.0.1:8000", "same-site"
        ))
        self.assertFalse(is_safe_mutation_request(
            "https://attacker.example", "http://127.0.0.1:8000", "cross-site"
        ))

    def test_rejects_originless_cross_site_mutations(self):
        self.assertFalse(is_safe_mutation_request(
            None, "http://127.0.0.1:8000", "cross-site"
        ))
        self.assertFalse(is_safe_mutation_request(
            None, "http://127.0.0.1:8000", None
        ))
        self.assertTrue(is_safe_mutation_request(
            None, "http://127.0.0.1:8000", "same-origin"
        ))

    def test_rejects_non_loopback_hosts_even_when_origin_matches_host(self):
        self.assertFalse(is_safe_mutation_request(
            "http://attacker.example:8000",
            "http://attacker.example:8000",
            "same-origin",
        ))


if __name__ == "__main__":
    unittest.main()
