# セクター分析 拡張設計 — 時系列相対ヒートマップ ＋ 深掘り選択フロー

作成日: 2026-07-05
更新: 2026-07-05（既存 history パイプライン発見に伴い方針改定）

## 目的

sector-analysis スキルに、独立した2つの拡張を加える。

- **拡張A: 時系列相対ヒートマップ** — 既存の日次ヒートマップ資産
  (`sector_history.py` / `sector_history_report.py`) を拡張し、
  (1) 日次30営業日を**対ベンチマーク相対リターン**で色付けするよう変更、
  (2) **週次3ヶ月（約13週）相対リターン**ヒートマップを追加する。
- **拡張B: 深掘り選択フロー** — 「セクター分析して」の際に背景分析（エージェント
  チームによる金利・為替・FRB等の解釈）を行うかを選択式で確認し、選ばれた場合は
  結果を HTMLレポートとチャットの両方に出力する。後から深掘りブロックだけの単独実行にも対応。

## 既存資産の前提（重要）

CLAUDE.md 未記載だが、以下が既に存在し稼働している:

- `scripts/sector_history.py`: 直近N営業日(既定30)の**日次リターン(%)**を収集
  → `data/history_{date}.json` / `data/history_latest.json`。`sector_data.py` から
  セクター定義 (`JP_SECTORS` 等) を import して再利用。ベンチマーク行を先頭に持ち、
  各セクターに `daily`(日次リターン配列) と `cum`(期間累積) を格納。
- `scripts/sector_history_report.py`: 上記JSONを「セクター×N営業日」ヒートマップHTML
  (`reports/sector_history_{date}.html` / `reports/history_latest.html`) に描画。
  固定セクター名列・固定累積列・縦書き日付ヘッダー・週区切り縦線・セルホバー(title)・
  全セル絶対値95パーセンタイルでの色正規化を実装済み。現状は**絶対リターン**で色付け。

方針: この資産を**作り直さず拡張**する。時系列ヒートマップ（日次・週次）は history
パイプラインに実装する。背景分析（拡張B）は主レポート `sector_report.py`
(`reports/latest.html`) に実装する。「セクター分析して」は主レポートと history レポートの
**2つのHTML**を出力し、両方のリンクを提示する（これは既存の運用実態を踏襲する形）。

確定事項（推奨案で確定）:
- 日次・週次とも **対ベンチマーク相対リターンに統一**（既存の絶対リターン表示は相対に置き換え）。
- 時系列ヒートマップは **history パイプラインを拡張**して実装（`sector_report.py` に新規実装しない）。

---

## 拡張A: 時系列相対ヒートマップ（history パイプライン拡張）

### セル値の定義（確定事項）

- **日次セル**（日付 t）: `(セクターの t 日の日次リターン%) − (ベンチマークの t 日の日次リターン%)`
- **週次セル**（週 w）: `(セクターの w 週の週次リターン%) − (ベンチマークの w 週の週次リターン%)`
  - 週の区切りは **カレンダー週（週末=金曜終値、pandas `W-FRI`）**、直近13週。
- 各セルは「その期間ごと」の相対リターン（累積ではない）。値の欠損は `null`。
- 相対化に伴い、ベンチマーク行は常に 0（相対 0）となるため、時系列ヒートマップの
  **ベンチマーク行は表示しない**（凡例で「緑=指数超過 / 赤=指数劣後」と明記）。

### データ層 — `scripts/sector_history.py`

`collect_market` を拡張。既存の `daily_returns()` を使い、ベンチマークの日次リターン系列を
基準日付軸として、各セクターの**相対**日次リターンを計算する。さらに週足を追加する。

日次（相対化）:
- `bench_daily = daily_returns(closes[bench])`、対象日付 = 直近 `days`(30) 営業日。
- 各セクター: `sec_daily = daily_returns(closes[tkr])`、各日 `rel = sec_daily[d] - bench_daily[d]`
  （どちらか欠損なら `null`）。出力キーは従来通り `daily`（中身が相対値に変わる）。
- 累積 `cum` は相対日次の単純合計（従来の `sum(vals)` ロジックのまま。中身が相対になる）。

週次（新規、直近13週）:
- 週足終値: `closes[tkr].resample("W-FRI").last()`、`pct_change()*100` で週次リターン。
- ベンチマークも同様に週次リターンを計算し、`rel = sec_weekly[w] - bench_weekly[w]`。
- 直近 `weeks`(既定13) 週ぶんを取り出す。欠損は `null`。
- 出力: market単位に `weekly_dates`（週末日 `YYYY-MM-DD` 配列）を追加し、
  各セクターに `weekly`（相対週次配列）と `weekly_cum`（相対週次の合計）を追加。

CLI引数追加: `--weeks`（既定13）。既存 `--days`（既定30）は据え置き。

