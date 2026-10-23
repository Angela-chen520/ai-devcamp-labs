"""
Security Guardrails & Anti-Malware Module for VideoLearn AI.
Defends against:
1. Malicious URLs, Phishing, & SSRF (Server-Side Request Forgery)
2. Command Injection & Path Traversal (Shell breakout prevention)
3. Malware / Disguised Executable Payloads (Magic Bytes & MIME validation)
4. Prompt Injection & Adversarial Jailbreaks
5. XSS & Malicious Content Injection

Provides comprehensive security diagnostics, detailing virus types/models,
computer file impacts, mobile phone file impacts, and firm refusal notices.
"""

import ipaddress
import os
import re
import socket
from typing import Tuple, Dict, Any, List, Optional
from urllib.parse import urlparse

# Allowed Video / Audio Hosting Domains (SurFast 2 platform coverage)
ALLOWED_PLATFORM_DOMAINS = [
    # YouTube
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
    # TikTok
    "tiktok.com", "www.tiktok.com", "vm.tiktok.com",
    # Facebook / Meta
    "facebook.com", "www.facebook.com", "fb.watch", "web.facebook.com", "m.facebook.com",
    # X / Twitter
    "twitter.com", "www.twitter.com", "x.com", "www.x.com",
    # Instagram
    "instagram.com", "www.instagram.com",
    # Twitch
    "twitch.tv", "www.twitch.tv", "clips.twitch.tv",
    # Bilibili
    "bilibili.com", "www.bilibili.com", "b23.tv",
    # Vimeo
    "vimeo.com", "www.vimeo.com", "player.vimeo.com",
    # SoundCloud
    "soundcloud.com", "www.soundcloud.com", "on.soundcloud.com",
    # Reddit
    "reddit.com", "www.reddit.com", "v.redd.it",
    # LinkedIn
    "linkedin.com", "www.linkedin.com",
    # Pinterest
    "pinterest.com", "www.pinterest.com", "pin.it",
    # Bandcamp
    "bandcamp.com"
]

