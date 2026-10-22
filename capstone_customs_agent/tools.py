"""Deterministic tools for the Traveler Customs Advisor agent.

Includes:
1. calculate_duty_tax: Accurate duty and tax estimator for international baggage items.
2. generate_phrase_card: Generates a bilingual customs inspection flashcard for travelers.
3. lookup_country_limits: Fast-path limits lookup for top travel corridors across 18 destinations.
4. get_destination_weather: Real-time and seasonal weather forecast & packing advice.
5. get_destination_culture_etiquette: Destination cultural etiquette, traveler laws, and penalty warnings.
"""

import datetime
import re
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
    elif any(k in dest for k in ["italy", "it", "義大利", "意大利"]):
        official_text = (
            f"All'attenzione dei funzionari doganali:\n"
            f"Trasporto i seguenti articoli per uso personale e desidero dichiararli spontaneamente.\n\n"
            f"【Articoli dichiarati】\n"
            f"{items}\n\n"
            f"Sono disponibile a corrispondere i dazi e le imposte applicabili. Grazie per l'assistenza."
        )
        native_text = f"海關長官您好：我攜帶了以上自用物品，特此主動走紅線申報並願意配合繳稅。"
    elif any(k in dest for k in ["spain", "es", "西班牙"]):
        official_text = (
            f"A la atención de los funcionarios de aduanas:\n"
            f"Llevo los siguientes artículos para uso personal y deseo declararlos voluntariamente.\n\n"
            f"【Artículos declarados】\n"
            f"{items}\n\n"
            f"Estoy dispuesto/a a abonar los aranceles e impuestos correspondientes. Gracias por su ayuda."
        )
        native_text = f"海關長官您好：我攜帶了以上自用物品，主動走紅線向海關申報並配合繳納稅捐。"
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
    """Provides instant reference limits for all 18 top international travel destinations.

    Supported:
    Taiwan, Japan, South Korea, Canada, Italy, Netherlands, Singapore, Thailand,
    Vietnam, Philippines, Malaysia, France, Australia, Spain, Greece, USA, UK, Hong Kong.
    """
    dest = destination_country.strip().lower()

    if any(k in dest for k in ["taiwan", "tw", "臺灣", "台灣"]):
        return {
            "country": "臺灣 (Taiwan)",
            "currency": "TWD",
            "general_exemption": "NT$35,000 (自用物品完稅價格合計)",
            "alcohol_limit": "1.0 公升 (免稅，限18歲以上)；自用攜帶上限5.0公升 (超額1L部分走紅線申報補稅，超過5L需進口許可)",
            "tobacco_limit": "捲菸 200 支 (1條) 或雪茄 25 支 或菸絲 250g (限20歲以上)",
            "vapes_e_cigarettes": "【嚴正警告 - 絕對禁止】電子煙與加熱菸全面禁帶入境，違者最高罰 NT$500 萬，切勿心存僥倖！",
            "cash_limit": "新臺幣 10 萬元、人民幣 2 萬元、外幣等值 1 萬美元 (超額需主動向海關申報，未申報全數沒入)",
            "meat_quarantine": "【嚴格禁止】任何豬肉/含肉製品（非洲豬瘟零容忍，初犯罰 NT$20 萬，累犯罰 NT$100 萬；外籍人士未繳清罰鍰將拒絕入境）",
            "otc_medicine": "非處方藥 (OTC) 單一種最多 12 瓶/盒，各類合計總數不超過 36 瓶/盒",
            "prescription_drug": "處方藥未出示醫師處方箋限 2 個月用量；具合格處方箋限 6 個月用量",
            "red_channel_golden_rule": "主動走紅線誠實申報，海關絕不處罰，頂多補稅或自願退運！",
        }
    elif any(k in dest for k in ["japan", "jp", "日本"]):
        return {
            "country": "日本 (Japan)",
            "currency": "JPY",
            "general_exemption": "200,000 日圓 (海外購入市價總和，單件逾20萬者全額課稅)",
            "alcohol_limit": "3 瓶 (每瓶約 760ml，合計約 2,280ml 免稅)",
            "tobacco_limit": "捲菸 200 支 或雪茄 50 支 或菸草 250g (僅供海外居住者)",
            "vapes_e_cigarettes": "含尼古丁煙油自用限 120ml 或 1 個月用量；非尼古丁電子煙可攜帶",
            "cash_limit": "1,000,000 日圓等值現鈔、支票或黃金 (超額需主動向稅關申報)",
            "meat_quarantine": "嚴禁未經日本動物檢疫所認證肉製品 (違者最高罰 300 萬日圓或 3 年有期徒刑)",
            "otc_medicine": "一般醫藥品限 2 個月用量；外用藥/眼藥水每種限 24 個以內",
            "prohibited_medicine": "【嚴禁】含偽麻黃鹼超過10%感冒藥、Adderall、含可待因超量藥品",
            "red_channel_golden_rule": "超出免稅範圍請走「赤の課税通路」誠實填單申報補稅即可安心出關。",
        }
    elif any(k in dest for k in ["korea", "kr", "韓國", "韩国", "south korea"]):
        return {
            "country": "韓國 (South Korea)",
            "currency": "KRW",
            "general_exemption": "USD $800 (海外旅行購入物品免稅總額)",
            "alcohol_limit": "2 瓶 (合計不超過 2 公升，且總價在 USD $400 以下免稅)",
            "tobacco_limit": "捲菸 200 支 (1條) 或雪茄 50 支 或電子煙液 20ml",
            "vapes_e_cigarettes": "尼古丁煙油自用限 20ml 以內免稅，超出需按規定繳稅",
            "cash_limit": "等值 USD $10,000 外幣現鈔或韓元 (超額需填表向關稅廳申報)",
            "meat_quarantine": "嚴禁攜帶未經檢疫之豬肉、牛肉、火腿及肉乾製品 (違者最高重罰 1,000 萬韓元)",
            "otc_medicine": "常備自用藥品限 6 瓶以內或 3 個月用量；管制藥品必須具備英文醫師診斷證明",
            "red_channel_golden_rule": "申報單如實勾選有應稅物品並走申報通道，可免除逃稅罰金處分。",
        }
    elif any(k in dest for k in ["canada", "ca", "加拿大"]):
        return {
            "country": "加拿大 (Canada)",
            "currency": "CAD",
            "general_exemption": "CAD $800 (離境 48 小時以上之旅客免稅額)",
            "alcohol_limit": "葡萄酒 1.5L，或烈酒 1.14L，或啤酒 8.5L (年滿19歲，魁北克/亞伯達滿18歲)",
            "tobacco_limit": "捲菸 200 支 (1條) 及雪茄 50 支 及菸草 200g",
            "vapes_e_cigarettes": "允許個人自用少量電子煙，尼古丁含量不得超過 20mg/ml",
            "cash_limit": "等值 CAD $10,000 貨幣 (必須向加拿大邊境服務局 CBSA 申報)",
            "meat_quarantine": "嚴格禁止攜帶生鮮肉類、家禽產品及未經許可之新鮮蔬果與種子",
            "otc_medicine": "自用常備藥最多 90 天用量，需具備原廠包裝與明確成分標示",
            "red_channel_golden_rule": "於 CBSA 電子機台 (Kiosk) 或申報單據實勾選，海關查驗即開單計稅放行。",
        }
    elif any(k in dest for k in ["italy", "it", "義大利", "意大利"]):
        return {
            "country": "義大利 (Italy / EU)",
            "currency": "EUR",
            "general_exemption": "€430 (搭乘航空自非歐盟國入境旅客免稅總額)",
            "alcohol_limit": "烈酒 (>22%) 1.0L 或加強酒 2.0L；非氣泡葡萄酒 4.0L；啤酒 16.0L",
            "tobacco_limit": "捲菸 200 支 或雪茄 50 支 或菸草 250g (年滿 17 歲)",
            "vapes_e_cigarettes": "允許隨身攜帶個人合理自用電子煙與煙油，需符合歐盟安全規範",
            "cash_limit": "€10,000 等值現鈔或證券需主動向海關申報",
            "meat_quarantine": "嚴格禁止自非歐盟國家攜帶任何肉製品、香腸、火腿、乳酪及奶製品入境",
            "otc_medicine": "個人自用藥品限旅行天數合理用量 (一般 30 天內)，建議備妥英文處方箋",
            "red_channel_golden_rule": "走紅線通道向海關官員出示物品並補稅，絕不受罰。",
        }
    elif any(k in dest for k in ["netherlands", "nl", "荷蘭"]):
        return {
            "country": "荷蘭 (Netherlands / EU)",
            "currency": "EUR",
            "general_exemption": "€430 (搭乘民航班機自非歐盟國入境免稅額)",
            "alcohol_limit": "烈酒 (>22%) 1.0L 或加強酒 2.0L；葡萄酒 4.0L；啤酒 16.0L",
            "tobacco_limit": "捲菸 200 支 或雪茄 50 支 或菸絲 250g",
            "vapes_e_cigarettes": "個人自用少量可攜帶，需符合歐盟 TPD 標準",
            "cash_limit": "€10,000 等值貨幣 (需向荷蘭皇家海關主動申報)",
            "meat_quarantine": "禁止從非歐盟國家攜帶肉類、肉製品、牛奶及乳製品；花卉球莖未附植物檢疫證明嚴禁攜入",
            "otc_medicine": "自用常備藥品限個人旅行期所需量，管制藥物須附申根醫療證明 (Schengen Certificate)",
            "red_channel_golden_rule": "主動走申報紅線向海關出示並依稅率繳稅即可。",
        }
    elif any(k in dest for k in ["singapore", "sg", "新加坡"]):
        return {
            "country": "新加坡 (Singapore)",
            "currency": "SGD",
            "general_exemption": "離境48小時以上 SGD $500 / 離境未滿48小時 SGD $100",
            "alcohol_limit": "烈酒 1L + 葡萄酒 1L + 啤酒 1L (多種組合任選，限年滿18歲且非自馬來西亞入境)",
            "tobacco_limit": "【重要提醒】新加坡【無任何免稅香菸額度】！攜帶任何香菸哪怕一包皆須走紅線如實申報並繳納關稅與消費稅！",
            "vapes_e_cigarettes": "【嚴正警告 - 絕對禁止】電子煙與仿菸草製品全面非法！持有最高罰 SGD $2,000，走私/進口最高罰 SGD $10,000 或監禁 6 個月！",
            "cash_limit": "等值 SGD $20,000 貨幣 (必須填寫 Form NP 727 主動申報)",
            "meat_quarantine": "嚴格限制肉類，口香糖嚴禁攜帶入境；非核准產地之肉乾與禽肉全面禁止",
            "otc_medicine": "自用常備藥限 3 個月內用量；管制藥品或麻醉劑須事先向新加坡衛生科學局 (HSA) 申請核准",
            "red_channel_golden_rule": "新加坡海關執法嚴謹，如有任何菸酒或超額物品，務必走紅線申報，切勿冒險走綠線！",
        }
    elif any(k in dest for k in ["thailand", "th", "泰國", "泰国"]):
        return {
            "country": "泰國 (Thailand)",
            "currency": "THB",
            "general_exemption": "20,000 泰銖 (自用隨身行李物品免稅總額)",
            "alcohol_limit": "1.0 公升酒類 (限年滿 20 歲旅客)",
            "tobacco_limit": "捲菸 200 支 (1條) 或菸絲 250g。【特別警告】：切勿多人合資集中一人攜帶或幫同團代拿，超額會被當場處以數萬至數十萬泰銖鉅額罰款！",
            "vapes_e_cigarettes": "【嚴正警告 - 絕對禁止】泰國法律嚴格禁止電子煙、加熱菸與煙油！入境查獲最高面臨 10 年監禁或高額罰金！",
            "cash_limit": "外幣等值 USD $15,000 以上需向泰國海關申報",
            "meat_quarantine": "嚴格禁止攜帶未滅菌肉品、香腸、豬肉乾（防範非洲豬瘟，違者遭逮捕起訴重罰）",
            "otc_medicine": "自用常備藥限 30 天用量；含精神管制成分藥品需事先向泰國 FDA 線上申請許可",
            "red_channel_golden_rule": "若有疑慮，入境行李提取後走「Goods to Declare (Red Channel)」紅線主動詢問。",
        }
    elif any(k in dest for k in ["vietnam", "vn", "越南"]):
        return {
            "country": "越南 (Vietnam)",
            "currency": "VND",
            "general_exemption": "10,000,000 越南盾 (約等值 400 美元)",
            "alcohol_limit": "酒精度 20% 以上限 1.5L；20% 以下限 2.0L；啤酒限 3.0L",
            "tobacco_limit": "捲菸 200 支 或雪茄 20 支 或菸絲 250g (年滿 18 歲)",
            "vapes_e_cigarettes": "越南海關高度管制電子煙，強烈建議旅客不要攜帶入境外免爭議",
            "cash_limit": "等值 5,000 美元外幣或 1,500 萬越南盾現鈔需主動申報",
            "meat_quarantine": "嚴禁未經檢疫之生鮮肉類、肉製品及未加工農產品",
            "otc_medicine": "個人自用藥品需附有效處方或包裝，管制藥品不得超過 7 日用量",
            "red_channel_golden_rule": "超額外幣與貴重物品填寫申報單走申報通道，保障合法權益。",
        }
    elif any(k in dest for k in ["philippines", "ph", "菲律賓", "菲律宾"]):
        return {
            "country": "菲律賓 (Philippines)",
            "currency": "PHP",
            "general_exemption": "10,000 菲律賓披索 (PHP)",
            "alcohol_limit": "2 瓶 (每瓶容量不超過 1 公升免稅)",
            "tobacco_limit": "捲菸 400 支 (2條) 或雪茄 50 支 或菸草 250g",
            "vapes_e_cigarettes": "僅限極少量自用，菲律賓公共場所全面禁止吸食電子煙",
            "cash_limit": "披索現鈔超過 50,000 PHP 需中央銀行許可；外幣等值 USD $10,000 需申報",
            "meat_quarantine": "嚴禁攜帶未經農業部核可之生鮮與加工肉品（包括豬肉罐頭或肉乾）",
            "otc_medicine": "自用常備藥限旅行天數合理用量，處方藥請隨身攜帶英文醫師證明",
            "red_channel_golden_rule": "於 e-Travel 系統或海關申報單如實申報，海關即開單計稅放行。",
        }
    elif any(k in dest for k in ["malaysia", "my", "馬來西亞", "马来西亚"]):
        return {
            "country": "馬來西亞 (Malaysia)",
            "currency": "MYR",
            "general_exemption": "RM 1,000 馬幣 (需離境超過 72 小時)",
            "alcohol_limit": "1.0 公升酒類 (限年滿 21 歲)",
            "tobacco_limit": "捲菸 200 支 (1條) 或雪茄 50 支 或菸絲 225g",
            "vapes_e_cigarettes": "部分州全面禁止電子煙，攜帶含尼古丁煙油可能觸犯毒藥法，強烈建議避免攜帶",
            "cash_limit": "等值 USD $10,000 以上貨幣需填 Customs Form 22 申報",
            "meat_quarantine": "清真法規與檢疫嚴格管制，嚴禁攜帶豬肉相關製品及生鮮肉品",
            "otc_medicine": "自用藥品限 1 個月內用量，處方藥品應隨身備妥英文診斷證明書",
            "red_channel_golden_rule": "走紅線通道申報繳納適用稅捐，手續完備即獲放行。",
        }
    elif any(k in dest for k in ["france", "fr", "法國", "法国"]):
        return {
            "country": "法國 (France / EU)",
            "currency": "EUR",
            "general_exemption": "€430 (搭乘民航空中交通入境之個人物品免稅額)",
            "alcohol_limit": "烈酒 (>22%) 1.0L 或加強酒 2.0L；非氣泡葡萄酒 4.0L；啤酒 16.0L",
            "tobacco_limit": "捲菸 200 支 或雪茄 50 支 或菸草 250g (年滿 17 歲)",
            "vapes_e_cigarettes": "允許個人少量自用攜帶，符合歐盟安全性規定",
            "cash_limit": "€10,000 等值現鈔需向法國海關申報",
            "meat_quarantine": "嚴格禁止從非歐盟國家攜帶肉類、乳酪、肉醬及乳製品入境",
            "otc_medicine": "個人醫療常備藥限 3 個月內用量，需具備原廠包裝與英文醫師處方",
            "red_channel_golden_rule": "主動向海關申報超出額度之精品或酒類，現場開單補稅即可。",
        }
    elif any(k in dest for k in ["australia", "au", "澳洲", "澳大利亚"]):
        return {
            "country": "澳洲 (Australia)",
            "currency": "AUD",
            "general_exemption": "AUD $900 (年滿18歲) / AUD $450 (未滿18歲)",
            "alcohol_limit": "2.25 公升酒類 (限年滿 18 歲)",
            "tobacco_limit": "【極度嚴格】僅限 1 包已開封香菸（最多 25 支）或 25g 菸草製品！超額全部需申報繳稅！",
            "vapes_e_cigarettes": "【嚴正警告】澳洲實施嚴格電子煙進口禁令，非經醫療處方與許可嚴禁攜帶電子煙設備及煙油入境！",
            "cash_limit": "AUD $10,000 等值現鈔需向 AUSTRAC 填單申報 (無上限但必須申報)",
            "meat_quarantine": "【全球最嚴格生物檢疫】任何肉類、蛋類、中藥材、種子、堅果、木製品、新鮮蔬果必須 100% 誠實申報！未申報查獲將面臨最高 AUD $6,260 罰款或取消簽證遣返！",
            "medicine": "個人自用藥品限最多 3 個月用量，必須備妥英文處方箋或醫師信函",
            "red_channel_golden_rule": "「若有疑慮，務必申報 (If in doubt, declare it)」！在入境卡上打叉勾選申報，海關就算沒收也不會處以罰款！",
        }
    elif any(k in dest for k in ["spain", "es", "西班牙"]):
        return {
            "country": "西班牙 (Spain / EU)",
            "currency": "EUR",
            "general_exemption": "€430 (搭乘航空個人免稅總額)",
            "alcohol_limit": "烈酒 (>22%) 1.0L 或加強酒 2.0L；葡萄酒 4.0L；啤酒 16.0L",
            "tobacco_limit": "捲菸 200 支 或雪茄 50 支 或菸草 250g",
            "vapes_e_cigarettes": "允許個人自用少量攜帶",
            "cash_limit": "€10,000 等值現鈔需向海關申報",
            "meat_quarantine": "嚴禁自非歐盟境外攜帶任何肉製品及乳製品入境",
            "otc_medicine": "自用常備藥品限個人旅行合理用量，需具備原處方標籤",
            "red_channel_golden_rule": "於海關申報櫃檯主動出示，誠實繳納稅款後放行。",
        }
    elif any(k in dest for k in ["greece", "gr", "希臘", "希腊"]):
        return {
            "country": "希臘 (Greece / EU)",
            "currency": "EUR",
            "general_exemption": "€430 (搭乘民航班機入境免稅額)",
            "alcohol_limit": "烈酒 (>22%) 1.0L 或加強酒 2.0L；葡萄酒 4.0L；啤酒 16.0L",
            "tobacco_limit": "捲菸 200 支 或雪茄 50 支 或菸草 250g",
            "vapes_e_cigarettes": "允許自用少量攜帶",
            "cash_limit": "€10,000 等值貨幣需向海關申報",
            "meat_quarantine": "嚴格禁止從非歐盟國家攜帶肉類及乳製品",
            "otc_medicine": "自用藥物限個人旅行期間合理劑量，處方藥請攜帶英文處方箋",
            "red_channel_golden_rule": "走紅線通道完成申報手續即可順利通關。",
        }
    elif any(k in dest for k in ["us", "usa", "united states", "美國"]):
        return {
            "country": "美國 (United States)",
            "currency": "USD",
            "general_exemption": "USD $800 (美國居民) / USD $100 (非居民訪客禮物額度)",
            "alcohol_limit": "1.0 公升酒類 (限年滿 21 歲免稅)",
            "tobacco_limit": "捲菸 200 支 (1 條) 及 100 支非古巴雪茄",
            "vapes_e_cigarettes": "允許自用電子煙，電池必須放置於隨身隨行行李，禁止託運",
            "cash_limit": "USD $10,000 等值貨幣 (需向 CBP 提交 FinCEN 105 表格主動申報)",
            "meat_quarantine": "大多數生鮮肉製品、水果、未處理種子嚴格禁止攜入 (違者罰款最高 $10,000)；商業包裝無肉之純鳳梨酥/糕餅可攜入 (需在 CBP 申報單誠實申報食物類)",
            "otc_medicine": "自用常備藥最多 90 天用量，需具備完整原廠標籤與英文處方箋",
            "red_channel_golden_rule": "在 CBP 申報單 6059B 或 MPC 手機 App 上誠實勾選，海關查驗無違禁即放行，絕不罰款！",
        }
    elif any(k in dest for k in ["uk", "united kingdom", "英國"]):
        return {
            "country": "英國 (United Kingdom)",
            "currency": "GBP",
            "general_exemption": "£390 (搭乘民航商業機個人免稅額)",
            "alcohol_limit": "啤酒 42L、葡萄酒 18L，及烈酒 (>22%) 4L 或加強酒 9L",
            "tobacco_limit": "捲菸 200 支 或雪茄 50 支 或菸草 250g",
            "vapes_e_cigarettes": "允許個人自用電子煙（煙油容量符合規定）",
            "cash_limit": "£10,000 等值貨幣需向英國稅務海關總署 HMRC 申報",
            "meat_quarantine": "禁止從非歐盟國家攜帶任何肉類、肉製品或奶製品入境",
            "otc_medicine": "個人自用合理用量 (一般 3 個月)，需原包裝及英文醫師處方",
            "red_channel_golden_rule": "走「Red Channel (Goods to Declare)」如實申報，海關計稅繳款後立即放行。",
        }
    elif any(k in dest for k in ["hong kong", "hk", "香港"]):
        return {
            "country": "香港 (Hong Kong)",
            "currency": "HKD",
            "general_exemption": "訪港旅客攜帶之個人自用合理行李物品免稅",
            "alcohol_limit": "1.0 公升酒精濃度 30% 以上烈酒 (年滿 18 歲免稅)；葡萄酒及啤酒無關稅",
            "tobacco_limit": "【極度嚴格】僅限捲菸 19 支 或雪茄 1 支 或菸草 25g (超額一律須申報納稅)",
            "vapes_e_cigarettes": "【嚴正警告 - 絕對禁止】香港已立法全面禁止進口、推廣、製造、售賣電子煙與加熱菸，違者最高可罰款 5 萬港元及監禁 6 個月！",
            "cash_limit": "等值 12 萬港元貨幣需使用紅線通道向海關申報",
            "meat_quarantine": "嚴禁攜帶未煮熟生鮮肉類與家禽入港",
            "otc_medicine": "受管制藥物需具備香港衛生署許可或合法醫生處方箋",
            "red_channel_golden_rule": "只要走紅通道（Red Channel）申報，海關即依規辦理，不會受到未申報懲罰。",
        }
    else:
        return {
            "country": destination_country,
            "currency": "Local",
            "general_rule": "Please consult local customs service or declaration desk upon arrival.",
            "red_channel_golden_rule": "Always declare non-standard personal items at the Red Channel upon arrival.",
        }


