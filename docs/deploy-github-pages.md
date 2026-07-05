# iPhoneから見る：GitHub Pages 配信セットアップ

セクター強弱ダッシュボードを GitHub 上で生成し、公開URLで配信する手順。
別アカウントの iPhone（Claudeアプリ／Safari）からもURLを開くだけで閲覧できる。

## 仕組みの全体像

```
GitHub Actions（手動実行）
  → sector_data.py / sector_report.py / sector_trend.py などを実行
  → build_site.py が site/ にHTMLをまとめ index.html を生成
  → GitHub Pages が site/ を公開URLで配信
iPhone（どのアカウントでも）→ 公開URL を開く／ClaudeアプリにURLを貼って要約
```

- データ取得は **yfinance（APIキー不要）**。まずこれで動く簡易版。
- **手動実行のみ**（Actions画面の "Run workflow"）。定期実行にしたくなったらワークフローの `schedule` を有効化。
- **公開範囲はパブリック**（個人アカウントの Pages は非公開にできないため）。配信内容はセクター強弱という一般的な市場情報のみ。

## セットアップ手順

### 1. リポジトリを用意して push
このプロジェクト一式を GitHub リポジトリに push する（private でも public でも可。Pages 自体は公開になる）。

```
git init
git add .
git commit -m "sector dashboard"
git branch -M main
git remote add origin https://github.com/<あなた>/<repo>.git
git push -u origin main
```

### 2. GitHub Pages を「GitHub Actions」ソースで有効化
リポジトリの **Settings → Pages → Build and deployment → Source** を **「GitHub Actions」** に設定する。
（`/docs` フォルダ方式ではなく Actions デプロイを使うので、生成物をコミットする必要はない）

### 3. ワークフローを手動実行
リポジトリの **Actions → 「Build sector dashboard」→ Run workflow** を押す。
完了すると、ジョブの `Deploy to GitHub Pages` に公開URL（例 `https://<あなた>.github.io/<repo>/`）が表示される。

### 4. iPhoneから閲覧
- そのURLを **別アカウントの iPhone の Safari** で開く（ブックマーク推奨）。
- または **Claudeアプリに URL を貼る** → Claude がページを取得して要約・質問対応できる。

## 日本株を J-Quants（JPX API）で取得する（実装済み）

日本株は **JQUANTS_API_KEY があれば J-Quants の TOPIX-17 セクター指数**（公式データ）で取得し、
無ければ **yfinance の ETF にフォールバック**する。米国株は yfinance のまま。

### 設定手順
1. J-Quants にログインし、**ダッシュボードで APIキーを発行**する（V2 は APIキー方式。
   TOPIX-17 指数は上位プラン＝Premium が必要な場合がある。取得できないときはプランを確認）。
2. そのキーを **コードに書かず**、リポジトリの **Settings → Secrets and variables → Actions →
   New repository secret** に **`JQUANTS_API_KEY`** という名前で登録する。
   ※「リポジトリにAPIキーを保存」は、この **暗号化される Secrets** が正解。平文コミットはしない。
3. ワークフロー `build-report.yml` は既に `JQUANTS_API_KEY` を渡すよう設定済み。Run workflow するだけ。

### 挙動
- `scripts/jquants.py` が `x-api-key` ヘッダーで `GET /v2/indices/bars/daily` を叩き、
  TOPIX-17(0080-0090) と TOPIX(0000) の日次終値を取得する。
- ローカルで試すとき: `export JQUANTS_API_KEY=xxxx` してから各スクリプトを実行（未設定なら yfinance）。

## iPhoneのClaudeだけで分析する（PC不要の運用）

セットアップ後は、公開される `mobile.json`（各セクターの短期/中期/長期の5段階評価）を
iPhoneのClaudeプロジェクトから読ませるだけで「分析して」→表示ができる。
データ生成はクラウド（Actions の定期実行）で自走するのでPCは不要。
→ 具体的な設定と貼り付け用のカスタム指示は [iphone-claude-project.md](iphone-claude-project.md) を参照。

公開されるデータ:
- `https://<user>.github.io/<repo>/mobile.json` … iPhone/Claude用の軽量版
- `https://<user>.github.io/<repo>/latest.json` … フルデータ

## 注意・既知の制約

- **公開されます**：個人アカウントの GitHub Pages はアクセス制御不可（非公開は Enterprise のみ）。
  非公開が必須なら Cloudflare Pages / Netlify のパスワード保護を検討。
- **yfinance の CI 実行はまれに失敗**しうる（Yahoo のレート制限）。失敗時は再実行、恒常的なら J-Quants 化。
- 生成物 `site/` はローカル確認用。コミット不要（`.gitignore` 済み）。Actions が毎回作り直す。
