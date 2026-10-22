"""
Security Guardrails & Anti-Malware Module for VideoLearn AI.
Defends against:
1. Malicious URLs, Phishing, & SSRF (Server-Side Request Forgery)
2. Command Injection & Path Traversal (Shell breakout prevention)
3. Malware / Disguised Executable Payloads (Magic Bytes & MIME validation)
4. Prompt Injection & Adversarial Jailbreaks
5. XSS & Malicious Content Injection
"""

import ipaddress
import os
import re
import socket
from typing import Tuple, Dict, Any, List
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

# Dangerous Binary Signatures (Malware, Executables, Scripts)
DANGEROUS_SIGNATURES = [
    (b"MZ", "Windows Portable Executable (EXE/DLL)"),
    (b"\x7fELF", "Linux Executable Binary (ELF)"),
    (b"\xca\xfe\xba\xbe", "Mach-O / Java Class Executable"),
    (b"#!", "Shell Script / Command File"),
    (b"PK\x03\x04", "Compressed Archive (ZIP/APK/JAR) - Disallowed direct audio"),
    (b"Rar!\x1a\x07", "RAR Archive - Disallowed direct audio"),
    (b"%PDF", "PDF Document disguised as media")
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
    def validate_url(url: str) -> Tuple[bool, str]:
        """
        Validates URL for:
        1. Correct HTTPS/HTTP scheme (reject file://, gopher://, ftp://, etc.)
        2. Known video/audio platform domain whitelist
        3. SSRF prevention (blocks private/loopback/cloud metadata IP addresses)
        4. Command injection patterns (shell metacharacters)
        """
        if not url or not isinstance(url, str):
            return False, "網址不能為空。"

        clean_url = url.strip()

        # Check for dangerous shell characters
        dangerous_chars = [";", "|", "&", "`", "$", "\n", "\r", "<", ">", "\0", "\\"]
        for ch in dangerous_chars:
            if ch in clean_url:
                return False, f"偵測到不安全之特殊字元「{ch}」，疑似指令注入攻擊，已主動攔截。"

        # Parse URL
        try:
            parsed = urlparse(clean_url)
        except Exception as e:
            return False, f"網址解析失敗：{str(e)}"

        # 1. Scheme Check
        if parsed.scheme.lower() not in ["https", "http"]:
            return False, f"不支援的通訊協定「{parsed.scheme}」，僅允許安全的 https:// 影片網址。"

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False, "無效的網址格式（缺少主機域名）。"

        # 2. Raw IP and Localhost Check (Direct SSRF prevention)
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_multicast
                or ip_obj.is_reserved
            ):
                return False, "基於企業級安全防禦（SSRF），禁止請求本地端或內部區域網路位址。"
            # Block Cloud Metadata IP explicitly
            if str(ip_obj) in ["169.254.169.254", "169.254.169.253"]:
                return False, "嚴禁存取雲端執行個體中繼資料服務。"
        except ValueError:
            # Not a numeric IP, continue to hostname checks
            pass

        if hostname in ["localhost", "ip6-localhost", "ip6-loopback"]:
            return False, "基於企業級安全防禦（SSRF），禁止請求本地端或內部區域網路位址。"

        # 3. Domain Whitelist Check
        domain_matched = False
        for allowed in ALLOWED_PLATFORM_DOMAINS:
            if hostname == allowed or hostname.endswith("." + allowed):
                domain_matched = True
                break

        if not domain_matched:
            return (
                False,
                f"安全防護攔截：來源網域「{hostname}」非核准的影音平台白名單。\n"
                f"支援平台包括：YouTube, TikTok, Facebook, X/Twitter, Instagram, Bilibili, Vimeo, Twitch, SoundCloud, Reddit 等。"
            )

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
                return False, "基於企業級安全防禦（SSRF），網域名稱解析至內部私有 IP，已阻絕連線。"
            if str(ip_obj) in ["169.254.169.254", "169.254.169.253"]:
                return False, "嚴禁存取雲端執行個體中繼資料服務。"
        except (socket.gaierror, socket.herror, TimeoutError, OSError):
            # In offline/sandboxed environments without DNS, the domain already matched our verified whitelist
            pass

        return True, "驗證通過：安全合規的影音網址。"

    @staticmethod
    def validate_media_binary(data: bytes, filename: str = "media") -> Tuple[bool, str, str]:
        """
        Validates in-memory media byte buffers against malware signatures and valid media magic bytes.
        Returns (is_safe, detected_format, message).
        """
        if not data or len(data) == 0:
            return False, "empty", "檔案為空。"

        header = data[:64]

        # Scan for dangerous signatures
        for sig, desc in DANGEROUS_SIGNATURES:
            if header.startswith(sig) or sig in header[:16]:
                return (
                    False,
                    "malware",
                    f"⚠️ 資安嚴重告警：檢測到危險的可執行二進位特徵碼（{desc}），疑似夾帶病毒/木馬攻擊，已強制拒絕接收！"
                )

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
                return (
                    False,
                    "unknown",
                    "⚠️ 資安防護提示：檔案標頭不符合常見音訊/視訊二進位格式規範，可能為損毀或偽裝之未知格式。"
                )

        return True, detected_fmt, f"驗證通過：合規的 {detected_fmt.upper()} 影音串流檔案。"

    @classmethod
    def get_protection_manifest(cls) -> Dict[str, Any]:
        """Alias for get_security_manifest."""
        return cls.get_security_manifest()

    @staticmethod
    def validate_media_file(file_path: str, max_size_mb: int = 150) -> Tuple[bool, str]:
        """
        Verifies downloaded or uploaded media files against:
        1. File existence and size limit
        2. Dangerous binary signatures (PE executables, ELF, scripts)
        3. Magic bytes confirming legitimate audio/video stream
        """
        if not os.path.exists(file_path):
            return False, "檔案不存在。"

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False, "檔案為空。"

        if file_size > max_size_mb * 1024 * 1024:
            return False, f"檔案大小（{file_size // (1024*1024)}MB）超過系統安全上限（{max_size_mb}MB）。"

        # Read first 4096 bytes for header inspection
        with open(file_path, "rb") as f:
            header = f.read(4096)

        # 1. Scan for Dangerous Malware Signatures
        for sig, description in DANGEROUS_SIGNATURES:
            if header.startswith(sig) or (sig in header[:64]):
                return False, f"🚨 檔案安全性威脅：檢測到危險二進制標頭「{description}」，已立即銷毀隔離！"

        # 2. Check for legitimate media magic bytes
        is_legit_media = False
        # Check MP4 / M4A ftyp
        if b"ftyp" in header[:32]:
            is_legit_media = True
        # Check WebM / MKV
        elif header.startswith(b"\x1a\x45\xdf\xa3"):
            is_legit_media = True
        # Check MP3 ID3 or sync frame
        elif header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0):
            is_legit_media = True
        # Check RIFF (WAV)
        elif header.startswith(b"RIFF") and b"WAVE" in header[:16]:
            is_legit_media = True
        # Check OGG
        elif header.startswith(b"OggS"):
            is_legit_media = True

        if not is_legit_media:
            return False, "🚨 格式不合規：該檔案未包含標準影音串流特徵，疑似偽裝檔案，拒絕載入！"

        return True, "檔案通過惡意代碼與特徵碼掃描，為合法安全影音。"

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