# Climatological & seasonal database for the 18 global destinations
DESTINATION_CLIMATE_DATA = {
    "taiwan": {
        "country_zh": "臺灣 (Taipei / Taoyuan)",
        "spring": {"temp": "19°C ~ 26°C", "condition": "春暖花開、偶有春雨", "icon": "🌤️", "rain": "35%", "tips": ["建議穿著薄長袖搭配輕薄夾克", "隨身備折疊雨傘應對午後偶陣雨", "室內冷氣充足，備薄圍巾或罩衫"]},
        "summer": {"temp": "28°C ~ 35°C", "condition": "炎熱高溫、午後雷陣雨", "icon": "☀️", "rain": "50%", "tips": ["建議穿著純棉透氣短袖與排汗衣物", "必備高防曬係數防曬乳、遮陽帽與墨鏡", "午後常有短時強降雨，雨具不可少"]},
        "autumn": {"temp": "22°C ~ 28°C", "condition": "秋高氣爽、涼爽舒適", "icon": "🌤️", "rain": "25%", "tips": ["氣候宜人，建議長袖襯衫搭配薄風衣", "早晚稍有微風，採洋蔥式穿搭最合適", "隨身備水壺適時補充水分"]},
        "winter": {"temp": "14°C ~ 20°C", "condition": "陰涼濕冷、東北季風迎風面", "icon": "🌧️", "rain": "45%", "tips": ["建議攜帶防風防潑水保暖外套或輕羽絨", "北部地區多陰雨，隨身折疊雨傘不可少", "皮膚易乾燥者可備基礎保濕乳液"]},
    },
    "japan": {
        "country_zh": "日本 (Tokyo / Osaka)",
        "spring": {"temp": "10°C ~ 20°C", "condition": "櫻花季溫和宜人、日夜溫差大", "icon": "🌸", "rain": "30%", "tips": ["早晚溫差顯著，建議採洋蔥式穿搭", "隨身攜帶輕羽絨或防風風衣", "氣候相對乾燥，建議準備保濕乳液與護唇膏"]},
        "summer": {"temp": "24°C ~ 33°C", "condition": "潮濕溫熱、偶有夏日雷陣雨", "icon": "☀️", "rain": "40%", "tips": ["穿著透氣涼爽排汗衣物", "必備遮陽傘、防曬乳與隨身小風扇", "進入室內冷氣房可備一件薄針織衫"]},
        "autumn": {"temp": "13°C ~ 22°C", "condition": "紅葉季涼爽宜人、天高氣爽", "icon": "🍁", "rain": "25%", "tips": ["建議薄毛衣搭配夾克或大衣", "非常適合戶外觀光，穿著舒適健走鞋", "日本室內暖氣漸開，洋蔥式穿法最方便"]},
        "winter": {"temp": "3°C ~ 12°C", "condition": "晴朗乾燥、寒風刺骨", "icon": "❄️", "rain": "15%", "tips": ["必備防風厚羽絨外套、保暖發熱衣", "準備毛帽、圍巾、手套防寒配件", "日本冬季室內乾燥，強烈建議攜帶強效面霜與人工淚液"]},
    },
    "korea": {
        "country_zh": "韓國 (Seoul / Incheon)",
        "spring": {"temp": "8°C ~ 19°C", "condition": "春風拂面、日夜溫差偏大", "icon": "🌸", "rain": "25%", "tips": ["早晚偏涼，準備厚風衣或夾克", "春季偶有沙塵霧霾，建議隨身佩戴防護口罩", "多喝水並備高保濕護膚品"]},
        "summer": {"temp": "22°C ~ 30°C", "condition": "梅雨季溫熱潮濕、降雨機率高", "icon": "🌧️", "rain": "60%", "tips": ["必備抗風雨傘與防水便鞋", "穿著快乾透氣短袖衣服", "進入室內商場需備薄外套防止冷氣受寒"]},
        "autumn": {"temp": "10°C ~ 21°C", "condition": "銀杏楓葉季、乾燥爽朗", "icon": "🍁", "rain": "20%", "tips": ["首爾秋景極佳，準備時尚長版風衣或大衣", "日夜溫差可達10度以上，務必採多層次洋蔥穿搭", "氣候乾燥，護唇膏與身體乳必備"]},
        "winter": {"temp": "-6°C ~ 4°C", "condition": "嚴寒降雪、刺骨乾冷", "icon": "❄️", "rain": "15%", "tips": ["務必攜帶長版抗寒羽絨大衣 (Padding)", "必備極暖發熱衣褲、羊毛襪與防滑雪靴", "耳罩、手套、保暖圍巾不可或缺"]},
    },
    "canada": {
        "country_zh": "加拿大 (Vancouver / Toronto)",
        "spring": {"temp": "6°C ~ 16°C", "condition": "微涼漸暖、偶有春雨", "icon": "🌱", "rain": "40%", "tips": ["建議穿著防風防潑水夾克搭配針織衫", "隨身備折疊雨傘", "多倫多早春仍可能飄雪，保暖衣物需備齊"]},
        "summer": {"temp": "15°C ~ 26°C", "condition": "陽光溫和、乾爽舒適", "icon": "☀️", "rain": "20%", "tips": ["白天溫暖舒適，可穿短袖長褲", "日落後氣溫驟降，隨身攜帶薄外套", "戶外紫外線強，備墨鏡與防曬霜"]},
        "autumn": {"temp": "7°C ~ 16°C", "condition": "楓葉轉紅、氣溫漸涼", "icon": "🍁", "rain": "45%", "tips": ["溫哥華秋季多雨，防水大衣或風衣不可少", "多倫多秋季較乾涼，穿厚外套或薄羽絨", "備舒適防水健走鞋"]},
        "winter": {"temp": "-8°C ~ 3°C", "condition": "寒冷下雪、積雪冰凍", "icon": "❄️", "rain": "50%", "tips": ["極地防寒等級厚羽絨大衣與保暖內搭", "防水防滑雪靴避免結冰滑倒", "毛帽、保暖手套與護臉圍巾為必備裝備"]},
    },
    "italy": {
        "country_zh": "義大利 (Rome / Milan)",
        "spring": {"temp": "12°C ~ 22°C", "condition": "地中海暖陽、溫和舒適", "icon": "🌤️", "rain": "30%", "tips": ["白天宜人，薄長袖搭休閒西裝或風衣", "進入教堂景點需注意著裝規範（不可露肩膝）", "穿著耐走的防滑平底鞋以便行走石板路"]},
        "summer": {"temp": "22°C ~ 34°C", "condition": "烈日晴空、乾燥炎熱", "icon": "☀️", "rain": "10%", "tips": ["陽光極為強烈，務必配戴 UV400 墨鏡與寬簷遮陽帽", "自備環保水壺可於羅馬街頭公共噴泉取水飲用", "高防曬乳液與曬後舒緩噴霧必備"]},
        "autumn": {"temp": "13°C ~ 23°C", "condition": "秋高氣爽、偶有地中海陣雨", "icon": "⛅", "rain": "40%", "tips": ["早晚微涼，準備皮衣、薄大衣或風衣", "隨身備輕便折疊傘", "採洋蔥式穿法應對溫差"]},
        "winter": {"temp": "5°C ~ 14°C", "condition": "溫和微雨、北部偏冷", "icon": "🌧️", "rain": "45%", "tips": ["羅馬溫和只需大衣夾克；米蘭較冷需厚毛衣與羽絨外套", "防雨外套與舒適短靴", "隨身保濕護理"]},
    },
    "netherlands": {
        "country_zh": "荷蘭 (Amsterdam)",
        "spring": {"temp": "6°C ~ 15°C", "condition": "鬱金香花季、多風偏涼", "icon": "🌷", "rain": "35%", "tips": ["荷蘭海風強勁，必備高防風防潑水外套", "建議穿著保暖毛衣採洋蔥式穿搭", "隨身備傘，留意春季陣風"]},
        "summer": {"temp": "14°C ~ 23°C", "condition": "涼爽宜人、日照極長", "icon": "🌤️", "rain": "30%", "tips": ["夏季極度舒適，白天短袖薄長袖皆宜", "晚間氣溫降至14度左右，務必備一件外套", "日照可達晚間十點，備墨鏡與防曬"]},
        "autumn": {"temp": "8°C ~ 16°C", "condition": "多風多雨、秋意濃郁", "icon": "🍂", "rain": "50%", "tips": ["抗風防水的連帽大衣為最佳選擇", "運河邊風大，不宜使用輕薄雨傘，建議著防雨連帽衫", "防滑健走鞋以便騎乘單車或步行"]},
        "winter": {"temp": "1°C ~ 7°C", "condition": "陰冷潮濕、寒風陣陣", "icon": "❄️", "rain": "45%", "tips": ["厚保暖大衣、保暖發熱內衣", "防風毛帽與圍巾保暖頭頸部", "氣候潮濕防寒需著重防風防水功能"]},
    },
    "singapore": {
        "country_zh": "新加坡 (Singapore)",
        "spring": {"temp": "25°C ~ 32°C", "condition": "熱帶島嶼、午後雷陣雨", "icon": "🌦️", "rain": "45%", "tips": ["透氣吸汗短袖短褲", "室內商場與地鐵冷氣非常強，建議自備薄長袖罩衫", "高防曬係數防曬乳、抗風晴雨兩用傘必備"]},
        "summer": {"temp": "26°C ~ 33°C", "condition": "陽光充沛、濕熱高溫", "icon": "☀️", "rain": "40%", "tips": ["輕薄透氣棉麻衣物", "隨身準備小毛巾與保濕吸油紙", "補充足夠水分防中暑"]},
        "autumn": {"temp": "25°C ~ 32°C", "condition": "常年如夏、微風陣雨", "icon": "⛅", "rain": "50%", "tips": ["隨身備折疊雨傘", "防滑好走的涼鞋或休閒鞋", "防蚊液與防曬用品"]},
        "winter": {"temp": "24°C ~ 31°C", "condition": "東北季候風、降雨較頻繁", "icon": "🌧️", "rain": "60%", "tips": ["降雨頻率偏高，備防水包袋或雨具", "衣物以易乾材質為主", "進出冷氣空間注意溫差調節"]},
    },
    "thailand": {
        "country_zh": "泰國 (Bangkok / Chiang Mai)",
        "spring": {"temp": "27°C ~ 36°C", "condition": "熱季酷暑、晴朗炎熱 (潑水節季節)", "icon": "🔥", "rain": "20%", "tips": ["氣溫極高，穿著寬鬆透氣純棉衣物", "必備高係數防曬乳、太陽眼鏡與遮陽帽", "參訪寺廟需自備覆蓋雙肩與膝蓋的長褲/長裙"]},
        "summer": {"temp": "25°C ~ 33°C", "condition": "雨季來臨、午後常有強雷陣雨", "icon": "⛈️", "rain": "65%", "tips": ["午後雷陣雨來得快去得快，備防風雨傘", "穿著防滑快乾鞋履或涼鞋", "備防蚊液以防登革熱"]},
        "autumn": {"temp": "24°C ~ 32°C", "condition": "雨季尾聲、氣溫漸趨穩定", "icon": "🌤️", "rain": "45%", "tips": ["透氣吸汗夏季穿著", "薄長袖外套防室內強烈冷氣", "戶外備防蚊防曬用品"]},
        "winter": {"temp": "22°C ~ 32°C", "condition": "涼季氣候最佳、乾燥舒適宜人", "icon": "☀️", "rain": "10%", "tips": ["曼谷全年最舒適旅遊季節，早晚微涼", "清邁山區早晚偏冷，需備一件薄外套或夾克", "非常適合戶外觀光，防曬保濕依然不可少"]},
    },
    "vietnam": {
        "country_zh": "越南 (Hanoi / Ho Chi Minh)",
        "spring": {"temp": "20°C ~ 28°C", "condition": "春風暖和、北越偶有細雨", "icon": "🌱", "rain": "35%", "tips": ["北越河內需薄外套，南越胡志明市全年皆夏穿短袖", "準備折疊傘與防滑便鞋", "自備防蚊液"]},
        "summer": {"temp": "26°C ~ 35°C", "condition": "炎熱多雨、季風降水", "icon": "🌦️", "rain": "60%", "tips": ["透氣排汗快乾衣物", "隨身備抗風雨傘與防水隨身包", "強效防曬與充足補水"]},
        "autumn": {"temp": "22°C ~ 29°C", "condition": "河內秋高氣爽、氣候怡人", "icon": "🌤️", "rain": "30%", "tips": ["河內秋季為黃金旅遊期，舒適宜人", "薄長袖襯衫搭休閒長褲", "備墨鏡防曬用品"]},
        "winter": {"temp": "14°C ~ 22°C", "condition": "北越偏冷陰涼、南越依舊溫暖", "icon": "⛅", "rain": "25%", "tips": ["前往北越（河內、下龍灣）務必帶保暖夾克或風衣", "南越胡志明市仍是熱帶氣候只需夏季衣物", "北越濕冷體感明顯，採洋蔥式穿法"]},
    },
    "philippines": {
        "country_zh": "菲律賓 (Manila / Cebu / Boracay)",
        "spring": {"temp": "25°C ~ 34°C", "condition": "乾季炎熱、陽光普照海島極佳", "icon": "☀️", "rain": "15%", "tips": ["海島度假必備泳裝、防曬水母衣與遮陽帽", "高係數海洋友善防曬乳", "墨鏡與防水手機袋必備"]},
        "summer": {"temp": "25°C ~ 32°C", "condition": "西南季風雨季、偶有颱風", "icon": "⛈️", "rain": "65%", "tips": ["備隨身雨具與防水背包套", "透氣快乾衣物與防滑涼鞋", "備腸胃常用常備藥"]},
        "autumn": {"temp": "24°C ~ 31°C", "condition": "季風交替、陣雨漸歇", "icon": "🌦️", "rain": "50%", "tips": ["輕便休閒服裝", "隨身防蚊噴霧不可少", "備一件輕薄長袖對應冷氣房"]},
        "winter": {"temp": "23°C ~ 31°C", "condition": "涼爽乾季、最舒適避冬旅遊期", "icon": "🌤️", "rain": "20%", "tips": ["全年最佳旅遊季節，海風涼爽", "白天短袖短褲，晚上海風較涼備薄罩衫", "防曬保濕用品隨身攜帶"]},
    },
    "malaysia": {
        "country_zh": "馬來西亞 (Kuala Lumpur / Penang)",
        "spring": {"temp": "24°C ~ 33°C", "condition": "典型熱帶雨林氣候、午後陣雨", "icon": "🌦️", "rain": "50%", "tips": ["寬鬆吸汗棉麻衣物", "進出清真寺需穿著長袖長褲，女性自備絲巾包裹頭部", "雨具不可離身"]},
        "summer": {"temp": "24°C ~ 33°C", "condition": "溫熱多雲、陽光強烈", "icon": "☀️", "rain": "40%", "tips": ["高防曬霜、太陽眼鏡、折疊傘", "吉隆坡各大商場冷氣極強，務必備長袖外套", "充足補水防中暑"]},
        "autumn": {"temp": "24°C ~ 32°C", "condition": "季風降雨、午後多雷陣雨", "icon": "⛈️", "rain": "60%", "tips": ["抗風耐用雨傘、防水鞋款", "穿著排汗快乾衣服", "隨身備防蚊液"]},
        "winter": {"temp": "23°C ~ 32°C", "condition": "東北季候風、東海岸多雨西海岸穩定", "icon": "⛅", "rain": "45%", "tips": ["西馬（吉隆坡/檳城）氣候宜人，穿短袖即可", "隨身攜帶防曬用品與薄開衫", "備常用藥品適應當地辛辣飲食"]},
    },
    "france": {
        "country_zh": "法國 (Paris)",
        "spring": {"temp": "9°C ~ 18°C", "condition": "春風微拂、早晚偏涼多風", "icon": "🌸", "rain": "35%", "tips": ["經典法式長版風衣、薄毛衣是標配", "早晚氣溫偏低，隨身備圍巾防風", "穿著耐走休閒鞋漫步巴黎街頭"]},
        "summer": {"temp": "17°C ~ 27°C", "condition": "日照極長、乾爽宜人偶有熱浪", "icon": "☀️", "rain": "25%", "tips": ["短袖搭配薄外套，日落後氣溫微涼", "巴黎很多飯店沒有冷氣，留意熱浪來襲資訊", "紫外線強，備防曬乳與太陽眼鏡"]},
        "autumn": {"temp": "10°C ~ 18°C", "condition": "落葉繽紛、陰涼微雨", "icon": "🍂", "rain": "40%", "tips": ["建議厚風衣、毛呢大衣與皮質靴子", "隨身折疊雨傘", "採洋蔥式穿搭以因應室內暖氣"]},
        "winter": {"temp": "3°C ~ 8°C", "condition": "陰冷潮濕、偶有飄雪", "icon": "❄️", "rain": "45%", "tips": ["厚毛呢大衣或羽絨外套、羊毛圍巾與手套", "氣候偏濕冷，防風保暖至關重要", "攜帶高保濕面霜防皮膚乾裂"]},
    },
    "australia": {
        "country_zh": "澳洲 (Sydney / Melbourne) [南半球季節相反]",
        "spring": {"temp": "14°C ~ 23°C", "condition": "（9-11月）春光明媚、微風吹拂", "icon": "🌤️", "rain": "25%", "tips": ["南半球季節與台灣相反！春季氣候舒適", "早晚偏涼，薄長袖搭配夾克外套", "澳洲臭氧層薄紫外線極強，務必塗抹高係數防曬"]},
        "summer": {"temp": "19°C ~ 28°C", "condition": "（12-2月）炎夏陽光耀眼、海灘度假季", "icon": "☀️", "rain": "20%", "tips": ["極度強烈的紫外線，必備防曬帽、墨鏡與抗UV防曬乳", "夏季清涼短袖，前往海灘備泳裝與遮陽配備", "墨爾本一天四季，隨身仍需備防風薄外套"]},
        "autumn": {"temp": "13°C ~ 22°C", "condition": "（3-5月）秋高氣爽、氣候宜人清爽", "icon": "🍁", "rain": "30%", "tips": ["溫暖舒適，薄毛衣搭配夾克", "適合葡萄園與戶外健行，著健走好鞋", "早晚溫差漸大，洋蔥式穿法最合適"]},
        "winter": {"temp": "8°C ~ 17°C", "condition": "（6-8月）涼爽微寒、早晚低溫", "icon": "🌬️", "rain": "35%", "tips": ["冬季不常下雪但早晚偏凍，需大衣或羽絨外套", "室內少有集中暖氣，備好保暖發熱衣物", "墨爾本風大需防風連帽外套"]},
    },
    "spain": {
        "country_zh": "西班牙 (Madrid / Barcelona)",
        "spring": {"temp": "11°C ~ 22°C", "condition": "春風暖陽、日照逐漸增加", "icon": "🌤️", "rain": "30%", "tips": ["穿著薄長袖搭配輕薄夾克或牛仔外套", "早晚溫差約10度，洋蔥式穿著必備", "舒適平底鞋以便在老城區石磚路漫步"]},
        "summer": {"temp": "21°C ~ 34°C", "condition": "烈日晴空、乾燥酷熱", "icon": "☀️", "rain": "10%", "tips": ["馬德里夏季極度乾燥酷熱，務必高防曬、戴墨鏡與草帽", "午間氣溫最高，可安排室內博物館行程避暑", "自備水壺隨時多補水，備滋潤護唇膏"]},
        "autumn": {"temp": "13°C ~ 23°C", "condition": "秋日宜人、陽光和煦", "icon": "🍂", "rain": "35%", "tips": ["氣候相當舒服，薄針織配風衣", "早晚偏涼，隨身備圍巾", "巴塞隆納海風吹拂較濕潤"]},
        "winter": {"temp": "5°C ~ 14°C", "condition": "馬德里乾冷、巴塞隆納溫和微涼", "icon": "⛅", "rain": "25%", "tips": ["馬德里海拔高冬季偏冷，需厚大衣與毛衣", "巴塞隆納地中海型氣候，一般夾克風衣即可", "隨身備面霜防乾裂"]},
    },
    "greece": {
        "country_zh": "希臘 (Athens / Santorini)",
        "spring": {"temp": "13°C ~ 22°C", "condition": "愛琴海春光和煦、觀光人潮舒適", "icon": "🌤️", "rain": "20%", "tips": ["白天氣溫舒適，薄長袖加防風小外套", "愛琴海跳島風浪較大，易暈船者隨身備暈船藥", "石階地形多，防滑健走鞋不可少"]},
        "summer": {"temp": "24°C ~ 35°C", "condition": "愛琴海豔陽高照、極度乾燥晴朗", "icon": "☀️", "rain": "5%", "tips": ["地中海無雲烈日，強烈防曬乳、遮陽帽、太陽眼鏡三件套必備", "白色/藍色系透氣棉麻服裝，拍照亮眼又透氣散熱", "島嶼海風強（熔爐風 Meltemi），固定帽子防吹飛"]},
        "autumn": {"temp": "16°C ~ 25°C", "condition": "秋高氣爽、海水依然溫暖宜人", "icon": "⛅", "rain": "25%", "tips": ["秋季非常適合慢遊古蹟，舒適不悶熱", "薄外套應對日落後的涼風", "備保濕護膚用品"]},
        "winter": {"temp": "8°C ~ 15°C", "condition": "地中海溫和多雨、島嶼進入淡季", "icon": "🌧️", "rain": "45%", "tips": ["雅典氣候溫和微雨，毛呢大衣與防雨連帽衫", "愛琴海島嶼冬季渡輪班次減少，注意行程彈性", "折疊雨傘隨身帶"]},
    },
    "usa": {
        "country_zh": "美國 (New York / Los Angeles)",
        "spring": {"temp": "10°C ~ 20°C", "condition": "紐約春寒漸消、加州溫暖少雨", "icon": "🌤️", "rain": "30%", "tips": ["東岸紐約日夜溫差大，備風衣夾克", "西岸洛杉磯陽光充足早晚微涼，薄外套即可", "隨身保濕乳液與舒適便鞋"]},
        "summer": {"temp": "20°C ~ 31°C", "condition": "東岸溫熱偶雨、西岸乾燥艷陽", "icon": "☀️", "rain": "25%", "tips": ["夏季短袖涼爽衣物", "西岸陽光極強，必備太陽眼鏡與高防曬霜", "室內冷氣偏低，進出隨身攜帶薄長袖"]},
        "autumn": {"temp": "11°C ~ 21°C", "condition": "東岸秋楓盛開、天高氣爽", "icon": "🍁", "rain": "25%", "tips": ["非常適合觀光，長袖長褲搭風衣或皮衣", "多層次洋蔥式穿法最合適", "氣候乾燥備護唇膏"]},
        "winter": {"temp": "-2°C ~ 8°C", "condition": "東岸嚴寒暴雪、西岸加州舒適微雨", "icon": "❄️", "rain": "35%", "tips": ["東岸紐約需專業抗風防雪長版羽絨外套與保暖手套", "加州洛杉磯冬季溫和僅需中等厚度夾克外套", "美式室內暖氣充足，內裡穿薄長袖外搭厚大衣便於脫穿"]},
    },
    "uk": {
        "country_zh": "英國 (London)",
        "spring": {"temp": "7°C ~ 16°C", "condition": "春風多變、陰晴不定偶有短雨", "icon": "🌦️", "rain": "45%", "tips": ["英倫經典風衣搭配針織衫是標配", "英國天氣瞬息萬變，折疊傘或防潑水外套隨身帶", "多層次穿搭方便穿脫"]},
        "summer": {"temp": "15°C ~ 25°C", "condition": "涼爽宜人、夏季日照長", "icon": "🌤️", "rain": "30%", "tips": ["避暑勝地，白天穿短袖或薄襯衫非常舒服", "晚上氣溫降至14度左右，備一件夾克或針織開衫", "倫敦多數公車地鐵無空調，備手帕或小扇子"]},
        "autumn": {"temp": "9°C ~ 16°C", "condition": "秋意濃郁、落葉綿綿細雨", "icon": "🍂", "rain": "50%", "tips": ["保暖毛呢大衣、風衣、羊毛圍巾必備", "防水短靴好走又保暖", "隨身攜帶抗風雨傘"]},
        "winter": {"temp": "3°C ~ 9°C", "condition": "陰濕寒冷、日照短早落日", "icon": "🌧️", "rain": "50%", "tips": ["厚大衣或羽絨服、圍巾、保暖手套防陰冷", "下午四點天黑，建議攜帶保溫瓶裝熱水暖身", "保濕乳霜防寒風吹拂造成的肌膚乾燥"]},
    },
    "hong kong": {
        "country_zh": "香港 (Hong Kong)",
        "spring": {"temp": "19°C ~ 26°C", "condition": "潮濕溫暖、霧氣濛濛偶有小雨", "icon": "🌫️", "rain": "45%", "tips": ["春季濕度極高，建議穿著透氣排汗衣物", "隨身攜帶折疊傘應對細雨", "室內冷氣偏冷，自備薄開衫"]},
        "summer": {"temp": "27°C ~ 33°C", "condition": "酷熱潮濕、午後雷陣雨或熱帶氣旋", "icon": "⛈️", "rain": "65%", "tips": ["純棉透氣涼感短袖短褲", "必備抗UV晴雨兩用傘與防曬霜", "商場室內冷氣強勁，備一件薄罩衫預防感冒"]},
        "autumn": {"temp": "22°C ~ 29°C", "condition": "晴空萬里、乾爽怡人（全年生態最佳）", "icon": "🌤️", "rain": "20%", "tips": ["香港最佳旅遊季節，涼風習習非常舒服", "薄長袖襯衫或T恤即可", "非常適合太平山夜景與街頭漫步，備健走鞋"]},
        "winter": {"temp": "14°C ~ 20°C", "condition": "乾爽微涼、氣候溫和舒適", "icon": "⛅", "rain": "15%", "tips": ["早晚微涼，準備薄毛衣或休閒外套", "不需要厚重羽絨衣，輕便夾克即可應對", "皮膚易乾燥者可備隨身護手霜"]},
    },
}


