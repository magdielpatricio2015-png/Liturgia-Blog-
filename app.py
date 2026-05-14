"""
Calendario Liturgico Luterano
=============================

Consulta a pagina "Tempo da Igreja" da IELB e relaciona a data liturgica
selecionada com comentarios do blog Teologia e Liturgia Luterana.

Melhorias desta versao:
- Layout mais limpo e focado na data liturgica.
- Classificacao do tempo liturgico.
- Busca do blog priorizando o mesmo tempo liturgico e o mesmo domingo/festa.
- Comentario do blog exibido abaixo das pericopes, no fluxo principal.
- Sem dependencia obrigatoria de feedparser ou BeautifulSoup.
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
from datetime import date
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
BLOG_FEED = "https://teologiaeliturgialuterana.blogspot.com/feeds/posts/default?alt=rss&max-results=150"
IELB_TEMPO_IGREJA = "https://www.ielb.org.br/tempo-da-igreja"

DATA_PATH = Path(__file__).parent / "pericopes.json"
HEADERS = {"User-Agent": "CalendarioLiturgicoLuterano/1.1"}

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

TEMPOS_LITURGICOS = [
    ("Advento", ["advento"]),
    ("Natal", ["natal", "natividade"]),
    ("Epifania", ["epifania", "batismo de nosso senhor", "transfiguracao", "transfiguração"]),
    ("Quaresma", ["quaresma", "cinzas", "ramos", "paixao", "paixão"]),
    ("Pascoa", ["pascoa", "páscoa", "ressurreicao", "ressurreição", "ascensao", "ascensão"]),
    ("Pentecostes", ["pentecostes", "trindade"]),
    ("Tempo Comum", ["proprio", "próprio", "apos pentecostes", "após pentecostes"]),
    ("Festas e datas especiais", ["reforma", "todos os santos", "confissao", "confissão"]),
]

CORES_POR_TEMPO = {
    "Advento": "Azul ou roxo",
    "Natal": "Branco",
    "Epifania": "Branco",
    "Quaresma": "Roxo",
    "Pascoa": "Branco",
    "Pentecostes": "Vermelho",
    "Tempo Comum": "Verde",
    "Festas e datas especiais": "A confirmar",
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
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)


def apply_style() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] { background: #f7f5f0; }
        .block-container { max-width: 1180px; padding-top: 1.35rem; }
        h1 { font-size: 1.7rem !important; letter-spacing: 0 !important; margin-bottom: .15rem !important; }
        h2 { font-size: 1.22rem !important; letter-spacing: 0 !important; }
        h3 { font-size: 1.04rem !important; letter-spacing: 0 !important; }
        section[data-testid="stSidebar"] { background: #2f3a33; }
        section[data-testid="stSidebar"] * { color: #f7f5f0 !important; }
        div[data-testid="stMetric"] {
            border: 1px solid #ddd6c8;
            border-radius: 8px;
            padding: .55rem .7rem;
            background: #fffdf8;
        }
        .hero {
            border: 1px solid #ddd6c8;
            border-radius: 8px;
            background: #fffdf8;
            padding: 1rem 1.05rem;
            margin: .35rem 0 1rem 0;
        }
        .hero-title { font-size: 1.35rem; font-weight: 750; color: #243027; margin-bottom: .35rem; }
        .hero-sub { color: #5d665f; font-size: .94rem; }
        .lit-card {
            border: 1px solid #ddd6c8;
            border-radius: 8px;
            padding: .85rem 1rem;
            background: #fffdf8;
            margin: .45rem 0;
        }
        .comment-card {
            border: 1px solid #c7d2c5;
            border-left: 4px solid #43634c;
            border-radius: 8px;
            padding: .95rem 1rem;
            background: #fbfff9;
            margin: .55rem 0 .8rem 0;
        }
        .reading {
            border-bottom: 1px solid #ece5d8;
            padding: .42rem 0;
            font-size: .98rem;
        }
        .reading:last-child { border-bottom: 0; }
        .pill {
            display: inline-block;
            border-radius: 999px;
            padding: .14rem .55rem;
            background: #e8eee7;
            color: #2f4b38;
            font-weight: 650;
            font-size: .78rem;
            margin: .08rem .12rem .08rem 0;
        }
        .source-line { color: #69736c; font-size: .88rem; }
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
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))

    match = re.search(r"(\d{1,2})\s+de\s+([A-Za-zÀ-ÿ]+)\s+de\s+(\d{4})", text, flags=re.I)
    if match:
        mes = MESES.get(norm(match.group(2)))
        if mes:
            return date(int(match.group(3)), mes, int(match.group(1)))
    return None


def liturgical_season(title: str) -> str:
    title_norm = norm(title)
    for season, needles in TEMPOS_LITURGICOS:
        if any(norm(needle) in title_norm for needle in needles):
            return season
    return "Tempo Comum"


def infer_color(title: str) -> str:
    title_norm = norm(title)
    if "sexta-feira santa" in title_norm or "paixao" in title_norm:
        return "Preto"
    season = liturgical_season(title)
    return CORES_POR_TEMPO.get(season, "A confirmar")


def looks_like_reading(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 90:
        return False
    if re.search(r"\b\d{1,3}[.,]\d", line):
        return True
    books = [
        "Sl", "Salmo", "Is", "Isaias", "Isaías", "Rm", "Romanos", "Mt",
        "Mateus", "Mc", "Marcos", "Lc", "Lucas", "Jo", "Joao", "João",
        "At", "Atos", "Ef", "Efesios", "Efésios", "Gn", "Genesis", "Gênesis",
        "Ex", "Êx", "Ap", "Apocalipse", "Hb", "Hebreus", "1 Co", "2 Co",
        "1 Ts", "2 Ts", "1 Pe", "2 Pe", "Tg", "Tiago", "Fp", "Filipenses",
    ]
    return any(line.startswith(book + " ") for book in books)


@st.cache_data(show_spinner=False)
def load_local_pericopes() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return {}
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def normalize_local_entry(key: str, entry: dict[str, Any]) -> dict[str, Any]:
    title = entry.get("titulo") or entry.get("dia_liturgico") or "Data liturgica"
    return {
        "titulo": title,
        "data": key,
        "cor": entry.get("cor") or infer_color(title),
        "tempo": entry.get("tempo") or liturgical_season(title),
        "serie": entry.get("serie", ""),
        "leituras": entry.get("leituras", []),
        "blog_keywords": entry.get("blog_keywords", []),
        "fonte": entry.get("fonte", "pericopes.json"),
    }


@st.cache_data(ttl=3600, show_spinner=False)
def load_ielb_calendar() -> dict[str, dict[str, Any]]:
    html_text = fetch_text(IELB_TEMPO_IGREJA)
    events: dict[str, dict[str, Any]] = {
        key: {**value, "tempo": liturgical_season(value.get("titulo", ""))}
        for key, value in FALLBACK_DATAS.items()
    }

    if html_text:
        text = clean_text(html_text)
        lines = [line.strip(" -\t") for line in text.splitlines() if line.strip()]

        for idx, line in enumerate(lines):
            lit_date = None
            title = ""

            if line.lower().startswith("dia "):
                lit_date = parse_pt_date(line)
                if lit_date:
                    for candidate in lines[idx + 1 : idx + 7]:
                        if not candidate.lower().startswith("trienal") and not looks_like_reading(candidate):
                            title = candidate
                            break
            elif re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", line):
                lit_date = parse_pt_date(line)
                if lit_date:
                    for candidate in reversed(lines[max(0, idx - 6) : idx]):
                        if not candidate.lower().startswith("selecione") and len(candidate) > 3:
                            title = candidate
                            break

            if not lit_date or not title:
                continue

            readings: list[str] = []
            serie = ""
            for candidate in lines[idx + 1 : idx + 16]:
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
                "tempo": liturgical_season(title),
                "serie": serie or current.get("serie", ""),
                "leituras": readings or current.get("leituras", []),
                "fonte": "IELB - Tempo da Igreja",
                "url": IELB_TEMPO_IGREJA,
            }

    for key, value in load_local_pericopes().items():
        if isinstance(value, dict):
            events[key] = {**events.get(key, {}), **normalize_local_entry(key, value)}

    return dict(sorted(events.items()))


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
        title = clean_text(post.title)
        unique.append(
            {
                "title": title,
                "link": post.link,
                "summary": clean_text(post.summary)[:900],
                "published": post.published,
                "tempo": liturgical_season(title),
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
        posts.append(
            BlogPost(
                title=clean_text(item.findtext("title") or "Sem titulo"),
                link=item.findtext("link") or "",
                summary=item.findtext("description") or "",
                published=item.findtext("pubDate") or "",
            )
        )
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
        if len(title) < 4 or "teologiaeliturgialuterana.blogspot.com" not in link:
            continue
        if title.lower() in {"image", "nenhum comentario", "postar no blog"}:
            continue
        posts.append(BlogPost(title=title, link=html.unescape(link)))
    return posts


@st.cache_data(ttl=3600, show_spinner=False)
def load_post_comment(url: str) -> str:
    page = fetch_text(url)
    if not page:
        return ""

    candidates = [
        r"<div[^>]+class=['\"][^'\"]*post-body[^'\"]*['\"][^>]*>(.*?)</div>\s*<div[^>]+class=['\"][^'\"]*post-footer",
        r"<div[^>]+class=['\"][^'\"]*post-body[^'\"]*['\"][^>]*>(.*?)</div>",
        r"<article[^>]*>(.*?)</article>",
    ]
    for pattern in candidates:
        match = re.search(pattern, page, flags=re.I | re.S)
        if match:
            text = clean_text(match.group(1))
            text = remove_blog_noise(text)
            if len(text) > 80:
                return text
    return ""


def remove_blog_noise(text: str) -> str:
    lines = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        low = norm(clean)
        if low.startswith(("postado por", "marcadores:", "compartilhar", "nenhum comentario")):
            continue
        lines.append(clean)
    return "\n\n".join(lines)


def keywords_for_event(event: dict[str, Any], selected: date) -> list[str]:
    explicit = event.get("blog_keywords") or []
    title = event.get("titulo", "")
    season = event.get("tempo") or liturgical_season(title)
    words = [title, season, selected.strftime("%d/%m"), selected.strftime("%d/%m/%Y")]

    for part in re.split(r"[-()]", title):
        part = part.strip()
        if len(part) >= 5:
            words.append(part)

    return [str(k) for k in [*explicit, *words] if str(k).strip()]


def search_posts(posts: list[dict[str, str]], event: dict[str, Any], selected: date, limit: int = 5) -> list[dict[str, str]]:
    title = event.get("titulo", "")
    season = event.get("tempo") or liturgical_season(title)
    keywords = [norm(k) for k in keywords_for_event(event, selected) if len(norm(k)) >= 3]
    title_norm = norm(title)
    season_norm = norm(season)

    scored: list[tuple[int, dict[str, str]]] = []
    for post in posts:
        post_title = norm(post.get("title", ""))
        haystack = norm(f"{post.get('title', '')} {post.get('summary', '')}")
        score = 0

        if title_norm and (title_norm in post_title or post_title in title_norm):
            score += 18
        if season_norm and season_norm in haystack:
            score += 8
        if post.get("tempo") == season:
            score += 6

        for keyword in keywords:
            if keyword in post_title:
                score += 5
            elif keyword in haystack:
                score += 2

        if selected.strftime("%d/%m") in haystack:
            score += 3

        if score:
            scored.append((score, post))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [post for _, post in scored[:limit]]


def events_for_year(events: dict[str, dict[str, Any]], year: int) -> dict[str, dict[str, Any]]:
    return {key: value for key, value in events.items() if key.startswith(str(year))}


def nearest_event(events: dict[str, dict[str, Any]], target: date) -> str:
    if not events:
        return target.isoformat()
    return min(events.keys(), key=lambda key: abs((date.fromisoformat(key) - target).days))


def render_event(event: dict[str, Any], selected: date) -> None:
    title = event.get("titulo", "Data liturgica")
    season = event.get("tempo") or liturgical_season(title)

    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-title">{html.escape(title)}</div>
            <div class="hero-sub">
                {selected.strftime("%d/%m/%Y")} · {html.escape(season)} ·
                Cor: {html.escape(event.get("cor", "A confirmar"))}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Tempo liturgico", season)
    m2.metric("Cor", event.get("cor", "A confirmar"))
    m3.metric("Serie", event.get("serie") or "Nao informada")

    readings = event.get("leituras") or []
    st.markdown("### Textos do dia")
    if readings:
        st.markdown('<div class="lit-card">', unsafe_allow_html=True)
        for reading in readings:
            st.markdown(f'<div class="reading">{html.escape(reading)}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Nao encontrei pericopes estruturadas para esta data. A fonte ainda pode ter informacoes relacionadas.")

    source = event.get("fonte", "Nao informada")
    if event.get("url"):
        st.markdown(f'<div class="source-line">Fonte: <a href="{event["url"]}">{html.escape(source)}</a></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="source-line">Fonte: {html.escape(source)}</div>', unsafe_allow_html=True)


def render_blog_comment(posts: list[dict[str, str]], event: dict[str, Any], selected: date) -> None:
    season = event.get("tempo") or liturgical_season(event.get("titulo", ""))
    found = search_posts(posts, event, selected)

    st.markdown("### Comentario do Teologia Luterana")
    st.markdown(f'<span class="pill">{html.escape(season)}</span>', unsafe_allow_html=True)

    if not found:
        st.info("Nenhum comentario do blog foi encontrado para este tempo liturgico.")
        return

    main_post = found[0]
    comment = load_post_comment(main_post.get("link", ""))
    st.markdown('<div class="comment-card">', unsafe_allow_html=True)
    st.markdown(f"**[{main_post['title']}]({main_post['link']})**")
    if main_post.get("published"):
        st.caption(main_post["published"])
    if comment:
        preview = comment[:1800].strip()
        st.write(preview + ("..." if len(comment) > len(preview) else ""))
    elif main_post.get("summary"):
        st.write(main_post["summary"])
    else:
        st.write("Abra o link para ler o comentario completo.")
    st.markdown("</div>", unsafe_allow_html=True)

    if len(found) > 1:
        with st.expander("Outros comentarios relacionados"):
            for post in found[1:]:
                st.markdown(f"- [{post['title']}]({post['link']})")


def render_sidebar(events: dict[str, dict[str, Any]], posts: list[dict[str, str]]) -> None:
    with st.sidebar:
        st.header("Fontes")
        st.markdown(f"[Tempo da Igreja - IELB]({IELB_TEMPO_IGREJA})")
        st.markdown(f"[Blog Teologia Luterana 2023]({BLOG_ARCHIVE_2023})")
        st.markdown(f"[Feed do blog]({BLOG_FEED})")
        st.divider()
        st.metric("Datas carregadas", len(events))
        st.metric("Posts do blog", len(posts))
        if st.button("Atualizar dados agora"):
            st.cache_data.clear()
            st.rerun()


def main() -> None:
    apply_style()

    st.title("Calendario Liturgico Luterano")
    st.caption("Escolha uma data liturgica; os comentarios do blog sao encaixados pelo mesmo tempo liturgico.")

    with st.spinner("Carregando calendario e blog..."):
        events = load_ielb_calendar()
        posts = load_blog_posts()

    render_sidebar(events, posts)

    current_year = date.today().year
    years = sorted({date.fromisoformat(key).year for key in events.keys()})
    if current_year not in years:
        years = sorted([*years, current_year])

    controls = st.container()
    with controls:
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
            "tempo": "Tempo Comum",
            "serie": "",
            "leituras": [],
            "fonte": "sem registro local",
            "blog_keywords": [selected.strftime("%d/%m")],
        }

    render_event(event, selected)
    render_blog_comment(posts, event, selected)

    with st.expander("Adicionar ou corrigir datas manualmente"):
        st.write("Crie um arquivo pericopes.json na mesma pasta do app para complementar ou corrigir os dados.")
        st.code(
            """
{
  "2026-01-06": {
    "dia_liturgico": "Epifania de Nosso Senhor",
    "cor": "Branco",
    "tempo": "Epifania",
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