JSON構造（market = `jp`/`us`、既存キー据え置き＋追加）:

```json
{
  "generated_at": "...", "days": 30, "weeks": 13,
  "jp": {
    "label": "日本株 (TOPIX-17)",
    "benchmark": { "ticker": "1306.T", "name": "TOPIX",
                   "daily": [ ... ], "weekly": [ ... ] },   // 参考保持（描画では非表示）
    "dates": ["2026-05-22", ...],           // 日次: 直近30営業日
    "weekly_dates": ["2026-04-10", ...],    // 週次: 直近13週の週末日
    "sectors": [
      { "ticker": "1617.T", "name": "食品",
        "daily": [0.12, -0.34, null, ...], "cum": 1.2,       // 相対日次（30個）
        "weekly": [0.5, -1.2, ...], "weekly_cum": -0.8 }     // 相対週次（13個）
    ]
  },
  "us": { ... }
}
```

- 相対化の結果、`benchmark.daily`/`benchmark.weekly` は全て概ね 0。JSONには保持するが
  描画では使わない（下記表示層でベンチマーク行を出さない）。

### 表示層 — `scripts/sector_history_report.py`

`build_html` を、market ごとに **日次ヒートマップ＋週次ヒートマップの2表**を出すよう変更する。

- 既存 `market_table(m, cap)` を汎用化: `heatmap_table(m, cap, dates_key, cells_key, cum_key, unit_label)`
  として、日次(`dates`/`daily`/`cum`)と週次(`weekly_dates`/`weekly`/`weekly_cum`)の両方を描ける形にする。
- **ベンチマーク行は描画しない**（相対化により常に0のため）。セクター行のみ。
- 色スケール `color_scale` / `cell_color` は流用。ただし日次と週次で値幅が異なるため、
  **日次用 cap と週次用 cap を別々に**算出する（それぞれ該当セルの絶対値95パーセンタイル）。
- 週次表のヘッダーは週末日付（`MM/DD`）。週区切り縦線は日次表のみ（週次は各列が1週なので不要）。
- セルホバー `title` に「{セクター名} {日付}: {符号付き相対値}%」を出す（従来は値のみだが相対に変更）。
- 見出し・凡例の文言を「対ベンチマーク相対リターン（緑=指数超過 / 赤=指数劣後）」に更新。
- 各市場: 「日次相対（直近30営業日）」表 → 「週次相対（直近3ヶ月）」表 の順で並べる。

`main()`: 入出力は据え置き（`data/history_latest.json` → `reports/history_latest.html`）。

---

## 拡張B: 深掘り選択フロー

### 標準フロー（`.claude/skills/sector-analysis/SKILL.md`）

1. **データ取得** — `python scripts/sector_data.py --market both`
2. **時系列データ取得** — `python scripts/sector_history.py --market both`
3. **ベースHTML生成** — `python scripts/sector_report.py` と
   `python scripts/sector_history_report.py`（この時点で判定＋時系列ヒートマップのHTMLが必ず残る）
4. **チャットにサマリー提示** — 従来どおり（4期間＋強弱＋show_widget）
5. **深掘りの要否を選択式で質問**（AskUserQuestion、質問文「背景分析の深掘りをしますか？」）。
   まず軽いサマリー（Step4）を出してから質問する。選択肢:
   - **日米＋統合で深掘り（推奨）** — jp/us アナリスト並列 → sector-strategist 統合
   - **日本だけ深掘り** — jp-sector-analyst のみ
   - **米国だけ深掘り** — us-sector-analyst のみ
   - **しない（サマリーのみで終了）**
6. 「しない」以外が選ばれた場合のみ深掘り実行 → 共通手順で背景分析を生成し、
   主レポート再生成＋チャット提示。

### 深掘りの共通手順（標準フロー Step6 / 後から単独実行 で共用）

1. 選択スコープに応じてエージェント起動:
   - 日米統合: `jp-sector-analyst` と `us-sector-analyst` を**並列起動**（Agent同一メッセージ2回）
     → 両者の結果を `sector-strategist` に渡し統合見解を得る。
   - 日本のみ / 米国のみ: 該当アナリスト1本のみ（ストラテジスト統合はスキップ、`strategist` は null）。
   - 各エージェントに `data/latest.json` のパスと担当市場要約を渡す。出力は**Markdownテキスト**
     （現行 tools のまま変更不要）。
2. オーケストレータ（メインループ）が結果を集約し `data/analysis_latest.json` に保存:
   ```json
   {
     "as_of": "2026-07-03", "generated_at": "2026-07-05T01:14:49",
     "scope": "both",                 // "both" | "jp" | "us"
     "jp": "…日本の背景分析(md)… or null",
     "us": "…米国の背景分析(md)… or null",
     "strategist": "…統合見解(md)… or null"
   }
   ```