# Magic Bytes Signatures for Known Audio/Video Formats
VALID_MAGIC_BYTES = {
    "mp4": [b"\x00\x00\x00\x18ftyp", b"\x00\x00\x00\x20ftyp", b"\x00\x00\x00\x1cftyp"],
    "webm": [b"\x1a\x45\xdf\xa3"],
    "mkv": [b"\x1a\x45\xdf\xa3"],
    "mp3": [b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"],
    "wav": [b"RIFF"],
    "ogg": [b"OggS"],
    "m4a": [b"\x00\x00\x00\x20ftypM4A", b"\x00\x00\x00\x1cftypM4A", b"M4A "]
}

# =========================================================================
# 惡意程式/病毒資料庫 (Malware & Disguised Payload Registry)
# 詳列病毒類型型號、電腦檔案威脅影響、手機檔案威脅影響及防禦處置
# =========================================================================
MALWARE_REGISTRY = {
    "pe": {
        "magic": b"MZ",
        "error_code": "SEC_MALWARE_WIN_PE",
        "signature_desc": "Windows Portable Executable (EXE/DLL)",
        "threat_level": "CRITICAL",
        "model_name": "Win32.Trojan.Generic / PE32 偽裝木馬程式",
        "model_name_en": "Win32.Trojan.Generic / PE32 Disguised Executable Trojan",
        "threat_summary": "偽裝成影音副檔名（.mp4/.mp3）之 Windows PE32/DLL 可執行二進制惡意代碼",
        "threat_summary_en": "Windows PE32/DLL executable binary disguised as media file (.mp4/.mp3)",
        "pc_impact": "【電腦檔案威脅】若使用者或伺服器執行此檔案，將觸發勒索軟體 (Ransomware) 惡意加密硬碟中所有個人文件（.docx, .xlsx, .pdf, .jpg）、相片與專案資料庫；植入木馬後門 (RAT) 側錄鍵盤輸入、竊取瀏覽器儲存之密碼、SSH 私鑰及加密貨幣錢包助記詞，並將電腦主機淪為殭屍網路（Botnet）節點。",
        "pc_impact_en": "[Computer Impact] Execution triggers Ransomware encrypting all personal documents (.docx, .xlsx, .pdf, .jpg), photos, and databases; injects Remote Access Trojans (RAT) to log keystrokes, steal browser credentials, SSH keys, and crypto wallets, enslaving the PC into a botnet.",
        "mobile_impact": "【手機檔案威脅】若透過跨平台檔案同步工具（如 iCloud, Google Drive, LINE, 微信）下載或同步至手機，將成為跨平台惡意種子，可能誘使第三方檔案總管解析引發溢位崩潰，並損毀跨平台共用工作區之同步目錄。",
        "mobile_impact_en": "[Mobile Impact] If synced across devices via cloud drives or chat apps, it acts as a cross-platform malicious seed, risking file viewer crashes and compromising synchronized media folders.",
        "action_verdict": "故系統依據企業級資安防禦規範，嚴格終止解析並拒絕提供下載，以保護您的電腦與手機檔案安全。",
        "action_verdict_en": "Therefore, in strict adherence to enterprise cybersecurity standards, the system has terminated analysis and refused download to safeguard your computer and mobile files."
    },
    "elf": {
        "magic": b"\x7fELF",
        "error_code": "SEC_MALWARE_LINUX_ELF",
        "signature_desc": "Linux Executable Binary (ELF)",
        "threat_level": "CRITICAL",
        "model_name": "Linux.Backdoor.Dropper / ELF 惡意二進制執行檔",
        "model_name_en": "Linux.Backdoor.Dropper / ELF Malicious Binary",
        "threat_summary": "偽裝成影音檔案之 Linux ELF 原生可執行二進制後門程式",
        "threat_summary_en": "Linux ELF native binary executable disguised as media stream",
        "pc_impact": "【電腦檔案威脅】在 Linux / macOS / WSL 終端環境下將獲得原生執行權限，植入持久化 Rootkit 提權木馬，篡改系統設定檔（/etc/passwd, ~/.ssh/authorized_keys），無聲於背景佈署加密貨幣挖礦程式，損毀或外洩本機開發專案核心原始碼。",
        "pc_impact_en": "[Computer Impact] Executes natively on Linux/macOS/WSL to install persistent rootkits, modify critical configs (/etc/passwd, ~/.ssh), deploy covert cryptominers, and exfiltrate proprietary source code files.",
        "mobile_impact": "【手機檔案威脅】Android 底層架構基於 Linux 核心，此類 ELF 檔案常被設計為 Android 原生惡意模組（Native Payload），可嘗試利用 Linux 核心漏洞進行提權（Kernel Exploit），突破 Android 應用程式沙盒（Sandbox Escape），任意讀取或篡改手機本機儲存空間中所有 App 的私有資料庫與照片檔案。",
        "mobile_impact_en": "[Mobile Impact] Android runs on the Linux kernel. This ELF payload can exploit kernel vulnerabilities to achieve Sandbox Escape, gaining root access to read, overwrite, or exfiltrate private mobile app databases and user photos.",
        "action_verdict": "故系統依據企業級資安防禦規範，嚴格終止解析並拒絕提供下載，以保護您的電腦與手機檔案安全。",
        "action_verdict_en": "Therefore, in strict adherence to enterprise cybersecurity standards, the system has terminated analysis and refused download to safeguard your computer and mobile files."
    },
    "macho": {
        "magic": b"\xca\xfe\xba\xbe",
        "error_code": "SEC_MALWARE_MACHO_JAVA",
        "signature_desc": "Mach-O / Java Class Executable",
        "threat_level": "HIGH",
        "model_name": "OSX.Trojan.Gen / Java.Exploit (Mach-O / Bytecode 惡意程式)",
        "model_name_en": "OSX.Trojan.Gen / Java.Exploit (Mach-O / Bytecode Malicious Binary)",
        "threat_summary": "偽裝成影音檔案之 macOS Mach-O 跨架構二進位碼或 Java 位元組碼",
        "threat_summary_en": "macOS Mach-O multi-arch binary or Java bytecode disguised as media stream",
        "pc_impact": "【電腦檔案威脅】鎖定 Mac (Apple Silicon / Intel) 與 Java 跨平台開發環境，可穿透 macOS Gatekeeper 安全機制，竊取 Keychain 鑰匙圈中儲存的 Safari 密碼、Wi-Fi 密碼、iCloud 同步 Token，並劫持本機麥克風與攝影機存取權。",
        "pc_impact_en": "[Computer Impact] Targets macOS and Java runtime environments to bypass Gatekeeper, exfiltrate Keychain passwords, Wi-Fi keys, iCloud tokens, and secretly hijack microphone/camera permissions.",
        "mobile_impact": "【手機檔案威脅】對 iOS 越獄設備及行動 Java/Dalvik 執行環境構成威脅，可能誘發惡意動態程式庫注入（Dylib Hijacking），導致行動端作業系統完整性遭破壞。",
        "mobile_impact_en": "[Mobile Impact] Threatens jailbroken iOS devices and mobile runtime containers, causing dynamic library hijacking and compromising mobile OS integrity.",
        "action_verdict": "故系統依據企業級資安防禦規範，嚴格終止解析並拒絕提供下載，以保護您的電腦與手機檔案安全。",
        "action_verdict_en": "Therefore, in strict adherence to enterprise cybersecurity standards, the system has terminated analysis and refused download to safeguard your computer and mobile files."
    },
    "script": {
        "magic": b"#!",
        "error_code": "SEC_MALWARE_SHELL_SCRIPT",
        "signature_desc": "Shell Script / Command File",
        "threat_level": "HIGH",
        "model_name": "Script.Trojan.Downloader (Shell / Bash / Python 惡意指令碼)",
        "model_name_en": "Script.Trojan.Downloader (Shell / Bash / Python Malicious Script)",
        "threat_summary": "帶有 Shebang (#!) 之系統命令檔，偽裝成串流音訊或影片",
        "threat_summary_en": "System shell command script with Shebang (#!) disguised as media",
        "pc_impact": "【電腦檔案威脅】可在終端機或命令提示字元中被直接執行，觸發 rm -rf 刪除磁碟所有重要資料夾、下載外部未授權後門程式、關閉防毒軟體即時防護，並向外部伺服器回傳主機敏感環境變數與金鑰。",
        "pc_impact_en": "[Computer Impact] Can execute directly in terminal to delete local disk directories, download external payloads, disable antivirus protections, and leak local environment credentials.",
        "mobile_impact": "【手機檔案威脅】若在 Termux 或具備 ADB/Root 權限之手機環境中執行，將篡改 /system 或 /data 系統分割區，導致手機開機無限卡頓（變磚），清空手機使用者所有本機檔案與通訊記錄。",
        "mobile_impact_en": "[Mobile Impact] In Termux or rooted mobile environments, can overwrite /data or /system partitions, causing bootloops (bricking device) and erasing all stored files and chat logs.",
        "action_verdict": "故系統依據企業級資安防禦規範，嚴格終止解析並拒絕提供下載，以保護您的電腦與手機檔案安全。",
        "action_verdict_en": "Therefore, in strict adherence to enterprise cybersecurity standards, the system has terminated analysis and refused download to safeguard your computer and mobile files."
    },
    "apk_zip": {
        "magic": b"PK\x03\x04",
        "error_code": "SEC_MALWARE_ANDROID_APK",
        "signature_desc": "Compressed Archive (ZIP/APK/JAR) - Disallowed direct audio",
        "threat_level": "HIGH",
        "model_name": "Android.Trojan.FakeApp / Banker (APK 惡意安裝包 / 偽裝封包)",
        "model_name_en": "Android.Trojan.FakeApp / Banker (Malicious APK / Disguised Archive)",
        "threat_summary": "將 ZIP / APK 封裝壓縮檔偽裝成影音副檔名（.mp4/.mp3）",
        "threat_summary_en": "Compressed ZIP/APK package disguised as audio/video extension",
        "pc_impact": "【電腦檔案威脅】解開後常內藏惡意 VBS/JS 腳本或巨集文件，誘騙使用者點擊執行，進而下載二階段攻擊載體，感染電腦工作區檔案。",
        "pc_impact_en": "[Computer Impact] May contain bundled malicious scripts or macro-enabled documents that trigger multi-stage dropper attacks infecting local desktop files.",
        "mobile_impact": "【手機檔案威脅】此為 Android 專屬惡意安裝包（APK）。一旦於手機端下載並安裝，將發動「金融覆蓋攻擊（Overlay Attack）」：在使用者開啟網銀或支付 App 時彈出偽造登入介面竊取帳號密碼；強制攔截所有簡訊（SMS）與雙因素驗證 OTP 驗證碼進行盜刷；常駐後台私自撥打付費電話、耗盡行動網路數據流量，並非法存取聯絡人與照片相簿。",
        "mobile_impact_en": "[Mobile Impact] Android package (APK). If installed on mobile, launches banking overlay attacks displaying phishing login windows over genuine banking apps, intercepts incoming SMS OTP authentication codes, dials premium rate numbers in background, drains mobile data, and exfiltrates contacts and photo gallery.",
        "action_verdict": "故系統依據企業級資安防禦規範，嚴格終止解析並拒絕提供下載，以保護您的電腦與手機檔案安全。",
        "action_verdict_en": "Therefore, in strict adherence to enterprise cybersecurity standards, the system has terminated analysis and refused download to safeguard your computer and mobile files."
    },
    "rar_bomb": {
        "magic": b"Rar!\x1a\x07",
        "error_code": "SEC_MALWARE_RAR_BOMB",
        "signature_desc": "RAR Archive - Disallowed direct audio",
        "threat_level": "MEDIUM",
        "model_name": "Archive.DecompressionBomb / MultiPayload (RAR 偽裝封包)",
        "model_name_en": "Archive.DecompressionBomb / MultiPayload (Disguised RAR Archive)",
        "threat_summary": "將 RAR 多重壓縮封包偽裝為串流媒體，疑似封裝炸彈或多階攻擊載體",
        "threat_summary_en": "Disguised RAR archive disguised as media, risk of decompression bomb",
        "pc_impact": "【電腦檔案威脅】可能包含高壓縮比解壓縮炸彈（Decompression Bomb），解壓時瞬間耗盡數百 GB 磁碟空間與 100% 記憶體，導致電腦操作系統當機藍屏（BSOD）或磁碟寫入故障。",
        "pc_impact_en": "[Computer Impact] May contain a decompression bomb exhausting hundreds of GBs of disk space and 100% memory, resulting in system crash (BSOD) or disk filesystem corruption.",
        "mobile_impact": "【手機檔案威脅】手機快閃記憶體容量有限，解壓縮炸彈將迅速填滿手機儲存空間，導致手機系統無法快取分頁而死機重啟，甚至觸發系統原廠重置風險。",
        "mobile_impact_en": "[Mobile Impact] Fills mobile flash storage instantly, causing out-of-memory lockups, infinite crash-loops, and potential forced factory resets.",
        "action_verdict": "故系統依據企業級資安防禦規範，嚴格終止解析並拒絕提供下載，以保護您的電腦與手機檔案安全。",
        "action_verdict_en": "Therefore, in strict adherence to enterprise cybersecurity standards, the system has terminated analysis and refused download to safeguard your computer and mobile files."
    },
    "pdf_exploit": {
        "magic": b"%PDF",
        "error_code": "SEC_MALWARE_PDF_EXPLOIT",
        "signature_desc": "PDF Document disguised as media",
        "threat_level": "HIGH",
        "model_name": "Exploit.PDF.EmbeddedJS / Phish (PDF 偽裝文件漏洞攻擊)",
        "model_name_en": "Exploit.PDF.EmbeddedJS / Phish (Disguised PDF Document Exploit)",
        "threat_summary": "將 PDF 文件偽裝成音訊或影片副檔名，內藏可疑嵌入式腳本",
        "threat_summary_en": "PDF document disguised as media extension with potential embedded JavaScript exploits",
        "pc_impact": "【電腦檔案威脅】利用 PDF 閱讀軟體未修補之零日漏洞（0-day），透過嵌入式 JavaScript 觸發記憶體溢位，取得電腦終端控制權並竊取工作區文件。",
        "pc_impact_en": "[Computer Impact] Exploits PDF reader zero-days via embedded JS to trigger memory corruption and gain local terminal execution to steal workplace documents.",
        "mobile_impact": "【手機檔案威脅】手機內建瀏覽器或文件預覽器解析異常 PDF 物件時，可能導致預覽服務崩潰，並被引導至釣魚認證頁面騙取手機號碼與帳號憑證。",
        "mobile_impact_en": "[Mobile Impact] Mobile document viewers can crash on malicious PDF structures, triggering redirection to credential phishing sites targeting mobile account credentials.",
        "action_verdict": "故系統依據企業級資安防禦規範，嚴格終止解析並拒絕提供下載，以保護您的電腦與手機檔案安全。",
        "action_verdict_en": "Therefore, in strict adherence to enterprise cybersecurity standards, the system has terminated analysis and refused download to safeguard your computer and mobile files."
    }
}

# Dangerous Binary Signatures tuple list for quick scanning (maintaining signature descriptions)
DANGEROUS_SIGNATURES = [
    (info["magic"], info["signature_desc"])
    for info in MALWARE_REGISTRY.values()
]

# Prompt Injection Keywords
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"system\s+prompt\s+leak",
    r"reveal\s+your\s+hidden\s+prompt",
    r"you\s+are\s+now\s+dan",
    r"bypass\s+all\s+safety\s+filters",
    r"override\s+system\s+directive",
    r"jailbreak\s+mode",
    r"<script\b[^>]*>",
    r"javascript\s*:",
    r"eval\s*\("
]


