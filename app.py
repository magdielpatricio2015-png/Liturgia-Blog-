import json
from datetime import date
from pathlib import Path

import feedparser
import streamlit as st

BLOG_FEED = "https://teologiaeliturgialuterana.blogspot.com/feeds/posts/default?alt=rss"

st.set_page_config(
    page_title="Liturgia Blog",
    page_icon="⛪",
    layout="centered",
)

DATA_PATH = Path(__file__).parent / "pericopes.json"


@st.cache_data
def load_pericopes():
    if DATA_PATH.exists():
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {}


@st.cache_data(ttl=3600)
def load_blog_posts():
    feed = feedparser.parse(BLOG_FEED)
    posts = []
    for entry in feed.entries:
        posts.append({
            "title": entry.get("title", "Sem título"),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", ""),
            "published": entry.get("published", ""),
        })
    return posts


def search_posts(posts, keywords):
    results = []
    for post in posts:
        haystack = f"{post['title']} {post['summary']}".lower()
        if any(k.lower() in haystack for k in keywords):
            results.append(post)
    return results[:6]


st.title("⛪ Liturgia Blog")
st.write("Selecione uma data para ver as perícopes e comentários relacionados.")

selected = st.date_input("Data litúrgica", value=date.today(), format="DD/MM/YYYY")
key = selected.isoformat()

pericopes = load_pericopes()
info = pericopes.get(key)

if info:
    st.subheader(info["dia_liturgico"])
    st.write(f"**Cor litúrgica:** {info.get('cor', '—')}")

    st.markdown("### Perícopes do dia")
    for leitura in info.get("leituras", []):
        st.write(f"- {leitura}")

    keywords = info.get("blog_keywords", [info["dia_liturgico"]])
else:
    st.warning("Ainda não há perícopes cadastradas para esta data.")
    keywords = [selected.strftime("%d/%m"), selected.strftime("%B")]

st.markdown("### Comentários do blog")
with st.spinner("Buscando comentários..."):
    posts = load_blog_posts()
    found = search_posts(posts, keywords)

if found:
    for post in found:
        st.markdown(f"**[{post['title']}]({post['link']})**")
        if post.get("published"):
            st.caption(post["published"])
else:
    st.info("Nenhum comentário encontrado automaticamente para esta data.")

with st.expander("Como adicionar novas datas"):
    st.code(
        '''
"2026-01-06": {
  "dia_liturgico": "Epifania de Nosso Senhor",
  "cor": "branco",
  "leituras": [
    "Isaías 60.1-6",
    "Efésios 3.1-12",
    "Mateus 2.1-12"
  ],
  "blog_keywords": ["Epifania", "A Epifania de Nosso Senhor"]
}
        ''',
        language="json",
    )
