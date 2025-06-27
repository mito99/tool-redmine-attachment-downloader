# Redmine添付ファイルダウンローダー

Redmineからチケットとその添付ファイルを一括ダウンロード・削除するPythonツールです。

## 機能

- Redmineのチケット一覧を取得（REST API使用）
- チケットに添付されたファイルを自動ダウンロード
- **チケットに添付されたファイルを自動削除（Playwright使用）**
- 範囲指定によるチケット取得（オフセット開始・終了）
- バッチ処理による大量データの効率的な処理
- 詳細なログ出力（ローテーション機能付き）
- ダウンロードディレクトリの自動クリア機能
- サーバー負荷軽減のための間隔制御機能
- URLエンコードされたファイル名の自動デコード機能

## インストール

### 前提条件

- Python 3.11以上
- uv（パッケージマネージャー）

### セットアップ

```bash
# リポジトリをクローン
git clone <repository-url>
cd tool-redmine-attachment-downloader

# 依存関係をインストール
uv sync

# Playwrightのブラウザをインストール（添付ファイル削除機能を使用する場合）
python scripts/install_playwright.py
```

## 設定

### 環境変数

以下の環境変数を設定してください：

```bash
# 必須
export REDMINE_BASE_URL="https://your-redmine-instance.com"

# 認証（APIキーまたはユーザ名・パスワードのいずれか）
export REDMINE_API_KEY="your-api-key"
# または
export REDMINE_USERNAME="your-username"
export REDMINE_PASSWORD="your-password"

# オプション
export REDMINE_DOWNLOAD_DIR="downloads"        # ダウンロードディレクトリ（デフォルト: downloads）
export REDMINE_LIMIT="10"                      # 1回の取得件数（デフォルト: 10）
export REDMINE_OFFSET_START="0"                # 開始オフセット（デフォルト: 0）
export REDMINE_OFFSET_END="0"                  # 終了オフセット（0の場合は制限なし）
export REDMINE_SORT="created_on:asc"           # ソート順（デフォルト: created_on:asc）
export REDMINE_CLEAR_DOWNLOADS="true"          # ダウンロードディレクトリをクリアする（デフォルト: true）
export REDMINE_REQUEST_INTERVAL="1.0"          # リクエスト間隔（秒）（デフォルト: 1.0）
export REDMINE_DOWNLOAD_INTERVAL="0.5"         # ダウンロード間隔（秒）（デフォルト: 0.5）
export REDMINE_VERIFY_SSL="true"               # SSL証明書の検証を行う（デフォルト: true）
export REDMINE_RETRY_COUNT="3"                 # リトライ回数（デフォルト: 3）
export REDMINE_RETRY_INTERVAL="5.0"            # リトライ間隔（秒）（デフォルト: 5.0）
export REDMINE_BASE_TIMEOUT="15"               # 基本タイムアウト時間（秒）（デフォルト: 15）
export REDMINE_TIMEOUT_INCREMENT="15"          # タイムアウト増加時間（秒）（デフォルト: 15）
export REDMINE_API_RETRY_COUNT="3"             # APIリクエスト失敗時のリトライ回数（デフォルト: 3）
export REDMINE_API_RETRY_INTERVAL="5.0"        # APIリクエストリトライ間隔（秒）（デフォルト: 5.0）
export REDMINE_API_BASE_TIMEOUT="30"           # APIリクエスト基本タイムアウト時間（秒）（デフォルト: 30）
export REDMINE_API_TIMEOUT_INCREMENT="10"      # APIリクエストタイムアウト増加時間（秒）（デフォルト: 10）

# 添付ファイル削除機能用の設定
export REDMINE_BROWSER_HEADLESS="true"         # ブラウザのヘッドレスモード（デフォルト: true）
export REDMINE_BROWSER_TIMEOUT="30"            # ブラウザ操作のタイムアウト（秒）（デフォルト: 30）
export REDMINE_DELETE_INTERVAL="1.0"           # 削除操作間の待機時間（秒）（デフォルト: 1.0）
export REDMINE_DELETE_RETRY_COUNT="3"          # 削除失敗時のリトライ回数（デフォルト: 3）
export REDMINE_DELETE_RETRY_INTERVAL="2.0"     # 削除リトライ間隔（秒）（デフォルト: 2.0）
export REDMINE_DELETE_CONFIRM_SKIP="false"     # 削除確認をスキップする（デフォルト: false）
```

