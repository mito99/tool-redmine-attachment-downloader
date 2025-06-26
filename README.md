# Redmine添付ファイルダウンローダー

Redmineからチケットとその添付ファイルを一括ダウンロードするPythonツールです。

## 機能

- Redmineのチケット一覧を取得
- チケットに添付されたファイルを自動ダウンロード
- 範囲指定によるチケット取得（オフセット開始・終了）
- バッチ処理による大量データの効率的な処理
- 詳細なログ出力（ローテーション機能付き）
- ダウンロードディレクトリの自動クリア機能
- サーバー負荷軽減のための間隔制御機能
- URLエンコードされたファイル名の自動デコード機能

## インストール

### 前提条件

- Python 3.8以上
- uv（パッケージマネージャー）

### セットアップ

```bash
# リポジトリをクローン
git clone <repository-url>
cd tool-redmine-attachment-downloader

# 依存関係をインストール
uv sync
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
```

## 使用方法

### 基本的な使用方法

```bash
# 環境変数を使用
python src/main.py

# コマンドライン引数を使用
python src/main.py \
  --base-url "https://your-redmine-instance.com" \
  --api-key "your-api-key" \
  --download-dir "downloads" \
  --limit 20 \
  --offset-start 0 \
  --offset-end 100 \
  --request-interval 2.0 \
  --download-interval 1.0
```

### コマンドライン引数

| 引数 | 説明 | デフォルト |
|------|------|------------|
| `--base-url` | RedmineのベースURL | 環境変数から取得 |
| `--api-key` | RedmineのAPIキー | 環境変数から取得 |
| `--username` | Redmineのユーザ名 | 環境変数から取得 |
| `--password` | Redmineのパスワード | 環境変数から取得 |
| `--download-dir` | ダウンロードディレクトリ | downloads |
| `--limit` | 1回の取得件数 | 10 |
| `--offset-start` | 開始オフセット | 0 |
| `--offset-end` | 終了オフセット（0の場合は制限なし） | 0 |
| `--sort` | ソート順 | created_on:asc |
| `--clear-downloads` | ダウンロードディレクトリをクリアする | true |
| `--no-clear-downloads` | ダウンロードディレクトリをクリアしない | - |
| `--request-interval` | リクエスト間隔（秒） | 1.0 |
| `--download-interval` | ダウンロード間隔（秒） | 0.5 |

### 使用例

#### 全チケットをダウンロード（ディレクトリをクリア）
```bash
python src/main.py --limit 50 --offset-start 0 --offset-end 0
```

#### 特定範囲のチケットをダウンロード（既存ファイルを保持、間隔を長めに設定）
```bash
python src/main.py --limit 20 --offset-start 100 --offset-end 200 --no-clear-downloads --request-interval 3.0 --download-interval 2.0
```

#### 最新のチケットからダウンロード（高速処理）
```bash
python src/main.py --limit 10 --sort "created_on:desc" --request-interval 0.5 --download-interval 0.1
```

## 動作仕様

### オフセット範囲処理

1. **開始オフセット（offset_start）**: ダウンロードを開始するチケットの位置
   - 指定されていない場合は0から開始
   - 0ベースのインデックス

2. **終了オフセット（offset_end）**: ダウンロードを終了するチケットの位置
   - 0の場合は制限なし（全チケットを処理）
   - 指定された値に達したら処理を終了

3. **バッチ処理**: 
   - `limit`で指定された件数ずつチケットを取得
   - 各バッチで添付ファイルをダウンロード
   - 取得できなくなったら自動的に終了

### ファイル名デコード機能

1. **URLエンコードデコード**: 
   - `urllib.parse.unquote`を使用してURLエンコードされたファイル名をデコード
   - 日本語などの2バイト文字を正しく表示

2. **ファイル名の安全化**:
   - Windows/Unix両方で使用できない文字を除去
   - 危険な文字（`<>:"/\|?*`など）を`_`に置換
   - 先頭・末尾の空白とドットを除去

3. **重複ファイル名の処理**:
   - 同名ファイルが存在する場合は連番を付与
   - 例: `document.pdf` → `document_1.pdf`

4. **エラーハンドリング**:
   - デコードに失敗した場合は元のファイル名を使用
   - 空のファイル名の場合は`unnamed_file`を使用

### サーバー負荷軽減機能

1. **リクエスト間隔（request_interval）**: チケット一覧取得間の待機時間
   - デフォルト: 1.0秒
   - バッチ間の間隔として適用
   - サーバーのAPI負荷を軽減

2. **ダウンロード間隔（download_interval）**: 添付ファイルダウンロード間の待機時間
   - デフォルト: 0.5秒
   - 各チケットの添付ファイルダウンロード後に適用
   - サーバーのファイル転送負荷を軽減

3. **間隔制御の効果**:
   - サーバーへの負荷を分散
   - レート制限エラーを回避
   - 安定したダウンロード処理を実現

### ダウンロードディレクトリのクリア

- **デフォルト動作**: ダウンロード開始前に既存のファイルを削除
- **無効化**: `--no-clear-downloads`オプションで既存ファイルを保持
- **安全性**: クリア処理はログに記録され、エラー時は処理を停止

### ダウンロード構造

```
downloads/
├── 123/                    # チケットID
│   ├── 添付ファイル1.pdf   # デコードされた日本語ファイル名
│   └── attachment2.jpg
├── 124/
│   └── ドキュメント.docx   # デコードされた日本語ファイル名
└── ...
```

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

3. **レート制限エラー**
   - 間隔を長くして再実行
   - `--request-interval`と`--download-interval`を増加

4. **ディスク容量不足**
   - ダウンロードディレクトリの空き容量を確認
   - 不要なファイルを削除

5. **ディレクトリクリアエラー**
   - ダウンロードディレクトリの権限を確認
   - 他のプロセスがファイルを使用していないか確認

6. **ファイル名エンコーディングエラー**
   - ファイル名のデコードに失敗した場合は元のファイル名で保存されます
   - ログでデコードエラーの詳細を確認してください

7. **ログファイルサイズ過大**
   - `logs`ディレクトリ内の古いログファイルを削除
   - ローテーション設定を調整（コード内で変更可能）

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。
