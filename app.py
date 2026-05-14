"""
Calendario Liturgico Luterano
=============================

App Streamlit que consulta:
- Blog Teologia e Liturgia Luterana, especialmente o arquivo de 2023.
- Pagina "Tempo da Igreja" da IELB.

O app evita depender obrigatoriamente de feedparser/bs4. Usa apenas biblioteca
padrao, com requests como opcional.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import streamlit as st

try:
    import requests

    REQUESTS_OK = True
except Exception:
    requests = None
    REQUESTS_OK = False


BLOG_ARCHIVE_2023 = "https://teologiaeliturgialuterana.blogspot.com/2023/"
BLOG_FEED = "https://teologiaeliturgialuterana.blogspot.com/feeds/posts/default?alt=rss&max-results=100"
IELB_TEMPO_IGREJA = "https://www.ielb.org.br/tempo-da-igreja"

DATA_PATH = Path(__file__).parent / "pericopes.json"
HEADERS = {"User-Agent": "CalendarioLiturgicoLuterano/1.0"}

MESES = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

CORES_POR_TEMPO = {
    "advento": "Azul ou roxo",
    "natal": "Branco",
    "epifania": "Branco",
    "cinzas": "Roxo",
    "quaresma": "Roxo",
    "ramos": "Vermelho ou roxo",
    "paixao": "Preto",
    "paixão": "Preto",
    "pascoa": "Branco",
    "páscoa": "Branco",
    "ascensao": "Branco",
    "ascensão": "Branco",
    "pentecostes": "Vermelho",
    "trindade": "Branco",
    "reforma": "Vermelho",
    "todos os santos": "Branco",
}

FALLBACK_DATAS = {
    "2026-01-06": {
        "titulo": "Epifania de Nosso Senhor",
        "data": "2026-01-06",
        "cor": "Branco",
        "serie": "",
        "leituras": ["Isaias 60.1-6", "Efesios 3.1-12", "Mateus 2.1-12"],
        "fonte": "fallback local",
    },
    "2026-02-18": {
        "titulo": "Quarta-Feira de Cinzas",
        "data": "2026-02-18",
        "cor": "Roxo",
        "serie": "",
        "leituras": [],
        "fonte": "fallback local",
    },
    "2026-04-03": {
        "titulo": "Sexta-Feira Santa",
        "data": "2026-04-03",
        "cor": "Preto",
        "serie": "",
        "leituras": [],
        "fonte": "fallback local",
    },
    "2026-04-05": {
        "titulo": "Domingo da Pascoa",
        "data": "2026-04-05",
        "cor": "Branco",
        "serie": "",
        "leituras": [],
        "fonte": "fallback local",
    },
}


@dataclass
class BlogPost:
    title: str
    link: str
    summary: str = ""
    published: str = ""


st.set_page_config(
    page_title="Calendario Liturgico Luterano",
    page_icon="calendar",
    layout="wide",
    initial_sidebar_state="expanded",
)


def apply_style() -> None:
    st.markdown(
        """
        <style>
        .block-container { max-width: 1180px; padding-top: 1.4rem; }
        h1 { font-size: 1.7rem !important; }
        h2 { font-size: 1.25rem !important; }
        h3 { font-size: 1.08rem !important; }
        div[data-testid="stMetric"] {
            border: 1px solid #e3e7ee;
            border-radius: 8px;
            padding: .55rem .7rem;
            background: #ffffff;
        }
        .lit-card {
            border: 1px solid #e3e7ee;
            border-radius: 8px;
            padding: .85rem 1rem;
            background: #ffffff;
            margin: .45rem 0;
        }
        .muted { color: #64748b; font-size: .9rem; }
        .pill {
            display: inline-block;
            border-radius: 999px;
            padding: .15rem .55rem;
            background: #eef2ff;
            color: #3730a3;
            font-weight: 650;
            font-size: .78rem;
            margin: .1rem .15rem .1rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def norm(text: str) -> str:
    text = strip_accents(html.unescape(str(text or ""))).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_text(raw: str) -> str:
    raw = html.unescape(raw or "")
    raw = re.sub(r"<script.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style.*?</style>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"</(p|div|li|h1|h2|h3|h4|h5|tr)>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n\s+", "\n", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def fetch_text(url: str) -> str:
    if REQUESTS_OK and requests is not None:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.encoding or "utf-8"
            return resp.text
        except Exception:
            pass

    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError):
        return ""


def parse_pt_date(text: str) -> Optional[date]:
    text = html.unescape(text or "").strip()

    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))

    m = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zÀ-ÿ]+)\s+de\s+(\d{4})",
        text,
        flags=re.I,
    )
    if m:
        mes = MESES.get(norm(m.group(2)))
        if mes:
            return date(int(m.group(3)), mes, int(m.group(1)))

    return None