## 使用方法

### 添付ファイルのダウンロード

```bash
# 基本的な使用方法
python scripts/donwload_attachments.py

# 環境変数を使用した詳細設定
export REDMINE_LIMIT="20"
export REDMINE_OFFSET_START="0"
export REDMINE_OFFSET_END="100"
python scripts/donwload_attachments.py
```

### 添付ファイルの削除

```bash
# 基本的な使用方法（削除確認あり）
python scripts/delete_attachments.py

# 削除確認をスキップする場合
export REDMINE_DELETE_CONFIRM_SKIP="true"
python scripts/delete_attachments.py

# ヘッドレスモードを無効にしてブラウザを表示
export REDMINE_BROWSER_HEADLESS="false"
python scripts/delete_attachments.py
```

### 使用例

#### 全チケットの添付ファイルをダウンロード
```bash
python scripts/donwload_attachments.py
```

#### 特定範囲のチケットの添付ファイルを削除
```bash
export REDMINE_LIMIT="20"
export REDMINE_OFFSET_START="100"
export REDMINE_OFFSET_END="200"
python scripts/delete_attachments.py
```

#### 最新のチケットから添付ファイルを削除（高速処理）
```bash
export REDMINE_LIMIT="10"
export REDMINE_SORT="created_on:desc"
export REDMINE_DELETE_INTERVAL="0.5"
python scripts/delete_attachments.py
```

## 動作仕様

### 添付ファイル削除機能

1. **ブラウザ操作**: Playwrightを使用してRedmineのWebインターフェースを操作
2. **ログイン処理**: 指定されたユーザ名・パスワードでRedmineにログイン
3. **チケット取得**: REST APIを使用して添付ファイルが存在するチケットを取得
4. **削除処理**: 各チケットページに移動し、添付ファイルの削除ボタンをクリック
5. **確認ダイアログ**: 削除確認ダイアログが表示された場合は自動的に「OK」をクリック
6. **間隔制御**: 削除操作間に指定された間隔で待機

### 削除確認機能

1. **削除対象の表示**: 削除対象となるチケットと添付ファイル数を事前に表示
2. **ユーザー確認**: 削除実行前にユーザーの確認を求める
3. **確認スキップ**: `REDMINE_DELETE_CONFIRM_SKIP=true`で確認をスキップ可能

### ブラウザ設定

1. **ヘッドレスモード**: デフォルトで有効（`REDMINE_BROWSER_HEADLESS=true`）
2. **タイムアウト設定**: ブラウザ操作のタイムアウト時間（デフォルト: 30秒）
3. **削除間隔**: 削除操作間の待機時間（デフォルト: 1.0秒）

## ログ機能

### ログファイルの配置

```
logs/
├── redmine_downloader.log      # 現在のログファイル
├── redmine_downloader.log.1    # バックアップファイル1
├── redmine_downloader.log.2    # バックアップファイル2
├── redmine_downloader.log.3    # バックアップファイル3
├── redmine_downloader.log.4    # バックアップファイル4
└── redmine_downloader.log.5    # バックアップファイル5
```

### ローテーション設定

- **最大ファイルサイズ**: 10MB
- **バックアップファイル数**: 5個
- **エンコーディング**: UTF-8
- **自動作成**: `logs`ディレクトリは自動的に作成されます

### ログレベル

- **ファイルログ**: DEBUGレベル以上（詳細な情報）
- **コンソールログ**: INFOレベル以上（重要な情報のみ）

