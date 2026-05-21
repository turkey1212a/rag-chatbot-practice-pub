# rag-chatbot-practice-pub

Angular と NestJS を Docker Compose で起動する、RAG chatbot 開発用の雛形アプリです。

## 構成

- `frontend`: Angular アプリをビルドし、nginx で配信します。
- `backend`: NestJS API サーバーです。
- `docker-compose.yml`: フロントエンドとバックエンドをまとめて起動します。

## 起動

### Docker Compose でアプリケーションを起動する

```bash
docker compose up --build
```

### ブラウザで確認する

起動後、ブラウザで以下にアクセス。

```text
http://localhost:8080
```

フロントエンドは `GET /api/message` を呼び、バックエンドから返された文字列を画面に表示します。

API の応答だけを確認したい場合は、以下を実行してください。

```bash
curl http://localhost:8080/api/message
```
