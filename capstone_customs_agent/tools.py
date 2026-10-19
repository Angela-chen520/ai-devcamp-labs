"""Deterministic tools for the Traveler Customs Advisor agent.

Includes:
1. calculate_duty_tax: Accurate duty and tax estimator for international baggage items.
2. generate_phrase_card: Generates a bilingual customs inspection flashcard for travelers.
3. lookup_country_limits: Fast-path limits lookup for top travel corridors across 18 destinations.
4. get_destination_weather: Real-time and seasonal weather forecast & packing advice.
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

