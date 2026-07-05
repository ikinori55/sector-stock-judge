# Sector Stock Judge

日本株・米国株のセクター強弱判定システム。
「セクター分析して」と言われたら **sector-analysis スキル** を必ず使う。

## 構成

| 要素 | パス | 役割 | モデル |
|------|------|------|--------|
| Skill | `.claude/skills/sector-analysis/` | ワークフロー本体 (データ取得→視覚化→サマリー) | — |
| Script | `scripts/sector_data.py` | ETF価格取得・4期間リターン・強弱判定 → JSON | — |
| Script | `scripts/sector_report.py` | JSON → HTMLヒートマップレポート | — |
| Script | `scripts/sector_history.py` | 日次30日・週次13週の対ベンチマーク相対リターン → JSON | — |
| Script | `scripts/sector_history_report.py` | 相対ヒートマップHTML（日次・週次） | — |
| Agent | `sector-data-collector` | データ更新の実行のみ | haiku |
| Agent | `jp-sector-analyst` | 日本株セクターの背景分析 | sonnet |
| Agent | `us-sector-analyst` | 米国株セクターの背景分析 | sonnet |
| Agent | `sector-strategist` | 日米統合・最終見解 | opus |

## データ仕様

- 日本: TOPIX-17 ETF (1617.T〜1633.T)、ベンチマーク TOPIX (1306.T)
- 米国: SPDRセクターETF 11本 (XLK等)、ベンチマーク SPY
- 期間: 1日=1営業日 / 1週間=5 / 1ヶ月=21 / 3ヶ月=63営業日
- 判定: ベンチマーク相対リターン符号の加重和 (weights 1/2/3/4) → 強気〜弱気の5段階
- 勢い: 短期ランク(1d,1w) − 長期ランク(1m,3m) → 強まっている/横ばい/弱まっている
- 出力: `data/sector_YYYY-MM-DD.json` (日次スナップショット・履歴として保持), `reports/sector_report_YYYY-MM-DD.html`
- 相対時系列: `data/history_YYYY-MM-DD.json`（日次30営業日・週次13週の対ベンチマーク相対リターン）→ `reports/history_latest.html`
- 深掘り: `data/analysis_latest.json`（jp/us/strategist の背景分析md）→ `sector_report.py --analysis` で `reports/latest.html` に「背景分析」セクション追記

## エージェントチームの使い分け

- 通常の「セクター分析して」→ スキルのStep1-4（スクリプト実行＋サマリー）を実行し、Step5で深掘り要否を選択式で確認
- 深掘り選択時／後から「詳しく」「なぜ」→ jp/us-sector-analyst（スコープに応じて）→ sector-strategist で統合し、結果を `data/analysis_latest.json` 経由で `reports/latest.html` に反映
- 「データだけ更新して」→ sector-data-collector

## 実行環境

- Python 3.10 / yfinance 1.4.1 (インストール済み)
- スクリプトは必ずプロジェクトルートから実行 (相対パス data/, reports/ に出力)