def get_destination_weather(
    destination: str,
    departure_date: str = "",
    return_date: str = "",
) -> Dict[str, Any]:
    """Provides destination weather forecast, temperature, and tailored baggage packing suggestions.

    Args:
        destination: Destination country or city name.
        departure_date: Departure travel date string (e.g. '2026-10-25' or '2026/11/01').
        return_date: Return travel date string (e.g. '2026-11-05').

    Returns:
        Structured dictionary containing:
        - destination: Target country/city display name.
        - travel_dates: Clean representation of travel span.
        - season: Identified season name (Spring/Summer/Autumn/Winter).
        - temperature_range: Average expected temperature.
        - condition: Concise meteorological description.
        - icon: Visual weather indicator.
        - rain_chance: Estimated precipitation chance.
        - packing_suggestions: Tailored clothing and luggage preparation advice.
    """
    dest_norm = destination.strip().lower()

    # Match key destination profile
    matched_key = "taiwan"
    for key in DESTINATION_CLIMATE_DATA.keys():
        if key in dest_norm:
            matched_key = key
            break
    else:
        # Check Chinese translations
        if any(k in dest_norm for k in ["日本", "東京", "大阪", "japan"]):
            matched_key = "japan"
        elif any(k in dest_norm for k in ["韓國", "首爾", "korea"]):
            matched_key = "korea"
        elif any(k in dest_norm for k in ["加拿大", "canada"]):
            matched_key = "canada"
        elif any(k in dest_norm for k in ["義大利", "意大利", "italy"]):
            matched_key = "italy"
        elif any(k in dest_norm for k in ["荷蘭", "netherlands"]):
            matched_key = "netherlands"
        elif any(k in dest_norm for k in ["新加坡", "singapore"]):
            matched_key = "singapore"
        elif any(k in dest_norm for k in ["泰國", "曼谷", "thailand"]):
            matched_key = "thailand"
        elif any(k in dest_norm for k in ["越南", "河內", "胡志明", "vietnam"]):
            matched_key = "vietnam"
        elif any(k in dest_norm for k in ["菲律賓", "馬尼拉", "philippines"]):
            matched_key = "philippines"
        elif any(k in dest_norm for k in ["馬來西亞", "吉隆坡", "malaysia"]):
            matched_key = "malaysia"
        elif any(k in dest_norm for k in ["法國", "巴黎", "france"]):
            matched_key = "france"
        elif any(k in dest_norm for k in ["澳洲", "雪梨", "墨爾本", "australia"]):
            matched_key = "australia"
        elif any(k in dest_norm for k in ["西班牙", "馬德里", "巴塞隆納", "spain"]):
            matched_key = "spain"
        elif any(k in dest_norm for k in ["希臘", "雅典", "greece"]):
            matched_key = "greece"
        elif any(k in dest_norm for k in ["美國", "紐約", "洛杉磯", "usa", "united states"]):
            matched_key = "usa"
        elif any(k in dest_norm for k in ["英國", "倫敦", "uk", "united kingdom"]):
            matched_key = "uk"
        elif any(k in dest_norm for k in ["香港", "hong kong"]):
            matched_key = "hong kong"

    profile = DESTINATION_CLIMATE_DATA[matched_key]

    # Parse month from departure date or fallback to current month
    month = 10
    if departure_date:
        digits = re.findall(r"\d+", departure_date)
        if len(digits) >= 2:
            # e.g. 2026-10-25 -> 10, or 10/25/2026 -> 10
            possible_month = int(digits[1]) if len(digits[0]) == 4 else int(digits[0])
            if 1 <= possible_month <= 12:
                month = possible_month
    else:
        month = datetime.datetime.now().month

    # Season mapping
    # Note: Australia is Southern Hemisphere, already handled in profile mapping
    if month in [3, 4, 5]:
        season_key = "spring"
        season_name = "春季 (Spring)"
    elif month in [6, 7, 8]:
        season_key = "summer"
        season_name = "夏季 (Summer)"
    elif month in [9, 10, 11]:
        season_key = "autumn"
        season_name = "秋季 (Autumn)"
    else:
        season_key = "winter"
        season_name = "冬季 (Winter)"

    season_data = profile[season_key]

    travel_dates_str = f"{departure_date} 至 {return_date}" if departure_date and return_date else (departure_date or "近期出發")

    return {
        "destination": profile["country_zh"],
        "travel_dates": travel_dates_str,
        "departure_date": departure_date,
        "return_date": return_date,
        "month": month,
        "season": season_name,
        "temperature_range": season_data["temp"],
        "weather_condition": season_data["condition"],
        "icon": season_data["icon"],
        "rain_chance": season_data["rain"],
        "packing_suggestions": season_data["tips"],
    }


