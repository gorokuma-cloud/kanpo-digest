# 官報 前日まとめ Discord自動配信システム

内閣府 官報発行サイト（https://www.kanpo.go.jp/）より前営業日発行分の官報全体目次（本紙・号外・政府調達等）を自動抽出し、重要カテゴリ別にまとめてDiscordへ毎朝自動配信するシステムです。

## 構成
- `kanpo_discord_digest.py`: 官報取得・目次解析・重要度抽出・Discord送信スクリプト（外部ライブラリ不要、Python標準機能のみで動作）
- `.github/workflows/daily_kanpo.yml`: 毎朝日本時間8:00（UTC 23:00）に自動起動するGitHub Actionsワークフロー

## 毎朝自動化（GitHub Actions）の導入手順
1. 本フォルダ（またはリポジトリ）の GitHub リポジトリを作成
2. GitHub の **Settings > Secrets and variables > Actions** に移動
3. **New repository secret** を作成:
   - Name: `DISCORD_WEBHOOK_URL`
   - Value: ご指定のWebhook URL
4. これにより、追加サーバーやPCの起動なしで、GitHub側から毎朝完全自動でDiscordへダイジェストが配信されます。
