"""Unit tests for Capstone Customs Advisor tools and guardrails."""

import pytest
from capstone_customs_agent.tools import (
    calculate_duty_tax,
    generate_phrase_card,
    lookup_country_limits,
    get_destination_culture_etiquette,
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

        # Test expanded 18 countries
        kr_limits = lookup_country_limits("South Korea")
        assert "800" in kr_limits["general_exemption"]
        assert "肉乾" in kr_limits["meat_quarantine"]

        ca_limits = lookup_country_limits("Canada")
        assert "800" in ca_limits["general_exemption"]

        fr_limits = lookup_country_limits("France")
        assert "430" in fr_limits["general_exemption"]

        au_limits = lookup_country_limits("Australia")
        assert "900" in au_limits["general_exemption"]
        assert "生物檢疫" in au_limits["meat_quarantine"]

    def test_get_destination_weather(self):
        from capstone_customs_agent.tools import get_destination_weather

        # Test autumn forecast for Japan
        res_jp = get_destination_weather("Japan", "2026-10-25", "2026-10-30")
        assert "日本" in res_jp["destination"]
        assert "°C" in res_jp["temperature_range"]
        assert len(res_jp["packing_suggestions"]) > 0

        # Test southern hemisphere / Australia
        res_au = get_destination_weather("Australia", "2026-12-15", "2026-12-25")
        assert "澳洲" in res_au["destination"]
        assert "°C" in res_au["temperature_range"]

        # Test default/unknown fallback
        res_unknown = get_destination_weather("Mars", "2026-10-25", "2026-10-30")
        assert "臺灣" in res_unknown["destination"]
        assert "舒適" in res_unknown["weather_condition"]

    def test_multilingual_phrase_cards(self):
        # Korea
        card_kr = generate_phrase_card(
            destination_country="South Korea",
            traveler_native_language="Traditional Chinese",
            declared_items_summary="Red Wine 2 bottles",
        )
        assert "세관 공무원 귀하" in card_kr["official_language_text"]

        # France
        card_fr = generate_phrase_card(
            destination_country="France",
            traveler_native_language="English",
            declared_items_summary="Cash €12,000",
        )
        assert "agents des douanes" in card_fr["official_language_text"]

    def test_destination_culture_etiquette(self):
        # 1. Singapore: Strict fines, littering, e-cigarettes, chewing gum
        sg_etiquette = get_destination_culture_etiquette("Singapore")
        assert "新加坡" in sg_etiquette["country_zh"]
        assert sg_etiquette["flag"] == "🇸🇬"
        assert len(sg_etiquette["highlight_warnings"]) >= 3
        assert len(sg_etiquette["rules"]) >= 4
        # Check specific penalty/rule presence
        titles = [r["title"] for r in sg_etiquette["rules"]]
        assert any("口香糖" in t for t in titles)
        assert any("垃圾" in t or "吸菸" in t for t in titles)

        # 2. Japan: Photography, smoking, train manners
        jp_etiquette = get_destination_culture_etiquette("日本 (Japan)")
        assert "日本" in jp_etiquette["country_zh"]
        assert jp_etiquette["flag"] == "🇯🇵"
        jp_titles = [r["title"] for r in jp_etiquette["rules"]]
        assert any("拍照" in t or "肖像" in t for t in jp_titles)
        assert any("抽菸" in t or "吸菸" in t for t in jp_titles)

        # 3. Thailand: Royal family defamation (lèse-majesté), sacred heads
        th_etiquette = get_destination_culture_etiquette("Thailand")
        assert "泰國" in th_etiquette["country_zh"]
        assert "皇室" in th_etiquette["overview"] or any("皇室" in w for w in th_etiquette["highlight_warnings"])

        # 4. Australia: Biosecurity, beach safety, wildlife
        au_etiquette = get_destination_culture_etiquette("澳洲 (Australia)")
        assert "澳洲" in au_etiquette["country_zh"]
        au_rules = au_etiquette["rules"]
        assert any("6,260" in r["penalty"] for r in au_rules)

        # 5. Fallback for unknown country
        unknown_etiquette = get_destination_culture_etiquette("Atlantis")
        assert "臺灣" in unknown_etiquette["country_zh"]

    def test_all_18_countries_etiquette_and_frontend_sync(self):
        import json
        from pathlib import Path

        countries_to_check = [
            ("台灣", "taiwan", "臺灣"),
            ("臺灣 (Taiwan)", "taiwan", "臺灣"),
            ("韓國 (South Korea)", "korea", "韓國"),
            ("日本 (Japan)", "japan", "日本"),
            ("美國 (USA)", "usa", "美國"),
            ("英國 (UK)", "uk", "英國"),
            ("加拿大 (Canada)", "canada", "加拿大"),
            ("義大利 (Italy)", "italy", "義大利"),
            ("荷蘭 (Netherlands)", "netherlands", "荷蘭"),
            ("西班牙 (Spain)", "spain", "西班牙"),
            ("希臘 (Greece)", "greece", "希臘"),
            ("澳洲 (Australia)", "australia", "澳洲"),
            ("新加坡 (Singapore)", "singapore", "新加坡"),
            ("泰國 (Thailand)", "thailand", "泰國"),
            ("越南 (Vietnam)", "vietnam", "越南"),
            ("菲律賓 (Philippines)", "philippines", "菲律賓"),
            ("馬來西亞 (Malaysia)", "malaysia", "馬來西亞"),
            ("香港 (Hong Kong)", "hong kong", "香港"),
            ("法國 (France)", "france", "法國"),
        ]

        for query, expected_key, expected_zh in countries_to_check:
            res = get_destination_culture_etiquette(query)
            assert res["key"] == expected_key, f"Failed key for {query}: {res.get('key')}"
            assert expected_zh in res["country_zh"], f"Failed country_zh for {query}: {res.get('country_zh')}"
            assert expected_zh in res["country_name"], f"Failed country_name for {query}: {res.get('country_name')}"
            assert res.get("flag"), f"Missing flag for {query}"
            assert res.get("overview"), f"Missing overview for {query}"
            assert len(res.get("highlight_warnings", [])) >= 3, f"Missing highlight_warnings for {query}"
            assert len(res.get("rules", [])) >= 3, f"Missing rules for {query}"

        # Verify static/index.html has all 18 countries in OFFLINE_ETIQUETTE_DB_I18N across all languages
        static_html_path = Path(__file__).resolve().parent.parent / "static" / "index.html"
        html_text = static_html_path.read_text(encoding="utf-8")
        prefix = "    const OFFLINE_ETIQUETTE_DB_I18N = "
        db_line = next(line for line in html_text.splitlines() if line.startswith(prefix))
        db_i18n = json.loads(db_line[len(prefix):].rstrip(";"))

        expected_keys = {k for _, k, _ in countries_to_check}
        for lang in ["zh-TW", "en", "ja", "ko", "en-US", "en-GB", "ja-JP", "ko-KR"]:
            assert lang in db_i18n, f"Missing language {lang} in OFFLINE_ETIQUETTE_DB_I18N"
            for k in expected_keys:
                assert k in db_i18n[lang], f"Missing country '{k}' in OFFLINE_ETIQUETTE_DB_I18N['{lang}']"
                entry = db_i18n[lang][k]
                assert entry.get("country_name"), f"Empty country_name for {k} in {lang}"
                assert entry.get("flag"), f"Empty flag for {k} in {lang}"
                assert entry.get("overview"), f"Empty overview for {k} in {lang}"
                assert len(entry.get("highlight_warnings", [])) >= 3, f"Insufficient warnings for {k} in {lang}"
                assert len(entry.get("rules", [])) >= 2, f"Insufficient rules for {k} in {lang}"


