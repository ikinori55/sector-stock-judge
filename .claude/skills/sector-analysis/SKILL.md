---
name: sector-analysis
description: 日本株・米国株のセクター別強弱を1日/1週間/1ヶ月/3ヶ月の4期間で判定し、ヒートマップで視覚化するスキル。ユーザーが「セクター分析して」「セクターの強弱を見せて」「セクターローテーション」「どのセクターが強い/弱い」「強くなったセクター」「弱くなったセクター」「sector analysis」などと言ったら必ずこのスキルを使う。個別銘柄の分析は stock-analysis、銘柄スクリーニングは stock-screener の役割で、このスキルはセクター単位の強弱判定と視覚化を担う。
---

# セクター強弱分析スキル

日本株 (TOPIX-17 ETF) と米国株 (SPDR 11セクターETF) を対象に、
1日 / 1週間(5営業日) / 1ヶ月(21営業日) / 3ヶ月(63営業日) のリターンと
ベンチマーク相対強度から、各セクターの強気・弱気と勢いの変化を判定する。

## ワークフロー

### Step 1: データ取得と判定
```
python scripts/sector_data.py --market both
```
- 出力: `data/sector_YYYY-MM-DD.json` と `data/latest.json`
- 日本のみ/米国のみは `--market jp` / `--market us`

### Step 2: 時系列データ取得（相対ヒートマップ用）
```
python scripts/sector_history.py --market both
```
- 出力: `data/history_YYYY-MM-DD.json` と `data/history_latest.json`
- 直近30営業日の日次＋直近13週の週次、いずれも対ベンチマーク相対リターン

### Step 3: HTMLレポート生成
```
python scripts/sector_report.py
python scripts/sector_history_report.py
```
- `reports/latest.html`（判定＋4期間ヒートマップ）と
  `reports/history_latest.html`（日次・週次の相対ヒートマップ）を生成
- 生成後、両ファイルのパスをmarkdownリンクで提示する

### Step 4: チャットでのサマリー提示
`data/latest.json` を読み、強まった/弱まったセクター・総合判定の上位下位を簡潔にまとめ、
可能なら show_widget でヒートマップをインライン表示する。

### Step 5: 深掘りの要否を選択式で確認
Step 4 のサマリーを出した後、AskUserQuestion で「背景分析の深掘りをしますか？」を質問する。
選択肢:
- 日米＋統合で深掘り（推奨）／日本だけ深掘り／米国だけ深掘り／しない（サマリーのみで終了）

### Step 6: 深掘り実行（Step 5 で「しない」以外が選ばれた場合のみ）
1. スコープに応じてエージェントを起動:
   - 日米統合: `jp-sector-analyst` と `us-sector-analyst` を並列起動（Agentを同一メッセージで2回）→
     両者の結果を `sector-strategist` に渡し統合見解を得る
   - 日本のみ/米国のみ: 該当アナリスト1本のみ（統合はスキップ）
   - 各エージェントに `data/latest.json` のパスと担当市場の要約を渡す。出力はMarkdownで受け取る
2. 結果を `data/analysis_latest.json` に保存（Writeツール）:
   ```json
   {"as_of":"...","generated_at":"...","scope":"both|jp|us",
    "jp":"…md… or null","us":"…md… or null","strategist":"…md… or null"}
   ```
3. `python scripts/sector_report.py --analysis data/analysis_latest.json` で主レポート再生成
4. `reports/latest.html` と `reports/history_latest.html` のリンクを提示し、チャットにも深掘り要点を出す

### 後から深掘りだけ実行
「深掘りして」「背景分析して」「なぜ」「詳しく」等と言われたら、データ取得・ヒートマップ再生成は
せず、既存 `data/latest.json` を前提に Step 6 の共通手順だけ実行する（`data/latest.json` が
無ければ Step 1-3 を先に実行）。スコープが不明確なら AskUserQuestion で確認する。

## 判定ロジック (要点)

- **verdict**: 相対リターンの符号 × 期間ウェイト (1日=1, 1週=2, 1ヶ月=3, 3ヶ月=4) の合計スコア。
  +6以上=強気 / +2以上=やや強気 / ±2未満=中立 / -2以下=やや弱気 / -6以下=弱気
- **momentum**: 短期(1日・1週間)ランク平均 − 中長期(1ヶ月・3ヶ月)ランク平均。
  マイナス=順位が上がってきている=「強まっている」

## 注意

- yfinanceのレート制限で失敗したら10秒待って1回だけリトライする
- 市場休場日はデータの `as_of` が古くなるが、そのまま基準日として明記する
- 判定は機械的なモメンタム指標であり、ファンダメンタルズは含まない旨を必ず添える