def infer_color(title: str) -> str:
    title_norm = norm(title)
    for key, color in CORES_POR_TEMPO.items():
        if norm(key) in title_norm:
            return color
    if "proprio" in title_norm or "apos pentecostes" in title_norm:
        return "Verde"
    return "A confirmar"


def looks_like_reading(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 80:
        return False
    if re.search(r"\b\d{1,3}[.,]\d", line):
        return True
    biblical_books = [
        "Sl", "Salmo", "Is", "Isaias", "Isaías", "Rm", "Romanos", "Mt",
        "Mateus", "Mc", "Marcos", "Lc", "Lucas", "Jo", "Joao", "João",
        "At", "Atos", "Ef", "Efesios", "Efésios", "Gn", "Genesis",
        "Êx", "Ex", "Ap", "Apocalipse", "Hb", "Hebreus", "1 Co", "2 Co",
        "1 Ts", "2 Ts", "1 Pe", "2 Pe", "Tg", "Tiago",
    ]
    return any(line.startswith(book + " ") for book in biblical_books)


@st.cache_data(ttl=3600, show_spinner=False)
def load_ielb_calendar() -> dict[str, dict[str, Any]]:
    html_text = fetch_text(IELB_TEMPO_IGREJA)
    events: dict[str, dict[str, Any]] = dict(FALLBACK_DATAS)

    if not html_text:
        return events

    text = clean_text(html_text)
    lines = [line.strip(" -\t") for line in text.splitlines() if line.strip()]

    for idx, line in enumerate(lines):
        lit_date = None
        title = ""

        if line.lower().startswith("dia "):
            lit_date = parse_pt_date(line)
            if lit_date:
                for candidate in lines[idx + 1 : idx + 6]:
                    if not candidate.lower().startswith("trienal") and not looks_like_reading(candidate):
                        title = candidate
                        break

        elif re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", line):
            lit_date = parse_pt_date(line)
            if lit_date:
                for candidate in reversed(lines[max(0, idx - 5) : idx]):
                    if not candidate.lower().startswith("selecione") and len(candidate) > 3:
                        title = candidate
                        break

        if not lit_date or not title:
            continue

        readings: list[str] = []
        serie = ""
        for candidate in lines[idx + 1 : idx + 14]:
            if candidate.lower().startswith("dia ") or re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", candidate):
                break
            if candidate.lower().startswith("trienal"):
                serie = candidate
            elif looks_like_reading(candidate):
                readings.append(candidate)

        key = lit_date.isoformat()
        current = events.get(key, {})
        events[key] = {
            "titulo": title,
            "data": key,
            "cor": current.get("cor") or infer_color(title),
            "serie": serie or current.get("serie", ""),
            "leituras": readings or current.get("leituras", []),
            "fonte": "IELB - Tempo da Igreja",
            "url": IELB_TEMPO_IGREJA,
        }

    local_data = load_local_pericopes()
    for key, value in local_data.items():
        if isinstance(value, dict):
            events[key] = {**events.get(key, {}), **normalize_local_entry(key, value)}

    return dict(sorted(events.items()))


@st.cache_data(show_spinner=False)
def load_local_pericopes() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return {}
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def normalize_local_entry(key: str, entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "titulo": entry.get("titulo") or entry.get("dia_liturgico") or "Data liturgica",
        "data": key,
        "cor": entry.get("cor", "A confirmar"),
        "serie": entry.get("serie", ""),
        "leituras": entry.get("leituras", []),
        "blog_keywords": entry.get("blog_keywords", []),
        "fonte": entry.get("fonte", "pericopes.json"),
    }


@st.cache_data(ttl=3600, show_spinner=False)
def load_blog_posts() -> list[dict[str, str]]:
    posts: list[BlogPost] = []
    posts.extend(parse_rss_posts(fetch_text(BLOG_FEED)))
    posts.extend(parse_archive_posts(fetch_text(BLOG_ARCHIVE_2023)))

    seen = set()
    unique: list[dict[str, str]] = []
    for post in posts:
        ident = post.link or post.title
        if not ident or ident in seen:
            continue
        seen.add(ident)
        unique.append(
            {
                "title": post.title,
                "link": post.link,
                "summary": clean_text(post.summary)[:700],
                "published": post.published,
            }
        )
    return unique


def parse_rss_posts(xml_text: str) -> list[BlogPost]:
    if not xml_text.strip():
        return []
    posts: list[BlogPost] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return posts

    for item in root.findall(".//item"):
        title = item.findtext("title") or "Sem titulo"
        link = item.findtext("link") or ""
        summary = item.findtext("description") or ""
        published = item.findtext("pubDate") or ""
        posts.append(BlogPost(title=clean_text(title), link=link, summary=summary, published=published))
    return posts


def parse_archive_posts(page_html: str) -> list[BlogPost]:
    if not page_html.strip():
        return []

    posts: list[BlogPost] = []
    pattern = re.compile(
        r"<h3[^>]*class=['\"][^'\"]*post-title[^'\"]*['\"][^>]*>.*?"
        r"<a[^>]+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>.*?</h3>",
        flags=re.I | re.S,
    )

    for link, title_html in pattern.findall(page_html):
        title = clean_text(title_html)
        if title and "Image" not in title:
            posts.append(BlogPost(title=title, link=html.unescape(link)))

    if posts:
        return posts

    anchor_pattern = re.compile(r"<a[^>]+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", flags=re.I | re.S)
    for link, title_html in anchor_pattern.findall(page_html):
        title = clean_text(title_html)
        if not title or len(title) < 4:
            continue
        if "teologiaeliturgialuterana.blogspot.com" not in link:
            continue
        if title.lower() in {"image", "nenhum comentario", "postar no blog"}:
            continue
        posts.append(BlogPost(title=title, link=html.unescape(link)))

    return posts


def keywords_for_event(event: dict[str, Any], selected: date) -> list[str]:
    explicit = event.get("blog_keywords") or []
    title = event.get("titulo", "")
    readings = event.get("leituras", [])
    words = [title, selected.strftime("%d/%m"), selected.strftime("%d/%m/%Y")]

    for reading in readings:
        book = re.split(r"\s+\d", reading, maxsplit=1)[0].strip()
        if book:
            words.append(book)

    for part in re.split(r"[-()]", title):
        part = part.strip()
        if len(part) >= 5:
            words.append(part)

    return [str(k) for k in [*explicit, *words] if str(k).strip()]


def search_posts(posts: list[dict[str, str]], keywords: list[str], limit: int = 8) -> list[dict[str, str]]:
    scored: list[tuple[int, dict[str, str]]] = []
    normalized_keywords = [norm(k) for k in keywords if len(norm(k)) >= 3]

    for post in posts:
        haystack = norm(f"{post.get('title', '')} {post.get('summary', '')}")
        score = 0
        for keyword in normalized_keywords:
            if keyword and keyword in haystack:
                score += 3 if keyword in norm(post.get("title", "")) else 1
        if score:
            scored.append((score, post))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [post for _, post in scored[:limit]]


def events_for_year(events: dict[str, dict[str, Any]], year: int) -> dict[str, dict[str, Any]]:
    return {key: value for key, value in events.items() if key.startswith(str(year))}


def nearest_event(events: dict[str, dict[str, Any]], target: date) -> str:
    if not events:
        return target.isoformat()
    keys = list(events.keys())
    return min(keys, key=lambda key: abs((date.fromisoformat(key) - target).days))


def render_event(event: dict[str, Any], selected: date) -> None:
    st.subheader(event.get("titulo", "Data liturgica"))

    m1, m2, m3 = st.columns(3)
    m1.metric("Data", selected.strftime("%d/%m/%Y"))
    m2.metric("Cor liturgica", event.get("cor", "A confirmar"))
    m3.metric("Serie", event.get("serie") or "Nao informada")

    st.markdown('<div class="lit-card">', unsafe_allow_html=True)
    st.markdown(f"**Fonte:** {event.get('fonte', 'Nao informada')}")
    if event.get("url"):
        st.markdown(f"[Abrir fonte]({event['url']})")
    st.markdown("</div>", unsafe_allow_html=True)

    readings = event.get("leituras") or []
    if readings:
        st.markdown("### Pericopes")
        for reading in readings:
            st.markdown(f"- {reading}")
    else:
        st.info("Nao encontrei pericopes estruturadas para esta data. A pagina da fonte ainda pode ter recursos relacionados.")


def render_blog(posts: list[dict[str, str]], keywords: list[str]) -> None:
    st.markdown("### Comentarios e recursos do blog")
    found = search_posts(posts, keywords)

    if keywords:
        visible = " ".join(f'<span class="pill">{html.escape(k)}</span>' for k in keywords[:10])
        st.markdown(visible, unsafe_allow_html=True)

    if not found:
        st.info("Nenhum comentario foi encontrado automaticamente para esta data.")
        return

    for post in found:
        st.markdown('<div class="lit-card">', unsafe_allow_html=True)
        st.markdown(f"**[{post['title']}]({post['link']})**")
        if post.get("published"):
            st.caption(post["published"])
        if post.get("summary"):
            st.write(post["summary"][:260] + ("..." if len(post["summary"]) > 260 else ""))
        st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    apply_style()

    st.title("Calendario Liturgico Luterano")
    st.caption("Datas liturgicas, pericopes e comentarios a partir da IELB e do blog Teologia e Liturgia Luterana.")

    with st.sidebar:
        st.header("Fontes")
        st.markdown(f"[Tempo da Igreja - IELB]({IELB_TEMPO_IGREJA})")
        st.markdown(f"[Blog - arquivo 2023]({BLOG_ARCHIVE_2023})")
        st.markdown(f"[Feed do blog]({BLOG_FEED})")
        if st.button("Atualizar dados agora"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("Carregando calendario liturgico..."):
        events = load_ielb_calendar()
        posts = load_blog_posts()

    current_year = date.today().year
    years = sorted({date.fromisoformat(key).year for key in events.keys()})
    if current_year not in years:
        years.append(current_year)
        years = sorted(years)

    c1, c2 = st.columns([0.35, 0.65])
    with c1:
        year = st.selectbox("Ano", years, index=years.index(current_year) if current_year in years else 0)
    year_events = events_for_year(events, year)

    with c2:
        mode = st.radio("Selecao", ["Datas liturgicas", "Data manual"], horizontal=True)

    if mode == "Datas liturgicas" and year_events:
        options = [
            f"{date.fromisoformat(key).strftime('%d/%m/%Y')} - {value.get('titulo', 'Data liturgica')}"
            for key, value in year_events.items()
        ]
        default_key = nearest_event(year_events, date.today())
        default_index = list(year_events.keys()).index(default_key)
        selected_label = st.selectbox("Data liturgica", options, index=default_index)
        selected_key = list(year_events.keys())[options.index(selected_label)]
        selected = date.fromisoformat(selected_key)
    else:
        selected = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        selected_key = selected.isoformat()

    event = events.get(selected_key)
    if not event:
        st.warning("Nao encontrei uma data liturgica cadastrada para esta data.")
        event = {
            "titulo": "Data sem cadastro",
            "data": selected_key,
            "cor": "A confirmar",
            "serie": "",
            "leituras": [],
            "fonte": "sem registro local",
            "blog_keywords": [selected.strftime("%d/%m"), selected.strftime("%B")],
        }

    left, right = st.columns([0.58, 0.42])
    with left:
        render_event(event, selected)
    with right:
        st.markdown("### Resumo das fontes")
        st.metric("Datas carregadas", len(events))
        st.metric("Posts do blog", len(posts))
        st.caption("Os dados sao armazenados em cache por 1 hora para deixar o app mais rapido.")

    keywords = keywords_for_event(event, selected)
    render_blog(posts, keywords)

    with st.expander("Adicionar ou corrigir datas manualmente"):
        st.write(
            "Voce pode criar um arquivo pericopes.json na mesma pasta do app. "
            "Esses dados complementam ou sobrescrevem o que veio da internet."
        )
        st.code(
            """
{
  "2026-01-06": {
    "dia_liturgico": "Epifania de Nosso Senhor",
    "cor": "Branco",
    "serie": "Trienal A",
    "leituras": [
      "Isaias 60.1-6",
      "Efesios 3.1-12",
      "Mateus 2.1-12"
    ],
    "blog_keywords": ["Epifania", "A Epifania de Nosso Senhor"]
  }
}
            """.strip(),
            language="json",
        )


if __name__ == "__main__":
    main()
