"""Deterministic tools for the Traveler Customs Advisor agent.

Includes:
1. calculate_duty_tax: Accurate duty and tax estimator for international baggage items.
2. generate_phrase_card: Generates a bilingual customs inspection flashcard for travelers.
3. lookup_country_limits: Fast-path limits lookup for top travel corridors.
"""

from typing import Any, Dict, List, Optional


# Approximate exchange rates relative to TWD (1 foreign currency unit to TWD)
EXCHANGE_RATES_TO_TWD = {
    "TWD": 1.0,
    "NTD": 1.0,
    "USD": 32.0,
    "JPY": 0.21,
    "EUR": 34.5,
    "GBP": 41.0,
    "KRW": 0.024,
    "CNY": 4.4,
    "HKD": 4.1,
    "AUD": 21.0,
    "SGD": 24.0,
}

# Standard statutory duty rates for common traveler items in Taiwan (關稅署標準稅率)
TAIWAN_DUTY_RATES = {
    "luxury_bag": 0.066,      # 精品名牌皮包 6.6%
    "leather_goods": 0.066,    # 皮革製品 6.6%
    "apparel": 0.105,         # 成衣/服飾 10.5%
    "cosmetics": 0.00,        # 化妝品/保養品 0%
    "perfume": 0.00,          # 香水 0%
    "electronics": 0.00,      # 手機/筆電/相機 0%
    "watch": 0.04,            # 一般手錶 4%
    "luxury_watch": 0.04,     # 高級手錶 4% (若逾 50 萬可能涉及奢侈品貨物稅)
    "jewelry": 0.00,          # 純金/首飾 0% (需符合洗錢防制申報)
    "health_supplement": 0.30,# 保健食品 (關稅約 30%)
    "wine": 0.10,             # 葡萄酒 10%
    "whisky": 0.00,           # 威士忌 0% 關稅 (主要課菸酒稅)
    "beer": 0.00,             # 啤酒 0% 關稅 (主要課菸酒稅)
    "general": 0.05,          # 一般物品綜合概算稅率 5%
}


