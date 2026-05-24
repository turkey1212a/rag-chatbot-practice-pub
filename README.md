# RAG PDF Ingestion MVP

PDFをページ単位で取り込み、OpenAI Embeddingsでベクトル化してPostgreSQL + pgvectorに保存するMVPです。

現時点の実装範囲は、最初のゴールである「PDFをページ単位で取り込み、embedding付きでDBへ保存し、取り込み結果を確認する」までです。チャット回答生成とUIは次フェーズです。

## 構成

- `docker-compose.yml`: PostgreSQL + pgvector と FastAPI backend を起動
- `backend/app`: FastAPI、DB初期化、PDF取り込み処理
- `backend/scripts/ingest_pdf.py`: 取り込み確認用CLI
- `.env.example`: ローカル環境変数のサンプル

既存のAngular/NestJS雛形ファイルは残っていますが、このMVPでは使用しません。

## セットアップ

`.env.example`をコピーして`.env`を作成します。

```bash
cp .env.example .env
```

`.env`の主な項目です。

```text
POSTGRES_DB=rag_chatbot
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=rag_password
POSTGRES_PORT=5432
BACKEND_PORT=8000
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
UPLOAD_DIR=uploads
MAX_PDF_PAGES=300
```

`OPENAI_API_KEY`は必ず自分のキーに変更してください。APIキー、アップロードPDF、DBデータはGit管理対象外です。

## 起動

PostgreSQL + pgvector と backend を起動します。

```bash
docker compose up --build
```

起動後、ヘルスチェックを確認します。

```bash
curl http://localhost:8000/health
```

期待する応答:

```json
{"status":"ok"}
```

FastAPI起動時に以下を自動で実行します。

- `vector`拡張を有効化
- `pgcrypto`拡張を有効化
- `documents`テーブルを作成
- `page_chunks`テーブルを作成
- embedding用のpgvector indexを作成

## PDF取り込み

### アップロードAPI

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@/path/to/sample.pdf"
```

### 指定パス取り込みAPI

Dockerコンテナ内から見えるパスを指定します。リポジトリの`backend/uploads`はコンテナの`/app/uploads`にマウントされています。

```bash
cp /path/to/sample.pdf backend/uploads/sample.pdf
curl -X POST http://localhost:8000/documents/ingest \
  -H "Content-Type: application/json" \
  -d '{"path":"/app/uploads/sample.pdf"}'
```

### CLI

DBだけをDockerで起動して、ローカルPythonから取り込む場合:

```bash
docker compose up -d db
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/ingest_pdf.py /path/to/sample.pdf
```

この場合、リポジトリルートの`.env`にある`DATABASE_URL`は`localhost`向けのままで動きます。

## 取り込み確認

取り込み済みPDF一覧:

```bash
curl http://localhost:8000/documents
```

ページチャンク一覧。本文は返さず、ページ番号と文字数だけ返します。

```bash
curl http://localhost:8000/documents/{document_id}/chunks
```

## 類似ページ検索

質問文をembedding化し、pgvectorのcosine距離で類似ページを検索します。

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"question":"この資料で説明されている評価方法は？","limit":5}'
```

検索結果にはPDF名、ページ番号、本文抜粋、類似度スコアを含めます。

## API仕様

### `GET /health`

DB接続を確認します。

### `POST /documents/upload`

PDFファイルをアップロードして取り込みます。同名PDFがすでに登録済みの場合、既存のdocumentとpage chunksを削除して再登録します。

### `POST /documents/ingest`

backendから参照できるPDFパスを指定して取り込みます。

Request:

```json
{"path":"/app/uploads/sample.pdf"}
```

### `GET /documents`

取り込み済みPDFの一覧を返します。

### `GET /documents/{document_id}/chunks`

指定PDFの保存済みページチャンクを確認します。PDF本文はレスポンスに含めません。

### `POST /search`

質問文をembedding化して、保存済みページから類似ページを検索します。

Request:

```json
{"question":"この資料で説明されている評価方法は？","limit":5}
```

Response:

```json
[
  {
    "pdf_name": "sample.pdf",
    "page_number": 3,
    "excerpt": "本文抜粋...",
    "similarity_score": 0.8123
  }
]
```

## DBスキーマ概要

`documents`

- `id`
- `file_name`
- `source_path`
- `page_count`
- `created_at`

`page_chunks`

- `id`
- `document_id`
- `file_name`
- `page_number`
- `chunk_text`
- `embedding vector(1536)`
- `created_at`

PDFは必ず1ページ1チャンクで保存します。ページ内の追加分割は今回は実装していません。

## 既知の制約

- チャット回答生成、簡易UIは未実装です。
- テキスト抽出できないページは`skipped_pages`として記録し、embedding保存をスキップします。
- `MAX_PDF_PAGES`を超えるPDFは取り込みを拒否します。
- embedding次元数を変える場合は、既存DBボリュームを作り直すか、テーブル再作成が必要です。
- ログにPDF本文やAPIキーを出さない方針のため、確認APIも本文を返しません。

## DBを初期化し直す

開発中にDBを作り直したい場合:

```bash
docker compose down -v
docker compose up --build
```
