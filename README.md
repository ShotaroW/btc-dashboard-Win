# BTC Price Dashboard

リアルタイムのBitcoin価格を取得・蓄積し、AIによる解説と24時間価格予測を備えたダッシュボードです。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red)
![Prophet](https://img.shields.io/badge/Prophet-1.3-orange)
![Ollama](https://img.shields.io/badge/Ollama-local%20LLM-green)
![SQLite](https://img.shields.io/badge/SQLite-3-lightgrey)

---

## 機能

| 機能 | 説明 |
|---|---|
| リアルタイム価格表示 | Binance APIからBTC/USDTを取得し円換算して表示 |
| 価格履歴グラフ | 1日・1週間のインタラクティブなチャート |
| 24時間価格予測 | Prophetによる時系列予測と信頼区間の可視化 |
| AIによる予測解説 | ローカルLLM（Ollama）が予測結果を自然言語で解説 |
| AIチャット | BTCの価格傾向についてAIに質問できる |

---

## システム構成

```
Binance API ──┐
              ├──► fetcher.py ──► database.py (SQLite)
exchangerate  ┘                        │
                                       ▼
                                    app.py (Streamlit)
                                       │
                              ┌────────┴────────┐
                              ▼                 ▼
                         predictor.py       ai_chat.py
                         (Prophet)          (Ollama)
```

---

## 技術スタック

- **フロントエンド**: [Streamlit](https://streamlit.io/) + [Altair](https://altair-viz.github.io/)
- **価格取得**: Binance REST API / exchangerate.host / CoinGecko API
- **データ保存**: SQLite（`data/btc_data.db`）
- **価格予測**: [Prophet](https://facebook.github.io/prophet/)（Meta製時系列予測ライブラリ）
- **AI機能**: [Ollama](https://ollama.com/)（ローカルLLM、`qwen3.5:9b`使用）

---

## セットアップ

### 前提条件

- Python 3.10 以上
- [Ollama](https://ollama.com/) インストール済み

### 1. リポジトリをクローン

```bash
git clone https://github.com/ShotaroW/btc-dashboard-Win.git
cd btc-dashboard-Win
```

### 2. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

### 3. Ollamaモデルをダウンロード

```bash
ollama pull qwen3.5:9b
```

### 4. Ollamaを起動

```bash
ollama serve
```

### 5. アプリを起動

```bash
streamlit run app.py
```

ブラウザで http://localhost:8501 が開きます。

---

## プロジェクト構成

```
btc-dashboard-Win/
├── app.py                  # Streamlitメインアプリ
├── requirements.txt        # 依存パッケージ
├── src/
│   ├── fetcher.py          # BTC価格・為替レート取得
│   ├── database.py         # SQLiteへの保存・読み込み
│   ├── predictor.py        # Prophetによる価格予測
│   ├── ai_chat.py          # Ollamaとのチャット連携
│   └── analyze.py          # データ分析ユーティリティ
├── data/
│   └── btc_data.db         # 価格履歴DB（自動生成、Git管理外）
└── tests/
    ├── test_database.py    # DBテスト
    └── test_fetcher.py     # データ取得テスト
```

---

## Dockerで起動する場合

```bash
# Ollamaをホスト側で起動しておく
ollama serve

# コンテナをビルドして起動
docker compose up --build
```

http://localhost:8501 でアクセスできます。

---

## テスト

```bash
pytest tests/ -v
```

---

## 注意事項

- 本アプリのAI解説・価格予測は**投資アドバイスではありません**
- 価格データはリアルタイムに近いものですが、遅延が生じる場合があります
- Ollamaはローカルで動作するため、外部にデータは送信されません
