# Liturgia App

App web simples para selecionar uma data no calendário e ver:

- Dia litúrgico
- Cor litúrgica
- Perícopes do dia
- Comentários relacionados do blog Teologia e Liturgia Luterana

## Rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abra:

```text
http://127.0.0.1:8000
```

## Deploy no Render

1. Suba este projeto para o GitHub.
2. Crie uma conta em https://render.com
3. Clique em **New Web Service**.
4. Conecte o repositório do GitHub.
5. Configure:

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Dados

As perícopes iniciais ficam em:

```text
app/data/pericopes.json
```

Você pode adicionar mais datas seguindo o mesmo formato.

## Observação

A busca no blog usa o feed público do Blogspot e exibe título, link e resumo curto.