3. `python scripts/sector_report.py --analysis data/analysis_latest.json` で主レポート再生成。
   4期間ヒートマップの下に「背景分析」セクション（日本・米国・統合見解の各ブロック、
   `null` は省略）を追記。
4. 主レポート(`reports/latest.html`)と history レポートのリンクを提示し、チャットにも深掘り要点を提示。

### 後から深掘りだけ実行

ユーザーが後で「深掘りして」「背景分析して」「なぜ」「詳しく」等と言った場合:
- **データ取得もヒートマップ再生成もしない**。既存 `data/latest.json` を前提（無ければ Step1-3 を先に実行）。
- 要求スコープに応じて上記「深掘りの共通手順」を実行し、`data/analysis_latest.json` 更新 →
  `sector_report.py --analysis ...` で主レポートの背景分析セクションだけ差し替え再生成 → 提示。
- スコープ不明確なら AskUserQuestion で確認。

### 表示層 — `scripts/sector_report.py` の `--analysis` 対応

- 引数 `--analysis <path>` を追加（省略時は従来どおり4期間ヒートマップのみ＝後方互換）。
- 指定パスが存在し読み込めた場合、4期間ヒートマップ群の後ろに「背景分析」セクションを描画:
  - 「日本株の背景分析」「米国株の背景分析」「統合見解（ストラテジスト）」の3ブロック。
  - 各ブロックは対応フィールドが `null`/欠落なら描画しない。
  - Markdown→簡易HTML変換は最小限（見出し `#`〜`###`、箇条書き `-`、段落、太字 `**`）を
    自前の軽量関数で行い、外部ライブラリを増やさない。特殊文字はエスケープする。
- 指定パスが存在しない/壊れている場合は stderr に警告し、背景分析なしで通常生成
  （レポート生成自体は失敗させない）。

### ドキュメント更新

- `.claude/skills/sector-analysis/SKILL.md`: ワークフローを上記（時系列データ取得の追加、
  選択式ゲート、後から深掘り単独実行）に書き換え。history レポートと `--analysis` の使い方を明記。
- `CLAUDE.md`: 構成表に `sector_history.py` / `sector_history_report.py` を追記。
  「エージェントチームの使い分け」を新フローに更新。データ仕様に相対日次/週次の記述を追記。

---

## エラーハンドリング / エッジケース

- 日次30営業日・週次13週に満たない場合は取れる範囲だけ出力（軸自体を短くする）。
- あるセクターだけ欠損する日/週は当該セルのみ `null`（灰色セル＋ホバー「—」）。
- ベンチマーク欠損日はその日の全セクター相対が `null`。
- `color_scale` が全 `null` の場合は既存どおり 1.0 を返し 0 除算を回避。
- `data/analysis_latest.json` が無い/壊れている場合、`--analysis` 指定でも背景分析なしで通常生成。
- 単独市場の深掘りではストラテジスト統合を行わず `strategist` は `null`。
- エージェント失敗時も、Step3 で生成済みのベースレポート（判定＋時系列ヒートマップ）は残る。

## テスト / 検証

- `python scripts/sector_history.py --market both` → `data/history_latest.json` に
  `dates`(≒30) / `weekly_dates`(≒13) と各セクターの `daily`(相対・長さ=dates) /
  `weekly`(相対・長さ=weekly_dates) が出ることを確認。ベンチマーク行の `daily` が概ね0であることを確認。
- `python scripts/sector_history_report.py` → `reports/history_latest.html` に
  市場ごと「日次相対」「週次相対」の2ヒートマップが描画され、ベンチマーク行が無く、
  横スクロール・週区切り・ホバー（相対値）が機能することを確認。
- `python scripts/sector_report.py`（--analysis なし）→ 従来どおり4期間ヒートマップのみ、
  背景分析セクションが無いことを確認（後方互換）。
- ダミー `data/analysis_latest.json`（both / jp のみ / 壊れJSON）で
  `sector_report.py --analysis ...` を実行し、背景分析の描画・`null`ブロック省略・
  壊れJSON時フォールバックを確認。
- SKILL.md フローに沿い、選択式ゲート各分岐（both/jp/us/しない）と「後から深掘り」経路を確認。

## 非対象（YAGNI）

- RRG等の別チャート化はしない。
- 履歴JSON横断集計はしない（時系列は当日取得データから計算）。
- インタラクティブ操作（期間切替UI等）は入れない。静的HTMLのまま。
- 深掘りのスケジュール自動化・定期実行はしない（手動トリガーのみ）。
- Markdown→HTML変換に外部ライブラリは導入しない（軽量自前変換）。
- 主レポートと history レポートの1枚統合はしない（既存資産再利用のため2枚のまま）。