def calculate_duty_tax(
    destination_country: str,
    item_category: str,
    declared_value: float,
    currency: str = "TWD",
    quantity: int = 1,
    alcohol_volume_liters: float = 0.0,
    alcohol_abv_percent: float = 0.0,
) -> Dict[str, Any]:
    """Calculates estimated customs duties and taxes for traveler baggage items.

    Args:
        destination_country: Destination country or region (e.g., 'Taiwan', 'Japan', 'USA', 'UK').
        item_category: Category of the item (e.g., 'luxury_bag', 'apparel', 'cosmetics', 'electronics', 'whisky', 'wine', 'general').
        declared_value: Original purchase price / invoice value of the item in the specified currency.
        currency: Currency code (e.g., 'TWD', 'USD', 'JPY', 'EUR', 'GBP'). Default is 'TWD'.
        quantity: Number of items.
        alcohol_volume_liters: Total volume in liters if the item is alcoholic beverage (e.g. 0.7, 1.0, 2.0).
        alcohol_abv_percent: Alcohol by volume percentage if alcoholic beverage (e.g. 40.0 for 40% whisky).

    Returns:
        A structured dictionary containing:
        - exceeds_exemption (bool): True if the item exceeds the duty-free allowance.
        - duty_free_threshold: The applicable duty-free threshold.
        - taxable_value: The value portion subject to duty and tax.
        - estimated_duty: The estimated customs duty amount.
        - estimated_vat: The estimated value-added / sales tax.
        - estimated_alcohol_tax: The estimated alcohol excise tax (if applicable).
        - total_estimated_tax: Total estimated payment due at customs.
        - channel_recommendation: 'Red Channel' (Goods to Declare) or 'Green Channel' (Nothing to Declare).
        - guidance: Actionable instructions for airport declaration.
    """
    dest_norm = destination_country.strip().lower()
    curr_norm = currency.strip().upper()
    cat_norm = item_category.strip().lower()
    total_val = float(declared_value) * int(quantity)

    # Convert to TWD for unified threshold comparison if Taiwan is destination
    rate_to_twd = EXCHANGE_RATES_TO_TWD.get(curr_norm, 32.0)
    value_in_twd = total_val * rate_to_twd

    # Handle Taiwan destination
    if any(k in dest_norm for k in ["taiwan", "tw", "臺灣", "台灣"]):
        if alcohol_volume_liters > 0:
            # Alcohol calculation for Taiwan
            # 1 liter is duty-free for age >= 18.
            excess_liters = max(0.0, alcohol_volume_liters - 1.0)
            if excess_liters <= 0.0:
                return {
                    "destination": "Taiwan",
                    "exceeds_exemption": False,
                    "channel_recommendation": "🟢 綠線免申報通道 (Green Channel)",
                    "alcohol_volume_liters": alcohol_volume_liters,
                    "duty_free_allowance": "1.0 公升 (免稅)",
                    "total_estimated_tax": 0.0,
                    "currency": "TWD",
                    "guidance": "酒類在 1 公升免稅範圍內，可直接走綠線免申報通道出關。",
                }

            if alcohol_volume_liters > 5.0:
                return {
                    "destination": "Taiwan",
                    "exceeds_exemption": True,
                    "channel_recommendation": "🔴 嚴正警告：超過自用攜帶上限！",
                    "alcohol_volume_liters": alcohol_volume_liters,
                    "guidance": "臺灣《菸酒管理法》規定旅客攜帶自用酒類上限為 5 公升。超過 5 公升必須具有菸酒進口業許可執照，否則海關依法不予放行或責令退運！",
                }

            # Distilled spirits: NT$2.5 per liter per degree ABV.
            # Other brewed / wine: NT$7 per liter or according to category.
            abv = alcohol_abv_percent if alcohol_abv_percent > 0 else 40.0
            if "wine" in cat_norm:
                alcohol_tax = excess_liters * 7.0 * (abv if abv <= 20 else 20)
                duty_rate = 0.10
            else:
                alcohol_tax = excess_liters * 2.5 * abv
                duty_rate = 0.00  # Whisky customs duty is 0% in Taiwan

            dutiable_val_twd = (excess_liters / alcohol_volume_liters) * value_in_twd
            customs_duty = dutiable_val_twd * duty_rate
            vat = (dutiable_val_twd + customs_duty + alcohol_tax) * 0.05
            total_tax = round(customs_duty + alcohol_tax + vat)

            return {
                "destination": "Taiwan",
                "exceeds_exemption": True,
                "channel_recommendation": "🟡 紅線應申報櫃檯 (Red Channel)",
                "alcohol_volume_liters": alcohol_volume_liters,
                "excess_liters": round(excess_liters, 2),
                "duty_free_allowance": "1.0 公升 (免稅)",
                "dutiable_value_twd": round(dutiable_val_twd),
                "estimated_customs_duty_twd": round(customs_duty),
                "estimated_alcohol_tax_twd": round(alcohol_tax),
                "estimated_vat_twd": round(vat),
                "total_estimated_tax_twd": total_tax,
                "currency": "TWD",
                "guidance": (
                    f"您攜帶酒類 {alcohol_volume_liters}L，扣除 1L 免稅額後，超額 {round(excess_liters, 2)}L 需申報補稅。"
                    f"預估應納稅費約新臺幣 {total_tax:,} 元。請入境時務必走【紅線應申報櫃檯】，主動申報絕不處罰！"
                ),
            }

        # General merchandise calculation for Taiwan
        # Exemption threshold: NT$35,000
        threshold_twd = 35000.0
        duty_rate = TAIWAN_DUTY_RATES.get(cat_norm, 0.05)
        vat_rate = 0.05

        if value_in_twd <= threshold_twd:
            return {
                "destination": "Taiwan",
                "exceeds_exemption": False,
                "channel_recommendation": "🟢 綠線免申報通道 (Green Channel)",
                "declared_value_twd": round(value_in_twd),
                "exemption_threshold_twd": round(threshold_twd),
                "total_estimated_tax": 0.0,
                "currency": "TWD",
                "guidance": f"物品完稅價值（約新臺幣 {round(value_in_twd):,} 元）在個人免稅額度 NT$35,000 以內，可安心走綠線通關。",
            }
        else:
            taxable_value_twd = value_in_twd - threshold_twd
            duty = taxable_value_twd * duty_rate
            vat = (taxable_value_twd + duty) * vat_rate
            total_tax = round(duty + vat)

            return {
                "destination": "Taiwan",
                "exceeds_exemption": True,
                "channel_recommendation": "🟡 紅線應申報櫃檯 (Red Channel)",
                "total_value_twd": round(value_in_twd),
                "exemption_threshold_twd": round(threshold_twd),
                "taxable_value_twd": round(taxable_value_twd),
                "duty_rate_percent": f"{duty_rate * 100:.1f}%",
                "estimated_duty_twd": round(duty),
                "estimated_vat_twd": round(vat),
                "total_estimated_tax_twd": total_tax,
                "currency": "TWD",
                "guidance": (
                    f"物品總值約新臺幣 {round(value_in_twd):,} 元，超出個人免稅額度（NT$35,000）。"
                    f"超出之課稅基礎為 NT$ {round(taxable_value_twd):,} 元，預估應繳關稅與營業稅約新臺幣 {total_tax:,} 元。"
                    "請於入境時走【紅線檯】主動填單申報繳稅，現場支援信用卡與行動支付。"
                ),
            }

    # Japan destination
    elif any(k in dest_norm for k in ["japan", "jp", "日本"]):
        threshold_jpy = 200000.0
        val_jpy = total_val if curr_norm == "JPY" else total_val * (rate_to_twd / 0.21)
        exceeds = val_jpy > threshold_jpy
        return {
            "destination": "Japan",
            "exceeds_exemption": exceeds,
            "channel_recommendation": "🟡 赤の課税通路 (Red Channel)" if exceeds else "🟢 緑の免税通路 (Green Channel)",
            "declared_value_jpy": round(val_jpy),
            "exemption_threshold_jpy": round(threshold_jpy),
            "guidance": (
                f"日本個人免稅額為 20 萬日圓。您的行李預估約 {round(val_jpy):,} 日圓。"
                + ("已超額，請走赤の課税通路申報。" if exceeds else "在免稅額內，可走綠色免稅通路。")
            ),
        }

    # United States destination
    elif any(k in dest_norm for k in ["us", "usa", "united states", "美國"]):
        threshold_usd = 800.0
        val_usd = total_val if curr_norm == "USD" else value_in_twd / 32.0
        exceeds = val_usd > threshold_usd
        return {
            "destination": "USA",
            "exceeds_exemption": exceeds,
            "channel_recommendation": "🟡 Red Channel (Declare to CBP)" if exceeds else "🟢 Green Channel (Nothing to Declare)",
            "declared_value_usd": round(val_usd, 2),
            "exemption_threshold_usd": round(threshold_usd, 2),
            "guidance": (
                f"US personal exemption is USD $800. Your item value is approx USD ${round(val_usd, 2)}."
                + (" Exceeds exemption: please declare on CBP Declaration Form 6059B or MPC app." if exceeds else " Within exemption allowance.")
            ),
        }

    # Default general guidance
    return {
        "destination": destination_country,
        "declared_value": total_val,
        "currency": curr_norm,
        "guidance": f"Destination: {destination_country}. Please check local customs portal or declare at Red Channel if commercial value exceeds standard personal baggage exemption.",
    }