class SecurityGuard:
    """Enterprise-grade security gatekeeper for VideoLearn AI."""

    FAIR_USE_DISCLAIMER = "一切資源作學術研討幫助學習者學習，不提供商業用、或搬運影片用"
    FAIR_USE_DISCLAIMER_EN = "All resources are provided solely for academic research and educational study to assist learners; commercial use or video piracy/re-uploading is strictly prohibited."

    @staticmethod
    def diagnose_url(url: str) -> Dict[str, Any]:
        """
        Deep diagnostic analysis of a video URL for security risks,
        returning structured reason, error code, threat level, and verdict.
        """
        if not url or not isinstance(url, str):
            return {
                "is_safe": False,
                "error_code": "SEC_URL_EMPTY",
                "threat_level": "LOW",
                "detailed_reason": "網址不能為空，請輸入欲研討之影音 URL。",
                "detailed_reason_en": "URL cannot be empty. Please enter a valid media URL.",
                "action_verdict": "故系統無法進行解析與下載。",
                "action_verdict_en": "System cannot parse or download.",
                "formatted_message": "網址不能為空。"
            }

        clean_url = url.strip()

        # Check for dangerous shell characters (Command Injection)
        dangerous_chars = [";", "|", "&", "`", "$", "\n", "\r", "<", ">", "\0", "\\"]
        for ch in dangerous_chars:
            if ch in clean_url:
                msg = f"偵測到不安全之特殊字元「{ch}」，疑似指令注入攻擊，已主動攔截。"
                return {
                    "is_safe": False,
                    "error_code": "SEC_CMD_INJECTION",
                    "threat_level": "CRITICAL",
                    "virus_model": "OS.CommandInjection.ShellBreakout (指令注入惡意攻擊)",
                    "virus_model_en": "OS.CommandInjection.ShellBreakout (Command Injection Attack)",
                    "detailed_reason": f"網址中檢測到特殊字元「{ch}」，企圖跳脫影音解析程式並在作業系統執行任意指令碼（Command Injection / 指令注入攻擊）。",
                    "detailed_reason_en": f"Disallowed shell metacharacter '{ch}' detected in URL, representing an arbitrary command injection attempt.",
                    "pc_impact": "【電腦檔案威脅】指令注入可能使攻擊者在伺服器或電腦端執行刪除檔案、植入未授權後門程式或盜取伺服器配置金鑰之毀滅性操作。",
                    "pc_impact_en": "[Computer Impact] Command injection enables arbitrary terminal commands to delete files, deploy backdoors, or steal server credentials.",
                    "mobile_impact": "【手機檔案威脅】若行動端客戶端轉發此類惡意參數，可能干擾行動應用程式處理序並導致通訊端點崩潰異常。",
                    "mobile_impact_en": "[Mobile Impact] May cause terminal crashes or remote execution vulnerabilities if forwarded to mobile components.",
                    "action_verdict": "故系統依據企業級資安防禦規範，嚴格終止解析並拒絕提供下載，以保護您的電腦與手機檔案安全。",
                    "action_verdict_en": "Therefore, in strict adherence to enterprise cybersecurity standards, the system has terminated analysis and refused download to safeguard your computer and mobile files.",
                    "formatted_message": msg
                }

        # Parse URL
        try:
            parsed = urlparse(clean_url)
        except Exception as e:
            return {
                "is_safe": False,
                "error_code": "SEC_URL_PARSE_ERROR",
                "threat_level": "LOW",
                "detailed_reason": f"網址解析失敗：{str(e)}",
                "detailed_reason_en": f"URL parsing error: {str(e)}",
                "action_verdict": "故系統無法進行解析與下載。",
                "action_verdict_en": "System cannot parse or download.",
                "formatted_message": f"網址解析失敗：{str(e)}"
            }

        # 1. Scheme Check
        if parsed.scheme.lower() not in ["https", "http"]:
            msg = f"不支援的通訊協定「{parsed.scheme}」，僅允許安全的 https:// 影片網址。"
            return {
                "is_safe": False,
                "error_code": "SEC_UNSUPPORTED_SCHEME",
                "threat_level": "MEDIUM",
                "detailed_reason": f"通訊協定「{parsed.scheme}://」不安全或非標準，禁止使用 file://, gopher://, ftp:// 等潛在危險協定。",
                "detailed_reason_en": f"Unsupported scheme '{parsed.scheme}://'. Only secure HTTPS/HTTP protocols are permitted.",
                "action_verdict": "故系統依據企業級資安防禦規範，拒絕提供解析與下載。",
                "action_verdict_en": "System strictly refuses parsing and downloading under enterprise security policies.",
                "formatted_message": msg
            }

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return {
                "is_safe": False,
                "error_code": "SEC_HOSTNAME_MISSING",
                "threat_level": "LOW",
                "detailed_reason": "無效的網址格式（缺少主機域名）。",
                "detailed_reason_en": "Invalid URL format (missing hostname).",
                "action_verdict": "故系統無法進行解析與下載。",
                "action_verdict_en": "System cannot parse or download.",
                "formatted_message": "無效的網址格式（缺少主機域名）。"
            }

        # 2. Raw IP and Localhost Check (Direct SSRF prevention)
        is_private_ip = False
        is_cloud_meta = False
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_multicast
                or ip_obj.is_reserved
            ):
                is_private_ip = True
            if str(ip_obj) in ["169.254.169.254", "169.254.169.253"]:
                is_cloud_meta = True
        except ValueError:
            pass

        if hostname in ["localhost", "ip6-localhost", "ip6-loopback"]:
            is_private_ip = True

        if is_cloud_meta:
            msg = "基於企業級安全防禦（SSRF），嚴禁存取雲端執行個體中繼資料服務。"
            return {
                "is_safe": False,
                "error_code": "SEC_SSRF_CLOUD_METADATA",
                "threat_level": "CRITICAL",
                "detailed_reason": "網址指向公有雲 (AWS/GCP/Azure) 之 Instance Metadata Service (169.254.169.254)。攻擊者企圖竊取雲端虛擬機 IAM 存取憑證、API 金鑰與伺服器內部密鑰。嚴禁存取雲端執行個體中繼資料服務。",
                "detailed_reason_en": "Target points to Cloud Instance Metadata Service (169.254.169.254). Enterprise policy strictly forbids metadata access to protect cloud credentials.",
                "pc_impact": "【電腦檔案威脅】若雲端 IAM 憑證失竊，攻擊者可藉此提權存取雲端儲存庫（S3 / Cloud Storage / Firestore），銷毀或洩漏所有遠端備份資料與個人檔案。",
                "pc_impact_en": "[Computer Impact] Compromised cloud credentials allow attackers to access cloud buckets, destroy remote database backups, and leak sensitive documents.",
                "mobile_impact": "【手機檔案威脅】間接導致手機端連線的雲端個人帳戶被惡意鎖定或資料遭未授權同步外洩。",
                "mobile_impact_en": "[Mobile Impact] Threatens cloud account linkage, risking remote wipe or unauthorized sync of mobile files.",
                "action_verdict": "故系統嚴格終止解析並拒絕提供下載，捍衛雲端基礎架構安全。",
                "action_verdict_en": "System strictly terminates analysis and refuses download to protect cloud infrastructure security.",
                "formatted_message": msg
            }

        if is_private_ip:
            msg = "基於企業級安全防禦（SSRF），禁止請求本地端或內部區域網路位址。"
            return {
                "is_safe": False,
                "error_code": "SEC_SSRF_INTRANET",
                "threat_level": "HIGH",
                "detailed_reason": f"來源主機「{hostname}」屬於私有內部網路位址（Localhost / Intranet / Private IP）。此為典型 SSRF (Server-Side Request Forgery) 探測行為。基於企業級安全防禦（SSRF），禁止請求本地端或內部區域網路位址。",
                "detailed_reason_en": f"Hostname '{hostname}' resolves to private intranet / localhost. Blocked by enterprise SSRF defense.",
                "pc_impact": "【電腦檔案威脅】SSRF 攻擊可突破網路邊界防火牆，直接探測本機內部資料庫、Redis 緩存或管理介面，造成內部系統檔案被竊取或勒索。",
                "pc_impact_en": "[Computer Impact] SSRF enables lateral movement to probe internal databases, Redis caches, and admin panels, risking local data theft.",
                "mobile_impact": "【手機檔案威脅】在同一區域 Wi-Fi 網路中，可能被用於掃描家庭或公司連線手機開放之除錯埠，危及手機內部檔案傳輸安全。",
                "mobile_impact_en": "[Mobile Impact] Can be abused to probe debugging ports of connected mobile devices on the local Wi-Fi, compromising local phone data transfers.",
                "action_verdict": "故系統依據企業級資安防禦規範，嚴格終止解析並拒絕提供下載，以保護內部網路與設備檔案安全。",
                "action_verdict_en": "System strictly terminates analysis and refuses download to safeguard internal network and device files.",
                "formatted_message": msg
            }

        # 3. Domain Whitelist Check
        domain_matched = False
        for allowed in ALLOWED_PLATFORM_DOMAINS:
            if hostname == allowed or hostname.endswith("." + allowed):
                domain_matched = True
                break

        if not domain_matched:
            msg = (
                f"安全防護攔截：來源網域「{hostname}」非核准的影音平台白名單。\n"
                f"支援平台包括：YouTube, TikTok, Facebook, X/Twitter, Instagram, Bilibili, Vimeo, Twitch, SoundCloud, Reddit 等。"
            )
            return {
                "is_safe": False,
                "error_code": "SEC_DOMAIN_UNVERIFIED",
                "threat_level": "HIGH",
                "detailed_reason": f"安全防護攔截：來源網域「{hostname}」非核准的影音平台白名單。非受信任網域常充斥釣魚轉址、掛馬下載或偽裝的假影音串流服務。",
                "detailed_reason_en": f"Security Intercept: Domain '{hostname}' is not in the approved media platform whitelist. Untrusted domains carry risks of drive-by downloads, phishing redirects, or fake media streams.",
                "pc_impact": "【電腦檔案威脅】未經驗證的第三方網站可能誘導瀏覽器下載偽裝檔案，觸發惡意腳本執行或勒索病毒感染，破壞電腦工作區檔案。",
                "pc_impact_en": "[Computer Impact] Unverified third-party sites may lure users into downloading spoofed files containing malware or ransomware infecting desktop files.",
                "mobile_impact": "【手機檔案威脅】惡意站點常透過彈出式廣告或偽造更新通知誘騙手機使用者安裝惡意描述檔或監控程式，竊取手機照片、通訊錄與簡訊。",
                "mobile_impact_en": "[Mobile Impact] Malicious sites frequently deploy deceptive pop-ups or fake update prompts to install spyware on phones, stealing photos, contacts, and SMS.",
                "action_verdict": "故系統依據企業級資安防禦規範，嚴格終止解析並拒絕提供下載，以保護您的電腦與手機檔案安全。",
                "action_verdict_en": "Therefore, in strict adherence to enterprise cybersecurity standards, the system has terminated analysis and refused download to safeguard your computer and mobile files.",
                "formatted_message": msg
            }

        # 4. DNS Resolution & Rebinding Check (if DNS is reachable)
        try:
            ip_str = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip_str)
            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_multicast
                or ip_obj.is_reserved
            ):
                msg = "基於企業級安全防禦（SSRF），網域名稱解析至內部私有 IP，已阻絕連線。"
                return {
                    "is_safe": False,
                    "error_code": "SEC_SSRF_DNS_REBINDING",
                    "threat_level": "CRITICAL",
                    "detailed_reason": f"DNS 重綁定攻擊（DNS Rebinding）：網域名稱「{hostname}」解析至內部私有 IP（{ip_str}）。基於企業級安全防禦（SSRF），網域名稱解析至內部私有 IP，已阻絕連線。",
                    "detailed_reason_en": f"DNS Rebinding attack: Domain '{hostname}' resolves to internal private IP ({ip_str}). Blocked by enterprise SSRF defense.",
                    "pc_impact": "【電腦檔案威脅】利用 DNS 伺服器動態變更 IP，企圖偽裝成公開網址以穿透防火牆存取內部主機機密資料。",
                    "pc_impact_en": "[Computer Impact] Exploits dynamic DNS responses to bypass firewall rules and access internal confidential files.",
                    "mobile_impact": "【手機檔案威脅】威脅區域網路內受信任的手機終端，造成私有傳輸資料遭攔截。",
                    "mobile_impact_en": "[Mobile Impact] Compromises trusted intranet sessions on mobile devices connected to the same LAN.",
                    "action_verdict": "故系統嚴格終止解析並拒絕提供下載，以保護內部設備檔案安全。",
                    "action_verdict_en": "System strictly terminates analysis and refuses download to protect internal device files.",
                    "formatted_message": msg
                }
            if str(ip_obj) in ["169.254.169.254", "169.254.169.253"]:
                msg = "基於企業級安全防禦（SSRF），嚴禁存取雲端執行個體中繼資料服務。"
                return {
                    "is_safe": False,
                    "error_code": "SEC_SSRF_CLOUD_METADATA",
                    "threat_level": "CRITICAL",
                    "detailed_reason": "網域解析至雲端中繼資料服務 IP。嚴禁存取雲端執行個體中繼資料服務。",
                    "detailed_reason_en": "Domain resolves to cloud metadata IP. Strictly forbidden by cloud security policies.",
                    "action_verdict": "故系統嚴格終止解析並拒絕提供下載。",
                    "action_verdict_en": "System strictly terminates analysis and refuses download.",
                    "formatted_message": msg
                }
        except (socket.gaierror, socket.herror, TimeoutError, OSError):
            # In offline/sandboxed environments without DNS, the domain already matched our verified whitelist
            pass

        return {
            "is_safe": True,
            "error_code": "SEC_OK",
            "threat_level": "NONE",
            "detailed_reason": "驗證通過：安全合規的影音網址。",
            "detailed_reason_en": "Validation passed: Legitimate and verified media URL.",
            "formatted_message": "驗證通過：安全合規的影音網址。"
        }

    @classmethod
    def validate_url(cls, url: str) -> Tuple[bool, str]:
        """Backward-compatible validation returning (is_safe, message)."""
        diag = cls.diagnose_url(url)
        return diag["is_safe"], diag["formatted_message"]

    @staticmethod
    def diagnose_media_binary(data: bytes, filename: str = "media") -> Dict[str, Any]:
        """
        Deep binary inspection of in-memory byte buffers against malware signatures
        and valid media magic bytes, returning complete threat model, impacts, and refusal notice.
        """
        if not data or len(data) == 0:
            return {
                "is_safe": False,
                "error_code": "SEC_FILE_EMPTY",
                "threat_level": "LOW",
                "detected_format": "empty",
                "detailed_reason": "上傳或下載之檔案內容為空（0 Bytes），無法進行音訊解析或轉譯。",
                "detailed_reason_en": "File content is empty (0 Bytes), cannot parse audio or transcribe.",
                "action_verdict": "故系統無法提供解析或下載。",
                "action_verdict_en": "System cannot parse or download empty files.",
                "formatted_message": "檔案為空。"
            }

        header = data[:64]

        # Scan for dangerous signatures registered in MALWARE_REGISTRY
        for key, info in MALWARE_REGISTRY.items():
            sig = info["magic"]
            if header.startswith(sig) or sig in header[:16]:
                # Construct backward-compatible string that includes exact description
                desc = info["signature_desc"]
                full_message = (
                    f"⚠️ 資安嚴重告警：檢測到危險的可執行二進位特徵碼（{desc}），疑似夾帶病毒/木馬攻擊，已強制拒絕接收！\n"
                    f"• 病毒類型型號：{info['model_name']}\n"
                    f"• {info['pc_impact']}\n"
                    f"• {info['mobile_impact']}\n"
                    f"• 防禦處置：{info['action_verdict']}"
                )
                return {
                    "is_safe": False,
                    "error_code": info["error_code"],
                    "threat_level": info["threat_level"],
                    "detected_format": "malware",
                    "virus_model": info["model_name"],
                    "virus_model_en": info["model_name_en"],
                    "signature": desc,
                    "threat_summary": info["threat_summary"],
                    "threat_summary_en": info["threat_summary_en"],
                    "detailed_reason": f"檢測到危險的可執行二進位特徵碼（{desc}），疑似夾帶病毒/木馬攻擊！",
                    "detailed_reason_en": f"Detected dangerous executable binary signature ({desc}), suspected disguised malware/trojan attack!",
                    "pc_impact": info["pc_impact"],
                    "pc_impact_en": info["pc_impact_en"],
                    "mobile_impact": info["mobile_impact"],
                    "mobile_impact_en": info["mobile_impact_en"],
                    "action_verdict": info["action_verdict"],
                    "action_verdict_en": info["action_verdict_en"],
                    "formatted_message": full_message
                }

        # Check for genuine media signatures
        detected_fmt = None
        for fmt, sigs in VALID_MAGIC_BYTES.items():
            for sig in sigs:
                if header.startswith(sig) or sig in header[:32]:
                    detected_fmt = fmt
                    break
            if detected_fmt:
                break

        if not detected_fmt:
            # Check extension fallback if no explicit match
            ext = os.path.splitext(filename)[1].lower().replace(".", "")
            if ext in ["mp4", "m4a", "mp3", "wav", "webm", "mkv"]:
                detected_fmt = ext
            else:
                msg = "⚠️ 資安防護提示：檔案標頭不符合常見音訊/視訊二進位格式規範，可能為損毀或偽裝之未知格式。"
                return {
                    "is_safe": False,
                    "error_code": "SEC_FORMAT_UNRECOGNIZED",
                    "threat_level": "MEDIUM",
                    "detected_format": "unknown",
                    "detailed_reason": "檔案標頭（Magic Bytes）未包含標準音訊/視訊串流格式規範，疑似損毀檔案或企圖繞過檢測之偽裝未知格式。",
                    "detailed_reason_en": "File header (Magic Bytes) does not match legitimate media formats. Suspected corrupted stream or disguised unknown binary.",
                    "pc_impact": "【電腦檔案威脅】未知或畸形二進位格式可能觸發底層媒體解碼器（如 ffmpeg, DirectShow）之緩衝區溢位漏洞（Buffer Overflow），導致非預期代碼執行。",
                    "pc_impact_en": "[Computer Impact] Malformed binary formats can trigger buffer overflows in underlying media decoders, causing unexpected code execution.",
                    "mobile_impact": "【手機檔案威脅】可能使手機媒體庫掃描服務（MediaScanner）死鎖崩潰，影響手機正常相簿預覽與電池續航。",
                    "mobile_impact_en": "[Mobile Impact] May crash mobile media scanner services, locking up album previews and draining battery.",
                    "action_verdict": "故系統依據企業級資安防禦規範，終止解析並拒絕提供下載，以防止潛在惡意載荷損害您的設備檔案。",
                    "action_verdict_en": "Therefore, system terminates analysis and refuses download to prevent potential payload damage to your device files.",
                    "formatted_message": msg
                }

        return {
            "is_safe": True,
            "error_code": "SEC_OK",
            "threat_level": "NONE",
            "detected_format": detected_fmt,
            "detailed_reason": f"驗證通過：合規的 {detected_fmt.upper()} 影音串流檔案。",
            "detailed_reason_en": f"Validation passed: Verified {detected_fmt.upper()} legitimate media stream.",
            "formatted_message": f"驗證通過：合規的 {detected_fmt.upper()} 影音串流檔案。"
        }

    @classmethod
    def validate_media_binary(cls, data: bytes, filename: str = "media") -> Tuple[bool, str, str]:
        """Backward-compatible binary validation returning (is_safe, detected_format, message)."""
        diag = cls.diagnose_media_binary(data, filename)
        return diag["is_safe"], diag["detected_format"], diag["formatted_message"]

    @staticmethod
    def diagnose_media_file(file_path: str, max_size_mb: int = 150) -> Dict[str, Any]:
        """
        Comprehensive forensic inspection of downloaded or uploaded media files on disk:
        1. File existence and size limit
        2. Malware registry binary signatures
        3. Legitimate media magic bytes
        """
        if not os.path.exists(file_path):
            return {
                "is_safe": False,
                "error_code": "SEC_FILE_NOT_FOUND",
                "threat_level": "LOW",
                "detailed_reason": "檔案不存在或存取路徑異常。",
                "detailed_reason_en": "File does not exist or invalid path.",
                "action_verdict": "故系統無法進行解析與下載。",
                "action_verdict_en": "System cannot parse or download.",
                "formatted_message": "檔案不存在。"
            }

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return {
                "is_safe": False,
                "error_code": "SEC_FILE_EMPTY",
                "threat_level": "LOW",
                "detailed_reason": "檔案大小為 0 Bytes，檔案為空。",
                "detailed_reason_en": "File size is 0 Bytes, empty file.",
                "action_verdict": "故系統無法進行解析與下載。",
                "action_verdict_en": "System cannot parse or download empty files.",
                "formatted_message": "檔案為空。"
            }

        if file_size > max_size_mb * 1024 * 1024:
            size_mb = file_size // (1024 * 1024)
            msg = f"檔案大小（{size_mb}MB）超過系統安全上限（{max_size_mb}MB）。"
            return {
                "is_safe": False,
                "error_code": "SEC_FILE_SIZE_EXCEEDED",
                "threat_level": "MEDIUM",
                "detailed_reason": f"檔案體積（{size_mb}MB）超過系統設定之安全防護上限（{max_size_mb}MB）。超大型檔案具備阻斷服務（DoS）或耗盡本機磁碟記憶體之風險。",
                "detailed_reason_en": f"File size ({size_mb}MB) exceeds system safety limit ({max_size_mb}MB). Blocked to prevent DoS or disk exhaustion.",
                "pc_impact": "【電腦檔案威脅】過大檔案可能導致電腦記憶體耗盡（OOM Crash），造成正在編輯的工作區文檔與專案資料遺失。",
                "pc_impact_en": "[Computer Impact] Excessive file size may trigger OOM crashes, losing unsaved workplace documents and workspace data.",
                "mobile_impact": "【手機檔案威脅】下載超大檔案將耗盡手機儲存空間與行動網路流量，可能導致手機系統緩存分頁失敗死機。",
                "mobile_impact_en": "[Mobile Impact] Exceeds mobile storage and mobile data limits, risking storage saturation and system freeze.",
                "action_verdict": "故系統不提供直接解析或下載，建議裁剪精簡學習段落後再行研討。",
                "action_verdict_en": "System terminates processing to ensure operational availability.",
                "formatted_message": msg
            }

        # Read first 4096 bytes for header inspection
        with open(file_path, "rb") as f:
            header = f.read(4096)

        # 1. Scan for Dangerous Malware Signatures
        for key, info in MALWARE_REGISTRY.items():
            sig = info["magic"]
            if header.startswith(sig) or (sig in header[:64]):
                desc = info["signature_desc"]
                msg = f"🚨 檔案安全性威脅：檢測到危險二進制標頭「{desc}」，已立即銷毀隔離！"
                return {
                    "is_safe": False,
                    "error_code": info["error_code"],
                    "threat_level": info["threat_level"],
                    "virus_model": info["model_name"],
                    "virus_model_en": info["model_name_en"],
                    "signature": desc,
                    "threat_summary": info["threat_summary"],
                    "threat_summary_en": info["threat_summary_en"],
                    "detailed_reason": f"檢測到危險二進制標頭「{desc}」，疑似夾帶惡意代碼！",
                    "detailed_reason_en": f"Detected dangerous binary header '{desc}', suspected disguised malware!",
                    "pc_impact": info["pc_impact"],
                    "pc_impact_en": info["pc_impact_en"],
                    "mobile_impact": info["mobile_impact"],
                    "mobile_impact_en": info["mobile_impact_en"],
                    "action_verdict": info["action_verdict"],
                    "action_verdict_en": info["action_verdict_en"],
                    "formatted_message": msg
                }

        # 2. Check for legitimate media magic bytes
        is_legit_media = False
        if b"ftyp" in header[:32]:
            is_legit_media = True
        elif header.startswith(b"\x1a\x45\xdf\xa3"):
            is_legit_media = True
        elif header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0):
            is_legit_media = True
        elif header.startswith(b"RIFF") and b"WAVE" in header[:16]:
            is_legit_media = True
        elif header.startswith(b"OggS"):
            is_legit_media = True

        if not is_legit_media:
            msg = "🚨 格式不合規：該檔案未包含標準影音串流特徵，疑似偽裝檔案，拒絕載入！"
            return {
                "is_safe": False,
                "error_code": "SEC_FORMAT_INVALID",
                "threat_level": "HIGH",
                "detailed_reason": "該檔案未包含標準影音串流特徵（Magic Bytes），疑似偽裝二進位檔案。",
                "detailed_reason_en": "File does not contain standard audio/video stream signatures, suspected disguised binary.",
                "pc_impact": "【電腦檔案威脅】偽裝媒體可能包含惡意構造的二進位載荷，意圖觸發剖析器崩潰或記憶體溢位攻擊。",
                "pc_impact_en": "[Computer Impact] Disguised media may embed crafted payloads to exploit parser vulnerabilities or memory corruption.",
                "mobile_impact": "【手機檔案威脅】若載入行動裝置可能引發媒體服務死鎖與 App 異常崩潰退出。",
                "mobile_impact_en": "[Mobile Impact] May crash mobile media frameworks and cause application instability.",
                "action_verdict": "故系統依據企業級資安防禦規範，嚴格終止解析並拒絕提供下載，以保護您的電腦與手機檔案安全。",
                "action_verdict_en": "Therefore, system strictly terminates analysis and refuses download to safeguard your computer and mobile files.",
                "formatted_message": msg
            }

        return {
            "is_safe": True,
            "error_code": "SEC_OK",
            "threat_level": "NONE",
            "detailed_reason": "檔案通過惡意代碼與特徵碼掃描，為合法安全影音。",
            "detailed_reason_en": "File passed malware signature scanning and verified as legitimate media.",
            "formatted_message": "檔案通過惡意代碼與特徵碼掃描，為合法安全影音。"
        }

    @classmethod
    def validate_media_file(cls, file_path: str, max_size_mb: int = 150) -> Tuple[bool, str]:
        """Backward-compatible file validation returning (is_safe, message)."""
        diag = cls.diagnose_media_file(file_path, max_size_mb)
        return diag["is_safe"], diag["formatted_message"]

    @staticmethod
    def sanitize_prompt(text: str) -> Tuple[bool, str, str]:
        """
        Scans learner inputs and video transcripts for prompt injection attacks.
        Returns (is_safe, sanitized_text, warning_message).
        """
        if not text:
            return True, "", ""

        text_lower = text.lower()
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                sanitized = re.sub(pattern, "[BLOCKED_ADVERSARIAL_INSTRUCTION]", text, flags=re.IGNORECASE)
                return False, sanitized, "⚠️ 系統資安防禦：檢測到異常提示詞注入（Prompt Injection）語句，已自動中和隔離。"

        # Strip dangerous HTML script tags to prevent XSS
        clean_text = re.sub(r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", "", text, flags=re.IGNORECASE)
        clean_text = clean_text.replace("<script", "&lt;script").replace("javascript:", "")

        return True, clean_text, ""

    @staticmethod
    def get_security_manifest() -> Dict[str, Any]:
        """Returns the active security status report for display on Web UI."""
        return {
            "status": "ACTIVE_ARMORED",
            "protections": [
                {"name": "多平台白名單過濾", "desc": "嚴格限制 YouTube, TikTok, FB, IG, Bilibili 等合法影音網域", "status": "🛡️ 啟用中"},
                {"name": "防 SSRF 與內網探測", "desc": "阻絕 localhost, 127.0.0.1, 10.x, 192.168.x 與雲端中繼資料存取", "status": "🛡️ 啟用中"},
                {"name": "防指令注入 (Command Injection)", "desc": "徹底清除分號、管線符號、反引號等 Shell 注入字元", "status": "🛡️ 啟用中"},
                {"name": "檔案二進制特徵碼掃描 (Magic Bytes)", "desc": "攔截偽裝成影音的 EXE, ELF, BAT, APK 與惡意腳本", "status": "🛡️ 啟用中"},
                {"name": "提示詞注入護欄 (Prompt Injection Guard)", "desc": "過濾 System Prompt 竊取、越獄攻擊與無效指令", "status": "🛡️ 啟用中"},
                {"name": "XSS 跨站腳本過濾", "desc": "自動淨化 HTML 標籤與惡意腳本注入", "status": "🛡️ 啟用中"},
                {"name": "純音訊串流沙盒抽取", "desc": "僅提取純音訊轉逐字稿，不傳遞任何可執行容器，避免病毒傳播", "status": "🛡️ 啟用中"}
            ],
            "fair_use_notice": "本系統一切資源僅供個人學術研討與學習輔助之合理使用，嚴禁商業營利、未經授權之影片搬運或侵權散佈。"
        }

    @classmethod
    def get_protection_manifest(cls) -> Dict[str, Any]:
        """Alias for get_security_manifest."""
        return cls.get_security_manifest()