# Comprehensive traveler cultural etiquette, legal taboos, and penalty database for 18 countries
DESTINATION_ETIQUETTE_DATA = {
    "japan": {
        "country_zh": "日本 (Japan)",
        "flag": "🇯🇵",
        "overview": "日本極其重視公共秩序、安靜、個人隱私與清潔。對於偷拍、隨地抽菸、亂丟垃圾及特定古蹟私有地的規範具有即席罰款甚至刑罰。",
        "highlight_warnings": [
            "🚫 嚴禁未經同意拍攝藝妓/舞妓（京都祇園私道禁拍違者罰 1 萬日圓）",
            "🚭 戶外道路邊走邊抽菸違法，開罰 2,000 ~ 20,000 日圓，須至指定吸菸區",
            "🚮 街頭少設垃圾桶，隨手亂丟廢棄物最高可處 1,000 萬日圓或拘役",
        ],
        "rules": [
            {
                "title": "肖像權與隱私偷拍嚴禁",
                "icon": "📸",
                "desc": "日本對個人隱私與肖像權保護嚴格，禁止未經同意拍攝路人（尤其是孩童）。京都祇園等私人小巷嚴禁攝影，違者當場罰款 10,000 日圓；偷拍行為將依《迷惑防止條例》移送警局留置詢問。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "罰款 10,000 日圓 / 刑責留置",
            },
            {
                "title": "指定吸菸區與邊走邊抽菸禁令",
                "icon": "🚭",
                "desc": "東京都、大阪市等各大城市多數公共街道為全面禁菸區，嚴禁邊走邊抽菸或隨地棄置菸蒂。抽菸必須前往特定有抽風設備之指定吸菸所 (喫煙所)。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "現場開罰 2,000 ~ 20,000 日圓",
            },
            {
                "title": "垃圾分類與隨身攜帶文化",
                "icon": "🚮",
                "desc": "日本自奧姆真理教事件後街頭極少設置垃圾桶。外帶飲食包裝需隨身帶回飯店分類丟棄；若在街頭隨意棄置垃圾，觸犯《廢棄物處理法》罰金高達 1,000 萬日圓或 5 年以下懲役。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "最高 1,000 萬日圓罰款或拘役",
            },
            {
                "title": "溫泉刺青限制與入浴禮儀",
                "icon": "♨️",
                "desc": "傳統公共浴場與溫泉大多謝絕身上有刺青紋身之旅客（源於傳統黑道關聯）。小型刺青請先以防水膚色貼布遮蔽，或預訂專屬私人獨立湯屋 (貸切風呂)。入池前必須先全身洗淨，毛巾不可浸入溫泉池中。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "拒絕入場或勸離",
            },
            {
                "title": "邊走邊吃 (食べ歩き) 規範",
                "icon": "🍡",
                "desc": "在淺草寺、京都錦市場等傳統商店街，請於購買之店鋪門前或指定食用區吃完再離開，邊走邊吃容易弄髒他人衣物，在日本文化中被視為不合禮節的行為。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "店家規勸",
            },
        ],
    },
    "korea": {
        "country_zh": "韓國 (South Korea)",
        "flag": "🇰🇷",
        "overview": "韓國法律對偷拍犯罪懲處極重，公共場所嚴格禁菸與推行垃圾計量制；長幼用餐禮節分明。",
        "highlight_warnings": [
            "📸 嚴格防範非法偷拍（包含拍攝他人臉孔或在地鐵拍攝，觸犯性暴力處罰法面臨重刑拘禁）",
            "🚭 地鐵出入口 10 公尺、公車站周邊吸菸罰款 10 萬韓元",
            "🚯 垃圾未依一般/食物垃圾分類隨意丟棄，開罰最高 100 萬韓元",
        ],
        "rules": [
            {
                "title": "嚴懲非法偷拍與肖像防範",
                "icon": "📸",
                "desc": "韓國依法強制本土手機拍照發出快門聲。旅客在公共場合切勿未經同意拍攝他人（特別是女性與未成年人），一旦被檢舉將被以現行犯逮捕，觸犯《性暴力犯罪處罰特例法》，面臨巨額罰金、居留調查或驅逐出境。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "拘役調查 / 巨額罰鍰與驅逐出境",
            },
            {
                "title": "公車站與地鐵口禁菸取締",
                "icon": "🚭",
                "desc": "首爾市及各大城市之地鐵站出入口 10 公尺內、公車候車亭周圍、學校周邊皆為法定禁菸區，巡查員頻繁開罰，查獲當場裁處 10 萬韓元罰款。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 10 萬韓元 (約 NT$2,400)",
            },
            {
                "title": "嚴格垃圾分類與計量袋規範",
                "icon": "🚯",
                "desc": "韓國實施垃圾從量制，一般垃圾必須購買各地區專用垃圾袋（Jongnyangje Bag），食物垃圾（음식물쓰레기）需獨立沥乾水分丟棄，隨意棄置外賣餐盒或未分類垃圾可處 10 萬至 100 萬韓元罰款。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "最高罰款 100 萬韓元",
            },
            {
                "title": "長幼用餐與敬酒禮儀",
                "icon": "🍶",
                "desc": "長輩動筷前晚輩不可先動筷；長輩倒酒時晚輩應雙手接杯並雙手托杯回敬，飲酒時身體應微側向一旁，不可正對長輩仰頭飲盡以示尊敬。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "社交失禮",
            },
        ],
    },
    "singapore": {
        "country_zh": "新加坡 (Singapore)",
        "flag": "🇸🇬",
        "overview": "以「罰款之城 (Fine City)」著稱，法治嚴謹且執法徹底，涉及鞭刑與高額罰金；旅客隨意攜帶口香糖、吐痰或亂丟垃圾均會受嚴厲制裁。",
        "highlight_warnings": [
            "🚫 嚴禁攜帶或進口口香糖（醫療處方除外），違者最高罰 10,000 新幣或監禁 1 年",
            "🚯 亂丟垃圾初犯罰款 2,000 新幣，累犯處 10,000 新幣並強制穿「勞動改造服」掃街",
            "🚭 攜帶或使用電子煙最高罰 2,000 新幣，進口最高罰 10,000 新幣或坐牢 6 個月",
        ],
        "rules": [
            {
                "title": "全面禁止口香糖進口與嚼食亂吐",
                "icon": "🚫",
                "desc": "除新加坡衛生科學局核准之藥用/戒菸口香糖外，旅客嚴禁攜帶口香糖入境。亂吐口香糖在公共場所視為重大破壞環境罪行，初犯開罰 1,000 新幣。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "最高 10,000 新幣罰款或監禁 1 年",
            },
            {
                "title": "公共場所衛生與反亂丟垃圾法",
                "icon": "🚯",
                "desc": "隨地吐痰、亂丟菸蒂、拋棄外帶紙屑初犯即罰 2,000 新幣（約 NT$48,000）；再犯罰 4,000 新幣；第三次最高罰 10,000 新幣並法院判處「勞動改造令 (CGO)」，穿著亮黃色反光背心在鬧區清掃大街。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "罰款 2,000 ~ 10,000 新幣 + 強制作掃街",
            },
            {
                "title": "嚴禁餵食野生動物與街頭鴿子",
                "icon": "🕊️",
                "desc": "在任何公共公園、綠地、住宅區餵食野生鴿子、八哥、野猴或野豬，違反《野生動物法》，初犯罰款最高 5,000 新幣，累犯最高罰款 10,000 新幣。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 500 ~ 10,000 新幣",
            },
            {
                "title": "地鐵 (MRT) 車廂禁止飲食與喝水",
                "icon": "🚇",
                "desc": "進入地鐵閘門付費區後，嚴禁任何形式之飲食，連喝白開水、嚼糖果均在禁止之列，巡查人員查獲即開立 500 新幣罰單。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 500 新幣 (約 NT$12,000)",
            },
            {
                "title": "嚴禁連接未授權之私人 Wi-Fi",
                "icon": "📶",
                "desc": "在新加坡未經許可破解或偷偷連接他人的開放 Wi-Fi 網絡，在法律上被視為駭客行為（觸犯《電腦濫用法》），最高可處 10,000 新幣罰款或 3 年有期徒刑。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "最高罰 10,000 新幣或監禁 3 年",
            },
        ],
    },
    "thailand": {
        "country_zh": "泰國 (Thailand)",
        "flag": "🇹🇭",
        "overview": "佛教文化與王室地位至高無上，法律對冒犯皇室有極端嚴厲之刑罰；電子煙全面違法拘禁。",
        "highlight_warnings": [
            "👑 冒犯君主罪 (刑法 112 條)：對王室言語手勢不敬或損毀泰銖，處 3 至 15 年監禁重刑！",
            "🚭 攜帶、吸食或進口電子煙全面違法，最高處 5 年監禁或 50 萬泰銖重罰！",
            "🛕 寺廟著裝禁露肩露膝，嚴禁踐踏佛像，切勿撫摸他人頭部或用腳指人",
        ],
        "rules": [
            {
                "title": "嚴禁冒犯泰國王室與國王肖像",
                "icon": "👑",
                "desc": "泰國《刑法》第 112 條冒犯君主罪 (Lèse-majesté) 舉世最嚴。切勿在社群媒體或公開場所發表對泰王及王室之批評，切勿踩踏印有泰王頭像之泰銖鈔票或硬幣，違者一律起訴入獄 3 至 15 年。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "3 至 15 年有期徒刑 (無緩刑)",
            },
            {
                "title": "電子煙全面禁止與刑事拘留",
                "icon": "🚭",
                "desc": "泰國自 2014 年起全面禁止電子煙、電子霧化器與加熱菸煙彈。外國旅客被警方查獲隨身攜帶電子煙，將面臨警方扣留、起訴、最高 5 年有期徒刑或最高 50 萬泰銖高額罰款。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "最高 5 年監禁或 50 萬泰銖罰款",
            },
            {
                "title": "佛教寺廟禮儀與神聖規範",
                "icon": "🛕",
                "desc": "參訪大皇宮、玉佛寺等必須穿著覆蓋雙肩的上衣與過膝長褲/長裙，不可穿夾腳拖或背心。嚴禁爬上佛像底座拍照；頭部為身體最高貴神聖部位，切勿觸摸泰國人（包括孩童）頭部；腳底被視為不潔，勿用腳底對著佛像或他人。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "拒絕入場或移送法辦",
            },
            {
                "title": "觀光海灘禁菸與珊瑚保育",
                "icon": "🏖️",
                "desc": "芭達雅、普吉島等熱門觀光海灘全面禁菸，違者可判處最高 1 年徒刑或 10 萬泰銖罰金。嚴禁在珊瑚礁區餵魚、採集貝殼或踩踏珊瑚，違者移送環境法庭。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 10 萬泰銖或 1 年監禁",
            },
        ],
    },
    "italy": {
        "country_zh": "義大利 (Italy)",
        "flag": "🇮🇹",
        "overview": "極度重視文化古蹟與公共建築保護，對破壞古蹟、坐在歷史名勝階梯、餵鴿等行為實施嚴厲罰款。",
        "highlight_warnings": [
            "🏛️ 羅馬西班牙階梯嚴禁坐下或拖行李，特雷維噴泉嚴禁戲水，違者罰 250 ~ 450 歐元",
            "🕊️ 威尼斯聖馬可廣場與羅馬嚴禁餵食鴿子與海鷗，最高罰款 500 歐元",
            "🎫 公車、地鐵或火車上車前務必於黃色打票機打卡 (Validate)，未打票當場罰 50 ~ 200 歐元",
        ],
        "rules": [
            {
                "title": "古蹟保護與階梯就座禁令",
                "icon": "🏛️",
                "desc": "羅馬西班牙階梯（Spanish Steps）全面禁止遊客坐下休息、進食或在階梯拖拉輪式行李箱（罰款 250~400 歐元）；嚴禁在羅馬競技場刻字（違者最高處 1.5 萬歐元罰款及 1 至 5 年徒刑）；特雷維噴泉等歷史水池嚴禁跳入涉水（罰款 450 歐元起並可能驅逐出市區）。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "罰款 250 ~ 15,000 歐元 / 刑事起訴",
            },
            {
                "title": "公共廣場餵鴿罰款禁令",
                "icon": "🕊️",
                "desc": "威尼斯聖馬可廣場、羅馬古蹟區全面禁止販售鳥飼料或餵食鴿子與海鷗，以防止鳥糞酸蝕千年歷史大理石建築，違者面臨 50 至 500 歐元即席罰款。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 50 ~ 500 歐元",
            },
            {
                "title": "大眾交通乘車前強制打票 (Validation)",
                "icon": "🎫",
                "desc": "義大利紙質單程火車票、巴士票上車前必須在車站或車廂內的黃色/綠色打卡機上打印時間戳。持票未打卡視同無票逃票，車長查票當場裁處 50 ~ 200 歐元罰單。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "當場裁罰 50 ~ 200 歐元",
            },
            {
                "title": "天主教教堂著裝嚴格規範",
                "icon": "⛪",
                "desc": "進入梵蒂岡聖彼得大教堂、米蘭大教堂、佛羅倫斯聖母百花大教堂，嚴格禁止穿著無袖背心、細肩帶、短褲、短裙（雙肩與雙膝必須完全覆蓋），否則現場守衛將直接拒絕入場。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "直接拒絕入場",
            },
        ],
    },
    "france": {
        "country_zh": "法國 (France)",
        "flag": "🇫🇷",
        "overview": "崇尚法治與世俗主義，公共場所禁止蒙面；餐廳社交講求基本招呼禮儀，地鐵查票頻繁。",
        "highlight_warnings": [
            "🎭 公共場所嚴禁穿戴全臉面罩或完全遮臉頭巾（遮面禁令違者罰 150 歐元）",
            "🥐 進店先說 'Bonjour'，否則被視為極其失禮；用餐勿催促服務生",
            "🚇 地鐵單程紙票出站前切勿丟棄，出站口查票無票當場開罰 35 ~ 50 歐元",
        ],
        "rules": [
            {
                "title": "公共場所全面面部遮蓋禁令",
                "icon": "🎭",
                "desc": "依據法國法規，任何人在公共街道、公園、公共交通工具內不得穿戴完全遮蓋面部的罩袍、全臉面具或巴拉克拉瓦頭套（醫療口罩除外），違者處 150 歐元罰鍰並需接受公民教育課程。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 150 歐元 + 公民義務課",
            },
            {
                "title": "地鐵車票妥善保存至出站",
                "icon": "🚇",
                "desc": "巴黎地鐵 (RATP) 進站閘門刷票後，車票必須妥善保存至完全離開地鐵站出口。查票人員經常在換乘通道與出站長廊堵截查票，遺失票根或未刷過閘門當場開罰 35 至 50 歐元現金。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "即席罰款 35 ~ 50 歐元",
            },
            {
                "title": "基本法式問候與社交禮節",
                "icon": "🥐",
                "desc": "進入任何法國商店、咖啡廳或麵包店時，務必先向店員說一聲清晰的 'Bonjour'（你好），離開時說 'Merci, au revoir'。在法國文化中，不打招呼直接指點商品被視為極大的人格輕蔑。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "冷淡對待或拒絕服務",
            },
            {
                "title": "公共綠地禁菸與菸蒂重罰",
                "icon": "🚭",
                "desc": "巴黎所有市立公園、花園、兒童遊樂區及公共室內全面禁菸。在街道上隨手將菸蒂拋棄於人行道或下水道，環保警察查獲直接開罰 135 歐元。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 135 歐元",
            },
        ],
    },
    "australia": {
        "country_zh": "澳洲 (Australia)",
        "flag": "🇦🇺",
        "overview": "擁有全球最嚴苛的動植物生物安全檢疫法，對行車安全、環境保護與戶外飲酒執法極其嚴厲。",
        "highlight_warnings": [
            "🦘 邊境生物安全未誠實申報，最高罰 AUD $6,260，情節嚴重註銷簽證即刻遣返並禁入 3 年！",
            "📱 開車觸摸手機（包括等紅燈）罰款逾 AUD $1,000 並扣點，公路全面高解析 AI 攝像頭執法",
            "🍺 公共場所（街道、海灘、公園）未經特許禁止公開飲酒，違者當場開單",
        ],
        "rules": [
            {
                "title": "全球最嚴生物安全法 (Biosecurity Act)",
                "icon": "🦘",
                "desc": "入境澳洲旅客旅客入境卡 (IPC) 上必須誠實申報所有食品、肉類、蛋類、中藥、植物種子及木製品。若被邊境檢疫犬查獲隱匿未報，處以最高 AUD 6,260 罰單，生物安全官可立即註銷簽證、收押遣返並實施 3 年禁止入境禁令。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "罰款 AUD 6,260 / 撤銷簽證遣返",
            },
            {
                "title": "開車使用手機與交通嚴打",
                "icon": "📱",
                "desc": "澳洲各州實施高架 AI 攝像頭取締駕駛人分心行為。開車時只要手持觸摸手機（即便停等紅綠燈），昆士蘭與新南威爾斯州開罰超過 AUD 1,000 至 1,162，並吊扣點數。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款逾 AUD 1,000 (約 NT$22,000)",
            },
            {
                "title": "公共場所公開飲酒限制 (Dry Zones)",
                "icon": "🍺",
                "desc": "澳洲多數市中心街道、公園與公眾海灘劃設為禁酒區 (Alcohol-Free Zones)。在非特許場所手持開罐啤酒或酒精飲料屬違法行為，警方有權直接沒收倒掉並開立即席罰鍰。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 AUD 100 ~ 500",
            },
            {
                "title": "保護野生動植物安全距離",
                "icon": "🐨",
                "desc": "嚴禁餵食袋鼠、野生鳥類或觸碰無尾熊。在國家公園內採摘野花、帶走原生貝殼或石頭違法，最高可處上萬澳幣罰金。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "違規開罰最高 AUD 10,000",
            },
        ],
    },
    "usa": {
        "country_zh": "美國 (USA)",
        "flag": "🇺🇸",
        "overview": "執法警察具高度警惕性，交通臨檢程序嚴密；具備法定 21 歲飲酒年齡及深厚的小費制度。",
        "highlight_warnings": [
            "🚗 警察攔檢切勿自行下車！停靠右側雙手放方向盤上 (Hands on the wheel)，不可伸入口袋！",
            "🔞 嚴格禁止未滿 21 歲飲酒或買酒；公共街頭禁止手持已開封酒瓶 (Open Container)",
            "💵 餐廳內用常態小費 15% ~ 20%，為當地服務業從業人員重要收入禮節",
        ],
        "rules": [
            {
                "title": "警方攔檢安全防衛守則",
                "icon": "🚗",
                "desc": "在美國開車若遇後方警車亮燈鳴笛，必須立即打方向燈減速安全停靠右側路肩。切勿自行解開安全帶開門下車！請搖下車窗，雙手置於方向盤頂端（10點與2點方向）。警方索取駕照前切勿突然將手伸進手套箱或暗袋，以免引發致命誤判拔槍。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "拒捕危險 / 刑事逮捕",
            },
            {
                "title": "開罐酒禁令 (Open Container Law)",
                "icon": "🔞",
                "desc": "除拉斯維加斯大道、紐奧良等特定特區外，全美絕大多數州份嚴禁在公共人行道、公園、車輛乘客座手持已開封之啤酒或烈酒瓶，查獲即屬輕罪 (Misdemeanor)，可處罰款或短暫拘留。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 USD 100 ~ 500 / 輕罪起訴",
            },
            {
                "title": "北美小費文化 (Tipping Customs)",
                "icon": "💵",
                "desc": "美國餐廳服務生底薪極低，小費為其主要合法收入來源。在有桌邊服務之正式餐廳內用，一般給予稅前消費額 15%~20% 之小費；計程車約 10%~15%；行李員每件行李 1~2 美元；若未付小費常會被視為對服務極度不滿或嚴重無禮。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "嚴正詢問與文化失禮",
            },
        ],
    },
    "uk": {
        "country_zh": "英國 (UK)",
        "flag": "🇬🇧",
        "overview": "重視個人空間與傳統紳士禮儀，嚴格講求排隊次序；地鐵手扶梯靠右為絕對默契。",
        "highlight_warnings": [
            "🚇 倫敦地鐵手扶梯務必靠右站立 (Stand on the right)，左側保持全空供急行旅客",
            "🚶 嚴格排隊秩序 (Queueing)，插隊會引發全場強烈譴責與驅離",
            "🏰 倫敦市中心、皇室城堡與公園全面禁止未經許可之無人機空拍",
        ],
        "rules": [
            {
                "title": "地鐵手扶梯嚴格靠右站立",
                "icon": "🚇",
                "desc": "倫敦地鐵 (The Tube) 每日通勤人潮巨大，手扶梯規定「右立左行 (Stand on the right)」。若旅客將行李或身體擋在左側通道，會引起後方通勤者嚴厲規勸。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "當場規勸",
            },
            {
                "title": "排隊文化與插隊禁忌",
                "icon": "🚶",
                "desc": "排隊 (Queueing) 在英國被視為社會公平的基石。在公車站、售票處或商店，切勿詢問插隊或假裝沒看到隊伍末端，插隊會被全體排隊者當眾糾正拒絕服務。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "拒絕服務與當眾糾正",
            },
            {
                "title": "無人機空拍禁飛與刑事罰則",
                "icon": "🏰",
                "desc": "未經民航局 (CAA) 特殊許可，嚴禁在倫敦市中心、泰晤士河沿岸、白金漢宮、溫莎城堡等管制空域飛行無人機，違者器材將被扣押沒收並處最高 2,500 英鎊罰款或監禁。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "罰款 2,500 英鎊 / 沒收器材起訴",
            },
            {
                "title": "傳統英式酒吧點餐禮節",
                "icon": "🍺",
                "desc": "傳統英式 Pub 通常無桌邊服務，顧客需自行至吧台排隊點餐、點啤酒並當場結帳，再自行將飲品端回座位。吧台通常不收取小費，但若想表示謝意可說 'and one for yourself'（請調酒師喝一杯）。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "空等無人點餐",
            },
        ],
    },
    "canada": {
        "country_zh": "加拿大 (Canada)",
        "flag": "🇨🇦",
        "overview": "國家公園自然保護極其嚴格，對野生動物保持法定距離；嚴厲禁止跨越國際邊境攜帶大麻。",
        "highlight_warnings": [
            "🌿 嚴禁將大麻攜帶出境或入境！跨國邊境攜帶大麻屬嚴重聯邦罪行，最高判刑 14 年",
            "🐻 國家公園嚴禁餵食野生動物或靠近熊與麋鹿，違者最高罰款 25,000 加幣",
            "💵 餐廳與服務業常態小費為 15% ~ 18%",
        ],
        "rules": [
            {
                "title": "跨國境大麻絕對禁令 (Cannabis Crossing Borders)",
                "icon": "🌿",
                "desc": "雖然大麻在加拿大境內特定合法化，但《加拿大邊境法》嚴格規定：任何旅客將任何形式之大麻或含有 THC 成分產品帶出加拿大境外或帶入境內，均屬重大刑事聯邦犯罪，面臨最高 14 年有期徒刑。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "最高 14 年有期徒刑聯邦重刑",
            },
            {
                "title": "國家公園野生動物距離與餵食重罰",
                "icon": "🐻",
                "desc": "在班夫 (Banff)、賈斯珀 (Jasper) 等國家公園內，嚴禁餵食任何野生動植物，見到熊類需保持至少 100 公尺距離、麋鹿 30 公尺距離。未妥善收納食物吸引野生動物，最高處 25,000 加元罰款。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "最高處 25,000 加幣罰款",
            },
            {
                "title": "室內全面禁菸與距離門窗法規",
                "icon": "🚭",
                "desc": "加拿大各省法律嚴格禁止在公共室內、工作場所及大眾交通吸菸，且在建築物門窗、通風口通常要求保持至少 6 至 9 公尺之法定禁菸緩衝距離。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 250 ~ 1,000 加幣",
            },
        ],
    },
    "netherlands": {
        "country_zh": "荷蘭 (Netherlands)",
        "flag": "🇳🇱",
        "overview": "自行車路權至高無上，紅燈區嚴禁拍攝櫥窗女郎；軟性毒品有特定合法場域限制且絕不可帶出境。",
        "highlight_warnings": [
            "🚲 紅色自行車道 (Fietspad) 嚴禁行人步行！荷蘭單車車速極快，違者易遭重大衝撞受傷",
            "📸 阿姆斯特丹紅燈區櫥窗女郎嚴禁拍照錄影，違者手機恐遭沒入或扔入運河",
            "🚬 咖啡館 (Coffeeshop) 軟性毒品僅限店內，絕對嚴禁攜帶跨越國境出境至其他國家！",
        ],
        "rules": [
            {
                "title": "紅色單車道步行禁令",
                "icon": "🚲",
                "desc": "阿姆斯特丹擁有世界最龐大的自行車網絡，紅色鋪面道路為單車專用道 (Fietspad)。行人在單車道上散步或拍照會招致猛烈鈴聲甚至高速衝撞，警察亦可對違法侵入者開立罰單。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 60 ~ 100 歐元 / 人身衝撞受傷",
            },
            {
                "title": "紅燈區嚴禁攝影與拍照",
                "icon": "📸",
                "desc": "阿姆斯特丹德瓦倫 (De Wallen) 紅燈區嚴格保護性工作者隱私，任何人嚴禁對櫥窗女郎拍照或錄影。現場有便衣巡邏與安保，違法拍攝者手機會被當場搶下砸毀或丟入運河，甚至引發肢體衝突被警局拘留。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "沒收沒入設備 / 警方拘留",
            },
            {
                "title": "管制藥物 Coffeeshop 與跨國邊境重罪",
                "icon": "🚬",
                "desc": "大麻在荷蘭並非無條件合法，而是採「容忍政策 (Gedogen)」，僅限於持照咖啡館 (Coffeeshop) 內購買自用。在一般街道吸食仍可能受罰，將大麻攜帶出境（包括乘火車前往比利時或德國）屬國際走私重罪，鄰國海關定點嚴查入獄。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "國際毒品走私刑事起訴",
            },
        ],
    },
    "spain": {
        "country_zh": "西班牙 (Spain)",
        "flag": "🇪🇸",
        "overview": "沿海城市市區街道禁止僅著泳裝；用餐時間偏晚，觀光熱點需高度防範扒竊。",
        "highlight_warnings": [
            "🩱 市區非海灘街道嚴禁僅穿著比基尼、泳褲或打赤膊，違者開罰 100 ~ 300 歐元",
            "🎒 蘭布拉大道與地鐵嚴防扒竊，後背包必須背胸前，手機切勿放露天咖啡桌邊",
            "🍽️ 西班牙用餐作息特殊：午餐約 14:00~16:00，晚餐 20:30~23:00，非供餐時段廚房休息",
        ],
        "rules": [
            {
                "title": "海灘外市區街道泳裝禁令",
                "icon": "🩱",
                "desc": "巴塞隆納、馬略卡島等觀光城市規定：離開沙灘與海濱步道進入一般市區街道、地鐵或商店時，必須穿上一般上衣與褲子/裙子，打赤膊或僅著泳裝比基尼可處 100 至 300 歐元罰款。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 100 ~ 300 歐元",
            },
            {
                "title": "扒竊防範與街頭安全常識",
                "icon": "🎒",
                "desc": "巴塞隆納加泰隆尼亞廣場、蘭布拉大道、馬德里太陽門廣場為歐洲扒手最高發區域。請勿將護照錢包置於後口袋，搭乘地鐵背包務必背在胸前，露天咖啡廳切勿將手機置於桌面邊緣以防飛車或小販假借問卷遮蔽扒竊。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "財務遭竊與證件補辦困擾",
            },
            {
                "title": "作息作息延後與午睡 (Siesta) 文化",
                "icon": "🍽️",
                "desc": "西班牙作息全球最晚。傳統店家於 14:00~17:00 常有關門午休之習慣；正式餐廳晚餐通常於晚間 20:30 或 21:00 方開門營業，過早抵達通常只能在 Tapas Bar 點小菜飲品。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "撲空或無熱食可點",
            },
        ],
    },
    "greece": {
        "country_zh": "希臘 (Greece)",
        "flag": "🇬🇷",
        "overview": "歷史古蹟保護嚴格，遺址嚴禁尖銳鞋跟；希臘小島衛生下水管線特殊，衛生紙不可扔馬桶。",
        "highlight_warnings": [
            "👠 衛城 (Acropolis) 等古代遺址嚴禁穿高跟鞋，以防尖底磨損千年大理石地面",
            "🧻 希臘海島排水管狹窄，衛生紙嚴禁投入馬桶，必須丟入旁邊專用垃圾桶",
            "🏛️ 嚴禁自歷史遺址、海灘拾取或帶走任何古老石塊、瓦片或特定貝殼，海關查獲刑責",
        ],
        "rules": [
            {
                "title": "歷史古蹟禁止高跟鞋與大背包",
                "icon": "👠",
                "desc": "為保護希臘國寶級千年大理石古蹟，希臘文化部規定參觀雅典衛城、帕德嫩神廟等景點嚴禁穿著高跟鞋或鞋跟具破壞性之尖底鞋，守衛將禁止入場；大型後背包必須寄放。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "現場拒絕入場參觀",
            },
            {
                "title": "海島衛生紙垃圾桶投放習慣",
                "icon": "🧻",
                "desc": "聖托里尼 (Santorini)、米科諾斯 (Mykonos) 等海島管道年代久遠且管徑狹小，將衛生紙沖入馬桶極易造成全棟下水道倒灌堵塞，嚴重者需負擔高達上千歐元之清通修繕賠償。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "造成管道堵塞須負擔修繕賠償",
            },
            {
                "title": "嚴禁撿拾古蹟石片或黑沙帶出境",
                "icon": "🏛️",
                "desc": "希臘《文物保護法》極其嚴格，在任何古蹟遺址周邊拾取任何哪怕一塊小石頭帶走，海關安檢發現視同走私古物，將被警方當場拘留起訴；部分特殊沙灘（如粉紅沙灘）沙石亦受法律保護不得帶走。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "刑事起訴 / 當場拘留",
            },
        ],
    },
    "vietnam": {
        "country_zh": "越南 (Vietnam)",
        "flag": "🇻🇳",
        "overview": "機車洪流庞大過馬路有特定技巧，貨幣面額大需仔細清點，參觀陵寢著裝嚴謹。",
        "highlight_warnings": [
            "🛵 穿越機車洪流需保持等速直線前進，切忌猶豫停頓、後退或突然奔跑！",
            "💵 越南盾面額零多（如 2 萬與 50 萬色澤近似），付款切勿讓小販自行翻抽錢包！",
            "🏛️ 參觀胡志明陵寢、古芝地道與寺廟必須穿著長褲長裙，保持肅靜不可交頭接耳",
        ],
        "rules": [
            {
                "title": "穿越馬路穩定均速行進法則",
                "icon": "🛵",
                "desc": "河內與胡志明市機車數量極多，缺乏人行紅綠燈時過馬路要訣：眼神觀察車流，以穩定、均勻的速度直線前進，機車騎士會自行預判軌跡從前後繞過。最危險的行為是走到一半突然驚慌停滯、向後跳或猛烈奔跑，極易引發車禍。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "發生人身交通危險",
            },
            {
                "title": "鈔票面額辨識防抽詐騙",
                "icon": "💵",
                "desc": "越南盾 (VND) 面額動輒數十萬，20,000 與 500,000 鈔票顏色相近容易混淆。結帳時務必自己看清楚面額抽出交付，切忌將整個錢包攤開任由計程車司機或攤販自行抽取，以免大鈔遭掉包。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "財物被詐騙損失",
            },
            {
                "title": "紀念碑與宗教場地嚴肅規範",
                "icon": "🏛️",
                "desc": "進入河內胡志明陵寢或重要革命紀念地時，禁止穿著短褲、露背背心或拖鞋，雙手不可插在口袋中，必須脫帽並保持肅靜，切勿有嬉笑打鬧行為。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "驅離出場或處罰",
            },
        ],
    },
    "philippines": {
        "country_zh": "菲律賓 (Philippines)",
        "flag": "🇵🇭",
        "overview": "對海灘環境生態保護執法嚴苛，嚴厲打擊非法攜帶海砂珊瑚；公共海灘禁菸酒。",
        "highlight_warnings": [
            "🐚 嚴禁攜帶未經許可之海砂、珊瑚或貝殼出境，海關查獲當場扣留移送法辦！",
            "🚭 長灘島等熱門海灘全面禁止吸菸、飲酒、丟垃圾，違者處罰鍰或拘役",
            "🛫 機場行李切勿讓可疑陌生人碰觸或協助搬運，嚴防行李搭訕敲詐",
        ],
        "rules": [
            {
                "title": "海砂、珊瑚與海洋生物出境禁令",
                "icon": "🐚",
                "desc": "菲律賓環境法嚴格禁止旅客私自收集長灘島白沙、未經加工珊瑚或硨磲貝帶出境。機場行李 X 光檢查若發現裝有海砂瓶或珊瑚，將被海關與海警扣押調查，面臨重額罰金甚至刑事起訴。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "扣留偵訊 / 移送法辦與高額罰金",
            },
            {
                "title": "觀光海灘禁菸酒與環境秩序法",
                "icon": "🚭",
                "desc": "長灘島自封島整治後實行嚴格生態法規：沙灘區域全面禁止吸菸、禁止飲用酒精飲料、禁止舉辦未經批准的沙灘派對或火舞表演，違者將由環保警察當場拘押處以罰款。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 2,500 披索或拘役數日",
            },
            {
                "title": "計程車跳表防坑 (Grab 優先)",
                "icon": "🚕",
                "desc": "馬尼拉機場搭乘黃色計程車或白色計程車時，上車前必須確認要求 'Meter please'（跳表計費）。建議優先使用 Grab 網約車叫車，免除喊價灌水、不找零或繞路爭議。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "車資被超收爭端",
            },
        ],
    },
    "malaysia": {
        "country_zh": "馬來西亞 (Malaysia)",
        "flag": "🇲🇾",
        "overview": "多元宗教文化國家，伊斯蘭教禮儀講究；公共餐飲區全面禁菸，飯店嚴禁攜帶榴槤。",
        "highlight_warnings": [
            "🕌 進入清真寺必須脫鞋並著合適長袍，勿用左手遞物或用食指指人（應用右手大拇指）",
            "🚭 露天餐飲店、嘛嘛檔 (Mamak) 3 公尺範圍內全面禁菸，最高罰 RM 10,000 或監禁 2 年！",
            "🚫 大部分星級飯店、地鐵及大眾運輸工具明確張貼告示：嚴禁攜帶榴槤入內",
        ],
        "rules": [
            {
                "title": "清真寺參訪服裝與身體指向禮節",
                "icon": "🕌",
                "desc": "參觀布城粉紅清真寺、吉隆坡國家清真寺時，女性需穿著長袍及佩戴頭巾（現場多提供租借），男性不可穿短褲背心。伊斯蘭文化中左手被視為不淨，遞物、付錢、進食必須使用右手；指點人事物請用右手大拇指（其餘四指握拳），切勿用食指直接指人。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "拒絕入場與嚴重失禮",
            },
            {
                "title": "全馬各類餐飲場所嚴格禁菸令",
                "icon": "🚭",
                "desc": "馬來西亞實施嚴格公共禁菸法，所有冷氣餐廳、無冷氣露天大排檔、嘛嘛檔（Mamak）周圍 3 公尺範圍內一律禁菸（包含電子煙）。違者最高可處 10,000 令吉罰款或判處最長 2 年監禁。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "最高罰款 RM 10,000 或坐牢 2 年",
            },
            {
                "title": "飯店與大眾交通「榴槤禁令」",
                "icon": "🚫",
                "desc": "由於榴槤氣味濃烈且滲透力強，馬來西亞絕大多數飯店、捷運 (LRT/MRT) 及長途巴士均嚴禁攜帶新鮮榴槤進入，若在飯店房間食用留下氣味，退房時將被索取高達 RM 500 ~ 1,000 的深層除臭清潔費。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "索取高額房間除臭清潔費",
            },
        ],
    },
    "hong kong": {
        "country_zh": "香港 (Hong Kong)",
        "flag": "🇭🇰",
        "overview": "快節奏大都會，法律規管極度嚴密；另類吸菸產品（電子煙/加熱菸）全面違法，港鐵禁食罰款重。",
        "highlight_warnings": [
            "🚭 電子煙、加熱菸全面違法！進口、攜帶或售賣最高罰款 50 萬港幣及監禁 6 個月！",
            "🚇 港鐵付費區與車廂內嚴禁飲食（包括飲水、嚼口香糖），最高開罰 2,000 港幣",
            "🚯 街頭亂丟菸蒂、垃圾或隨地吐痰定額罰款已提高至 3,000 港幣即席罰單",
        ],
        "rules": [
            {
                "title": "另類吸煙產品（電子煙/加熱菸）全面禁令",
                "icon": "🚭",
                "desc": "香港《2021年吸煙（公眾衛生）（修訂）條例》全面禁止進口、推廣、製造、售賣或為商業目的管有另類吸煙產品（包括電子煙、加熱菸煙彈及草本菸）。旅客攜帶自用入境亦屬違法，一經定罪最高可處罰款 50 萬港幣及監禁 6 個月。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "最高罰款 50 萬港幣及監禁 6 個月",
            },
            {
                "title": "港鐵 (MTR) 車廂與付費區絕對禁食",
                "icon": "🚇",
                "desc": "依據《香港鐵路附例》，旅客進入已付車費區域及列車車廂後，嚴禁進食或飲用任何飲品（白開水、手搖飲、嚼口香糖均在禁止之列）。港鐵職員定點巡查，違者最高可處罰款 2,000 港幣。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "最高罰款 2,000 港幣",
            },
            {
                "title": "公共潔淨定額罰款調高至 3,000 港幣",
                "icon": "🚯",
                "desc": "在公共街道亂拋垃圾、棄置菸蒂、吐痰或讓犬隻糞便弄污街道，食物環境衛生署執法人員直接開立定額罰款通知書，罰款金額已全面調高至 3,000 港幣（約 NT$12,300），無任何警告緩衝。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "即席罰單 3,000 港幣",
            },
            {
                "title": "茶餐廳搭檯與用餐步調文化",
                "icon": "☕",
                "desc": "香港茶餐廳客流高峰時「搭檯」（與陌生人共用一張桌子）為普遍常態；夥計點單與結帳講求高效率迅速，結帳時需持桌上帳單自行至櫃檯付款，用餐完畢不宜長時間久坐聊天占用座位。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "文化習慣無罰則",
            },
        ],
    },
    "taiwan": {
        "country_zh": "臺灣 (Taiwan)",
        "flag": "🇹🇼",
        "overview": "社會安全友好且守秩序，大眾捷運禁食執法嚴明；非洲豬瘟檢疫零容忍，電子煙全面禁用。",
        "highlight_warnings": [
            "🚇 進入捷運黃色禁食線後，嚴禁飲食、喝水或嚼口香糖，違者裁罰 NT$ 1,500 ~ 7,500！",
            "🐷 嚴禁攜帶任何肉製品入境（非洲豬瘟初犯罰 NT$20 萬，未繳清外籍旅客即刻拒絕入境）",
            "🚭 電子煙與未核定之加熱菸全面禁止攜帶入境，違者最高罰 NT$ 500 萬元！",
        ],
        "rules": [
            {
                "title": "捷運黃色禁食線嚴格規範",
                "icon": "🚇",
                "desc": "台北捷運與高雄捷運車站地面繪有明顯黃色禁食線。一旦跨越黃線進入付費區及車廂內，全面禁止飲食、喝水、嚼食口香糖或檳榔。站務人員及捷運警察常態巡查，違者依《大眾捷運法》裁處新臺幣 1,500 元以上 7,500 元以下罰鍰。",
                "risk_level": "⚠️ 公共管理罰款",
                "penalty": "罰款 NT$ 1,500 ~ 7,500",
            },
            {
                "title": "非洲豬瘟肉製品邊境絕對零容忍",
                "icon": "🐷",
                "desc": "為防堵非洲豬瘟，臺灣對肉製品入境檢疫極度嚴格。旅客自疫區攜帶豬肉製品（含火腿、肉鬆蛋捲、含肉快餐麵）未主動申報，初犯處新臺幣 20 萬元罰鍰，再犯處 100 萬元。外籍旅客若未當場繳清 20 萬元罰款，移民署依法立即拒絕入境並原機遣返！",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "罰款 NT$ 20 萬至 100 萬 / 立即遣返",
            },
            {
                "title": "電子煙全面禁止與重罰法規",
                "icon": "🚭",
                "desc": "依《菸害防制法》修正案，臺灣全面禁止製造、輸入、販賣、供應及使用電子煙或未經健康風險評估之加熱菸。旅客攜帶電子煙入境，海關查獲除當場沒入外，最高可處新臺幣 500 萬元罰鍰。",
                "risk_level": "🚨 重罰/拘役高風險",
                "penalty": "沒入煙品 / 最高處 NT$ 500 萬元罰款",
            },
            {
                "title": "博愛座禮讓與手扶梯靠右文化",
                "icon": "🤝",
                "desc": "大眾交通工具之深藍色博愛座優先禮讓老弱婦孺及隱形需求者；捷運手扶梯多數旅客習慣靠右站立，左側保持流暢供趕時間旅客快步通行。",
                "risk_level": "💡 文化習慣禮儀",
                "penalty": "社會良知與禮節",
            },
        ],
    },
}


