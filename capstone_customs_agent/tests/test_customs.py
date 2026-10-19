"""Unit tests for Capstone Customs Advisor tools and guardrails."""

import pytest
from capstone_customs_agent.tools import (
    calculate_duty_tax,
    generate_phrase_card,
    lookup_country_limits,
)
from capstone_customs_agent.guardrails import (
    scrub_pii,
    clean_pii_local,
    PRIVACY_BANNER,
)


class TestZeroPIIGuardrail:
    """Test cases for Zero-PII privacy protection."""

    def test_scrub_taiwan_passport(self):
        text = "我的護照號碼是 314567890，請問去日本可以帶肉乾嗎？"
        sanitized, redacted = scrub_pii(text)
        assert redacted is True
        assert "314567890" not in sanitized
        assert "[REDACTED_PASSPORT]" in sanitized

    def test_scrub_taiwan_national_id(self):
        text = "身分證字號 A123456789，想查去臺灣能帶多少酒"
        sanitized, redacted = scrub_pii(text)
        assert redacted is True
        assert "A123456789" not in sanitized
        assert "[REDACTED_NATIONAL_ID]" in sanitized

    def test_scrub_phone_and_email(self):
        text = "聯絡我：0912-345-678 或 traveler@example.com"
        sanitized, redacted = scrub_pii(text)
        assert redacted is True
        assert "traveler@example.com" not in sanitized
        assert "0912-345-678" not in sanitized

    def test_clean_input_unaffected(self):
        text = "我要從日本回臺灣，帶了 2 瓶威士忌跟 1 個名牌包"
        sanitized, redacted = scrub_pii(text)
        assert redacted is False
        assert sanitized == text


class TestCustomsTools:
    """Test cases for deterministic duty calculations and corridor lookup."""

    def test_taiwan_within_general_allowance(self):
        result = calculate_duty_tax(
            destination_country="Taiwan",
            item_category="apparel",
            declared_value=20000,
            currency="TWD",
        )
        assert result["exceeds_exemption"] is False
        assert "綠線" in result["channel_recommendation"]
        assert result["total_estimated_tax"] == 0.0

    def test_taiwan_luxury_bag_exceeding_allowance(self):
        # 80,000 TWD luxury bag, exceeds 35,000 TWD threshold by 45,000 TWD
        result = calculate_duty_tax(
            destination_country="Taiwan",
            item_category="luxury_bag",
            declared_value=80000,
            currency="TWD",
        )
        assert result["exceeds_exemption"] is True
        assert "紅線" in result["channel_recommendation"]
        assert result["taxable_value_twd"] == 45000.0
        assert result["total_estimated_tax_twd"] > 0

    def test_taiwan_alcohol_within_limit(self):
        result = calculate_duty_tax(
            destination_country="Taiwan",
            item_category="whisky",
            declared_value=3000,
            currency="TWD",
            alcohol_volume_liters=1.0,
        )
        assert result["exceeds_exemption"] is False
        assert "綠線" in result["channel_recommendation"]

    def test_taiwan_alcohol_exceeding_limit(self):
        result = calculate_duty_tax(
            destination_country="Taiwan",
            item_category="whisky",
            declared_value=6000,
            currency="TWD",
            alcohol_volume_liters=2.0,
            alcohol_abv_percent=40.0,
        )
        assert result["exceeds_exemption"] is True
        assert "紅線" in result["channel_recommendation"]
        assert result["excess_liters"] == 1.0
        assert result["total_estimated_tax_twd"] > 0

    def test_taiwan_alcohol_exceeding_personal_cap(self):
        result = calculate_duty_tax(
            destination_country="Taiwan",
            item_category="whisky",
            declared_value=15000,
            currency="TWD",
            alcohol_volume_liters=6.0,
        )
        assert result["exceeds_exemption"] is True
        assert "嚴正警告" in result["channel_recommendation"]

    def test_japan_phrase_card_generation(self):
        card = generate_phrase_card(
            destination_country="Japan",
            traveler_native_language="Traditional Chinese",
            declared_items_summary="Whisky (2 bottles, 1.4L)",
        )
        assert "税関職員の皆様へ" in card["official_language_text"]
        assert "Whisky" in card["official_language_text"]
        assert "CUSTOMS DECLARATION CARD" in card["presentation_markdown"]

    def test_lookup_country_limits(self):
        tw_limits = lookup_country_limits("Taiwan")
        assert "NT$35,000" in tw_limits["general_exemption"]
        assert "非洲豬瘟" in tw_limits["meat_quarantine"]
        assert "電子煙" in tw_limits["vapes_e_cigarettes"]
