"""Extraction de texte depuis PDF, DOCX, TXT brut et URL."""
from __future__ import annotations

import io
import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.logging import get_logger

log = get_logger("document_parser")

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_safe_url(url: str) -> bool:
    """Vérifie que l'URL pointe vers une IP publique (protection SSRF)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname or ""
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(hostname))
        return not any(ip in net for net in _BLOCKED_NETWORKS)
    except Exception:
        return False


async def parse_pdf(content: bytes) -> str:
    import pdfplumber  # import tardif — évite l'overhead au démarrage

    try:
        parts: list[str] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
        return "\n\n".join(parts)
    except Exception as exc:
        log.warning("parse_pdf_failed", error=str(exc))
        raise


async def parse_docx(content: bytes) -> str:
    from docx import Document  # python-docx

    try:
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as exc:
        log.warning("parse_docx_failed", error=str(exc))
        raise


async def parse_txt(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


async def parse_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Schéma non supporté : {parsed.scheme}. Utilise http ou https.")
    if not _is_safe_url(url):
        raise ValueError(f"Accès refusé à l'hôte : {parsed.hostname}")
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=15) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
    except Exception as exc:
        log.warning("parse_url_failed", url=url, error=str(exc))
        raise
    soup = BeautifulSoup(response.text, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)[:50_000]