def generate_phrase_card(
    destination_country: str,
    traveler_native_language: str,
    declared_items_summary: str,
    traveler_intent: str = "declaration_and_duty_payment",
) -> Dict[str, str]:
    """Generates an instant bilingual customs communication card for the traveler.

    This card is formatted for immediate display on a smartphone screen to customs officers,
    eliminating language barriers and demonstrating full compliance.

    Args:
        destination_country: Target country of entry (e.g. 'Japan', 'USA', 'Taiwan', 'UK', 'France', 'Korea').
        traveler_native_language: Native language of the traveler (e.g. 'Traditional Chinese', 'English', 'Japanese').
        declared_items_summary: Plain text description of the items to declare (e.g., '2 bottles of Scotch Whisky, 1 luxury handbag').
        traveler_intent: Intent of the traveler (default: 'declaration_and_duty_payment').

    Returns:
        A dictionary containing:
        - official_language_text: Large, clear phrase in destination country's official language.
        - native_language_translation: Explanatory translation for traveler reassurance.
        - presentation_markdown: Formatted markdown block ready to render directly.
    """
    dest = destination_country.strip().lower()
    items = declared_items_summary.strip()

    if any(k in dest for k in ["japan", "jp", "日本"]):
        official_text = (
            f"税関職員の皆様へ：\n"
            f"私は個人使用目的で以下の物品を所持しており、自発的に申告いたします。\n\n"
            f"【申告品目】\n"
            f"{items}\n\n"
            f"関税および消費税の計算と納付手続きをお願い申し上げます。"
        )
        native_text = f"海關長官您好：我攜帶了以下自用物品，特此主動辦理申報並繳納相關稅款：\n{items}"
    elif any(k in dest for k in ["korea", "kr", "韓國", "韩国"]):
        official_text = (
            f"세관 공무원 귀하:\n"
            f"저는 개인적인 용도로 다음 품목을 소지하고 있으며 자발적으로 세관에 신고합니다.\n\n"
            f"【신고 품목】\n"
            f"{items}\n\n"
            f"관세 및 세금 납부 절차를 안내해 주시기 바랍니다."
        )
        native_text = f"海關長官您好：我攜帶了以下自用物品，主動向海關申報並配合繳納稅捐：\n{items}"
    elif any(k in dest for k in ["france", "fr", "法國"]):
        official_text = (
            f"À l'attention des agents des douanes :\n"
            f"Je transporte les articles suivants pour mon usage personnel et je souhaite les déclarer spontanément.\n\n"
            f"【Articles déclarés】\n"
            f"{items}\n\n"
            f"Je suis disposé(e) à régler les droits et taxes applicables. Merci pour votre aide."
        )
        native_text = f"海關官員您好：我攜帶了以上自用物品，特此主動申報並願意繳納適用關稅。"
    elif any(k in dest for k in ["taiwan", "tw", "臺灣", "台灣"]):
        official_text = (
            f"海關執勤同仁您好：\n"
            f"本人隨身/託運行李中含有以下自用超額或應申報物品，特此主動向紅線櫃檯申報：\n\n"
            f"【申報物品明細】\n"
            f"{items}\n\n"
            f"請協助查驗並開立稅款繳納單，本人將配合依規完成繳稅。"
        )
        native_text = official_text
    else:  # Default to international English
        official_text = (
            f"To the Customs & Border Protection Officer:\n"
            f"Hello Officer, I am carrying the following personal items and would like to declare them voluntarily:\n\n"
            f"【Declared Items】\n"
            f"{items}\n\n"
            f"I would like to complete the customs declaration and pay any applicable duties or taxes. Thank you."
        )
        native_text = f"海關官員您好：我攜帶了以上自用物品，特此主動走紅線申報並願意繳納適用關稅與稅款。"

    card_markdown = (
        "```text\n"
        "┌──────────────────────────────────────────────────────────────┐\n"
        "│ 🛃 CUSTOMS DECLARATION CARD / 海關自主申報提示小卡             │\n"
        "├──────────────────────────────────────────────────────────────┤\n"
        f"{official_text}\n"
        "├──────────────────────────────────────────────────────────────┤\n"
        f"（旅客母語對照）:\n{native_text}\n"
        "└──────────────────────────────────────────────────────────────┘\n"
        "```"
    )

    return {
        "destination_country": destination_country,
        "official_language_text": official_text,
        "native_language_translation": native_text,
        "presentation_markdown": card_markdown,
    }