def get_destination_culture_etiquette(destination: str) -> Dict[str, Any]:
    """Provides local cultural etiquette, traveler behavioral laws, and penalty warnings for the destination.

    Args:
        destination: Destination country name or city.

    Returns:
        A structured dictionary containing:
        - destination: Country display name
        - flag: National flag emoji
        - overview: Concise cultural and legal summary
        - highlight_warnings: List of critical high-risk traveler warnings
        - rules: Detailed list of categories, icons, titles, descriptions, risk levels, and penalty amounts
    """
    dest_norm = destination.strip().lower()

    matched_key = None
    for key in DESTINATION_ETIQUETTE_DATA.keys():
        if key in dest_norm:
            matched_key = key
            break

    if not matched_key:
        if any(k in dest_norm for k in ["日本", "東京", "大阪", "japan"]):
            matched_key = "japan"
        elif any(k in dest_norm for k in ["韓國", "首爾", "korea"]):
            matched_key = "korea"
        elif any(k in dest_norm for k in ["新加坡", "singapore"]):
            matched_key = "singapore"
        elif any(k in dest_norm for k in ["泰國", "曼谷", "thailand"]):
            matched_key = "thailand"
        elif any(k in dest_norm for k in ["義大利", "意大利", "italy"]):
            matched_key = "italy"
        elif any(k in dest_norm for k in ["法國", "巴黎", "france"]):
            matched_key = "france"
        elif any(k in dest_norm for k in ["澳洲", "雪梨", "墨爾本", "australia"]):
            matched_key = "australia"
        elif any(k in dest_norm for k in ["美國", "紐約", "洛杉磯", "usa", "united states"]):
            matched_key = "usa"
        elif any(k in dest_norm for k in ["英國", "倫敦", "uk", "united kingdom"]):
            matched_key = "uk"
        elif any(k in dest_norm for k in ["加拿大", "canada"]):
            matched_key = "canada"
        elif any(k in dest_norm for k in ["荷蘭", "阿姆斯特丹", "netherlands"]):
            matched_key = "netherlands"
        elif any(k in dest_norm for k in ["西班牙", "馬德里", "巴塞隆納", "spain"]):
            matched_key = "spain"
        elif any(k in dest_norm for k in ["希臘", "雅典", "greece"]):
            matched_key = "greece"
        elif any(k in dest_norm for k in ["越南", "河內", "胡志明", "vietnam"]):
            matched_key = "vietnam"
        elif any(k in dest_norm for k in ["菲律賓", "馬尼拉", "philippines"]):
            matched_key = "philippines"
        elif any(k in dest_norm for k in ["馬來西亞", "吉隆坡", "malaysia"]):
            matched_key = "malaysia"
        elif any(k in dest_norm for k in ["香港", "hong kong"]):
            matched_key = "hong kong"
        elif any(k in dest_norm for k in ["臺灣", "台灣", "taiwan", "tw"]):
            matched_key = "taiwan"
        else:
            matched_key = "taiwan"

    entry = dict(DESTINATION_ETIQUETTE_DATA.get(matched_key, DESTINATION_ETIQUETTE_DATA["taiwan"]))
    entry.setdefault("country_name", entry.get("country_zh", ""))
    entry["key"] = matched_key
    return entry


