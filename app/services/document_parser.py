"""Extraction de texte depuis PDF, DOCX, TXT brut et URL."""
from __future__ import annotations

import io
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "::1", "[::1]"}


async def parse_pdf(content: bytes) -> str:
    import pdfplumber  # import tardif — évite l'overhead au démarrage

    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


async def parse_docx(content: bytes) -> str:
    from docx import Document  # python-docx

    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def parse_txt(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


async def parse_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Schéma non supporté : {parsed.scheme}. Utilise http ou https.")
    if parsed.hostname in _BLOCKED_HOSTS:
        raise ValueError(f"Accès refusé à l'hôte : {parsed.hostname}")
    async with httpx.AsyncClient(follow_redirects=False, timeout=15) as client:
        response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)[:50_000]