def lookup_country_limits(destination_country: str) -> Dict[str, Any]:
    """Provides instant reference limits for top international travel corridors.

    Args:
        destination_country: The name or code of the destination country.

    Returns:
        Dictionary of official statutory limits for duty-free goods, tobacco, alcohol, and cash.
    """
    dest = destination_country.strip().lower()
    if any(k in dest for k in ["taiwan", "tw", "臺灣", "台灣"]):
        return {
            "country": "Taiwan (臺灣)",
            "general_exemption": "NT$35,000 (自用完稅價格)",
            "alcohol_limit": "1.0 公升 (免稅，限18歲以上)；自用上限5.0公升 (需申報補稅)",
            "tobacco_limit": "捲菸 200 支 (1條) 或雪茄 25 支 或菸絲 250g (限20歲以上)",
            "vapes_e_cigarettes": "【嚴正警告 - 絕對禁止】電子煙與加熱菸全面禁帶，違者最高罰 NT$500 萬",
            "cash_limit": "新臺幣 10 萬元、人民幣 2 萬元、外幣等值 1 萬美元 (超額需主動申報)",
            "meat_quarantine": "【嚴格禁止】任何豬肉/含肉製品（非洲豬瘟零容忍，初犯罰 NT$20 萬，累犯罰 NT$100 萬）",
            "otc_medicine": "單一藥品最多 12 瓶/盒，各類藥品合計總數不超過 36 瓶/盒",
            "prescription_drug": "無處方箋限 2 個月用量；持處方箋限 6 個月用量",
        }
    elif any(k in dest for k in ["japan", "jp", "日本"]):
        return {
            "country": "Japan (日本)",
            "general_exemption": "200,000 日圓 (海外市價合計)",
            "alcohol_limit": "3 瓶 (每瓶約 760ml，合計約 2,280ml 免稅)",
            "tobacco_limit": "捲菸 200 支 或雪茄 50 支 或菸草 250g",
            "vapes_e_cigarettes": "自用尼古丁煙油限 120ml 或 1 個月用量；非尼古丁電子煙允許",
            "cash_limit": "1,000,000 日圓等值現鈔 (超額需向稅關申報)",
            "meat_quarantine": "嚴禁未經日本動物檢疫所認證肉製品，違者最高罰 300 萬日圓或 3 年有期徒刑",
            "otc_medicine": "一般醫藥品限 2 個月用量；眼藥水外用藥限 24 個以內",
            "prohibited_medicine": "【嚴禁】含偽麻黃鹼超過10%感冒藥、Adderall、含可待因超量藥劑",
        }
    elif any(k in dest for k in ["us", "usa", "united states", "美國"]):
        return {
            "country": "United States (美國)",
            "general_exemption": "USD $800 (美國居民) / USD $100 (非居民訪客禮物額度)",
            "alcohol_limit": "1.0 公升 (年滿 21 歲)",
            "tobacco_limit": "捲菸 200 支 (1 條) 及 100 支非古巴雪茄",
            "cash_limit": "USD $10,000 等值貨幣 (需向 CBP 提交 FinCEN 105 表格)",
            "meat_quarantine": "大多數肉製品、生鮮水果、未處理種子嚴格禁止攜入 (違者罰款最高 $10,000)",
        }
    elif any(k in dest for k in ["uk", "united kingdom", "英國"]):
        return {
            "country": "United Kingdom (英國)",
            "general_exemption": "£390 (搭乘民航商業機)",
            "alcohol_limit": "啤酒 42L、葡萄酒 18L，及烈酒 (>22%) 4L 或加強酒 9L",
            "tobacco_limit": "捲菸 200 支 或雪茄 50 支 或菸草 250g",
            "cash_limit": "£10,000 等值貨幣需向 HMRC 申報",
            "meat_quarantine": "禁止從非歐盟國家攜帶任何肉類、肉製品或奶製品入境",
        }
    else:
        return {
            "country": destination_country,
            "general_rule": "Please consult local customs service or declaration desk upon arrival.",
        }