### ログに含まれる情報

- ダウンロード範囲の設定
- 間隔設定の表示
- ディレクトリクリアの実行状況
- 各バッチの処理状況
- 間隔待機の実行状況
- ファイル名のデコード・変換状況
- チケットごとの添付ファイル数
- ダウンロード成功・失敗の詳細
- 処理統計情報

## エラーハンドリング

- ネットワークエラー: 自動的に次のバッチに進む
- 認証エラー: 処理を停止
- ファイルダウンロードエラー: 個別のエラーとして記録し、他のファイルは継続処理
- ディレクトリクリアエラー: 処理を停止
- レート制限エラー: 間隔を長くして再実行を推奨
- ファイル名デコードエラー: 元のファイル名を使用して処理を継続
- **リトライ機能**: ダウンロード失敗時は設定された回数まで自動リトライ

## パフォーマンスチューニング

### 推奨設定

#### 高速処理（サーバー負荷が低い場合）
```bash
python src/main.py --request-interval 0.5 --download-interval 0.1
```

#### 標準処理（バランス重視）
```bash
python src/main.py --request-interval 1.0 --download-interval 0.5
```

#### 低速処理（サーバー負荷が高い場合）
```bash
python src/main.py --request-interval 3.0 --download-interval 2.0
```

### 注意事項

- 間隔を短くしすぎるとサーバーに負荷がかかる可能性があります
- 間隔を長くしすぎると処理時間が大幅に増加します
- サーバーの設定やネットワーク状況に応じて適切な間隔を設定してください

## トラブルシューティング

### よくある問題

1. **認証エラー**
   - APIキーまたはユーザ名・パスワードが正しいか確認
   - RedmineのAPIアクセス権限を確認

2. **ネットワークエラー**
   - Redmineサーバーにアクセス可能か確認
   - ファイアウォール設定を確認

3. **SSL証明書エラー（社内プロキシ環境など）**
   - 社内プロキシ環境で証明書検証エラーが発生する場合
   - `export REDMINE_VERIFY_SSL="false"`を設定してSSL検証を無効化
   - 注意: セキュリティ上のリスクがあるため、信頼できる環境でのみ使用してください

4. **レート制限エラー**
   - 間隔を長くして再実行
   - `--request-interval`と`--download-interval`を増加

5. **タイムアウトエラー**
   - 大きなファイルや遅いネットワーク環境で発生する可能性があります
   - 基本タイムアウト時間を増加: `export REDMINE_DOWNLOAD_BASE_TIMEOUT="30"`
   - タイムアウト増加時間を調整: `export REDMINE_DOWNLOAD_TIMEOUT_INCREMENT="20"`
   - ネットワーク環境に応じて適切なタイムアウト時間を設定してください

6. **APIリクエストエラー**
   - チケット一覧取得時に発生する可能性があります
   - APIリクエストの基本タイムアウト時間を増加: `export REDMINE_API_BASE_TIMEOUT="60"`
   - APIリクエストのタイムアウト増加時間を調整: `export REDMINE_API_TIMEOUT_INCREMENT="15"`
   - APIリクエストのリトライ回数を増加: `export REDMINE_API_RETRY_COUNT="5"`
   - サーバーの負荷が高い場合は間隔を長くして再実行してください

7. **ディスク容量不足**
   - ダウンロードディレクトリの空き容量を確認
   - 不要なファイルを削除

8. **ディレクトリクリアエラー**
   - ダウンロードディレクトリの権限を確認
   - 他のプロセスがファイルを使用していないか確認

9. **ファイル名エンコーディングエラー**
   - ファイル名のデコードに失敗した場合は元のファイル名で保存されます
   - ログでデコードエラーの詳細を確認してください

10. **ログファイルサイズ過大**
    - `logs`ディレクトリ内の古いログファイルを削除
    - ローテーション設定を調整（コード内で変更可能）

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。
