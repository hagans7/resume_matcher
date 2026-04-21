"""Unit tests for MaskPIIService."""

import pytest

from src.services.mask_pii import MaskPIIService


@pytest.fixture
def svc() -> MaskPIIService:
    return MaskPIIService()


class TestEmailMasking:
    def test_masks_standard_email(self, svc):
        result = svc.execute("Contact: john.doe@example.com for details")
        assert "[EMAIL]" in result
        assert "john.doe@example.com" not in result

    def test_masks_multiple_emails(self, svc):
        result = svc.execute("a@b.com and c@d.org")
        assert result.count("[EMAIL]") == 2

    def test_preserves_non_email_text(self, svc):
        result = svc.execute("Python developer with 3 years experience")
        assert result == "Python developer with 3 years experience"


class TestPhoneMasking:
    def test_masks_indonesian_mobile(self, svc):
        result = svc.execute("Call me at 081234567890")
        assert "[PHONE]" in result
        assert "081234567890" not in result

    def test_masks_plus62_format(self, svc):
        result = svc.execute("Phone: +6281234567890")
        assert "[PHONE]" in result


class TestNIKMasking:
    def test_masks_16_digit_nik(self, svc):
        result = svc.execute("NIK: 3201234567890001")
        assert "[NIK]" in result
        assert "3201234567890001" not in result

    def test_does_not_mask_shorter_numbers(self, svc):
        result = svc.execute("5 years of experience")
        assert "[NIK]" not in result


class TestURLMasking:
    def test_masks_https_url(self, svc):
        result = svc.execute("Portfolio: https://myportfolio.com/work")
        assert "[URL]" in result

    def test_masks_linkedin(self, svc):
        result = svc.execute("linkedin.com/in/johndoe")
        assert "[URL]" in result

    def test_masks_github(self, svc):
        result = svc.execute("github.com/johndoe")
        assert "[URL]" in result


class TestNoMutation:
    def test_returns_new_string_not_mutates(self, svc):
        original = "Email: test@example.com"
        _ = svc.execute(original)
        assert original == "Email: test@example.com"

    def test_empty_string(self, svc):
        assert svc.execute("") == ""
