#!/usr/bin/env python3
"""
Redmine添付ファイルダウンローダー
Redmineからチケットとその添付ファイルをダウンロードするメインスクリプト
"""

import argparse
import logging
import logging.handlers
import os
import shutil
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# srcディレクトリをPythonパスに追加
sys.path.append(str(Path(__file__).parent.parent / "src"))

from redmine_client import RedmineClient

# ログディレクトリの作成
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)


# ログ設定
def setup_logging():
    """ログ設定を初期化"""
    # ログファイルのパス
    log_file = log_dir / "redmine_downloader.log"

    # フォーマッターの設定
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # ローテーティングファイルハンドラーの設定
    # 最大10MB、バックアップファイル5個まで保持
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"  # 10MB
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # コンソールハンドラーの設定
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # ルートロガーの設定
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # アプリケーションロガーの設定
    logger = logging.getLogger(__name__)
    logger.info(f"ログファイル: {log_file.absolute()}")

    return logger


# ログ設定を初期化
logger = setup_logging()


# .envファイルを読み込む
def load_environment_file():
    """
    .envファイルから環境変数を読み込む
    カレントディレクトリ、プロジェクトルート、ホームディレクトリの順に探索
    """
    env_paths = [
        ".env",  # カレントディレクトリ
        os.path.join(os.path.dirname(__file__), "..", ".env"),  # プロジェクトルート
        os.path.expanduser("~/.env"),  # ホームディレクトリ
    ]

    for env_path in env_paths:
        if os.path.exists(env_path):
            load_dotenv(env_path)
            logger.info(f".envファイルを読み込みました: {env_path}")
            return

    logger.info(".envファイルは見つかりませんでした。環境変数を使用します。")


# .envファイルを読み込む
load_environment_file()


def setup_environment():
    """環境変数から設定を読み込み"""
    config = {
        "base_url": os.getenv("REDMINE_BASE_URL"),
        "api_key": os.getenv("REDMINE_API_KEY"),
        "username": os.getenv("REDMINE_USERNAME"),
        "password": os.getenv("REDMINE_PASSWORD"),
        "download_dir": os.getenv("REDMINE_DOWNLOAD_DIR", "downloads"),
        "limit": int(os.getenv("REDMINE_LIMIT", "10")),
        "offset_start": int(os.getenv("REDMINE_OFFSET_START", "0")),
        "offset_end": int(os.getenv("REDMINE_OFFSET_END", "0")),
        "sort": os.getenv("REDMINE_SORT", "created_on:asc"),
        "clear_downloads": os.getenv("REDMINE_CLEAR_DOWNLOADS", "true").lower()
        == "true",
        "request_interval": float(os.getenv("REDMINE_REQUEST_INTERVAL", "1.0")),
        "download_interval": float(os.getenv("REDMINE_DOWNLOAD_INTERVAL", "0.5")),
        "verify_ssl": os.getenv("REDMINE_VERIFY_SSL", "true").lower() == "true",
        "retry_count": int(os.getenv("REDMINE_RETRY_COUNT", "3")),
        "retry_interval": float(os.getenv("REDMINE_RETRY_INTERVAL", "5.0")),
    }

    # 必須項目のチェック
    if not config["base_url"]:
        raise ValueError("REDMINE_BASE_URL環境変数が設定されていません")

    if not config["api_key"] and (not config["username"] or not config["password"]):
        raise ValueError(
            "認証情報が不足しています。REDMINE_API_KEYまたはREDMINE_USERNAME/REDMINE_PASSWORDを設定してください"
        )

    return config


def create_download_directory(download_dir: str, clear_downloads: bool = True):
    """ダウンロードディレクトリを作成・クリア"""
    path = Path(download_dir)

    if clear_downloads and path.exists():
        logger.info(f"ダウンロードディレクトリをクリア中: {path.absolute()}")
        try:
            shutil.rmtree(path)
            logger.info("ダウンロードディレクトリをクリアしました")
        except Exception as e:
            logger.error(f"ダウンロードディレクトリのクリアに失敗しました: {e}")
            raise

    path.mkdir(parents=True, exist_ok=True)
    logger.info(f"ダウンロードディレクトリを作成しました: {path.absolute()}")


def download_attachments(client: RedmineClient, config: dict):
    """添付ファイルをダウンロード"""
    try:
        offset_start = config["offset_start"]
        offset_end = config["offset_end"]
        limit = config["limit"]
        sort = config["sort"]
        request_interval = config["request_interval"]
        download_interval = config["download_interval"]
        retry_count = config["retry_count"]
        retry_interval = config["retry_interval"]

        logger.info(
            f"ダウンロード範囲: offset_start={offset_start}, offset_end={offset_end}"
        )
        logger.info(
            f"間隔設定: リクエスト間隔={request_interval}秒, ダウンロード間隔={download_interval}秒"
        )
        logger.info(
            f"リトライ設定: リトライ回数={retry_count}回, リトライ間隔={retry_interval}秒"
        )

        total_attachments = 0
        downloaded_attachments = 0
        current_offset = offset_start
        batch_count = 0

        while True:
            # offset_endが設定されている場合の範囲チェック
            if offset_end > 0 and current_offset >= offset_end:
                logger.info(
                    f"指定された範囲の終端に到達しました: {current_offset} >= {offset_end}"
                )
                break

            logger.info(
                f"チケット一覧を取得中... (offset={current_offset}, limit={limit})"
            )

            try:
                issues = client.get_issues(
                    limit=limit, offset=current_offset, sort=sort
                )
            except Exception as e:
                logger.error(f"チケット取得エラー (offset={current_offset}): {e}")
                break

            # 取得したチケットがない場合は終了
            if not issues:
                logger.info(f"チケットが取得できませんでした (offset={current_offset})")
                break

            batch_count += 1
            logger.info(
                f"バッチ {batch_count}: {len(issues)}件のチケットを取得しました (offset={current_offset})"
            )

            for i, issue in enumerate(issues, 1):
                logger.info(
                    f"チケット {i}/{len(issues)} を処理中: {issue.id} (全体のoffset={current_offset + i - 1})"
                )

                if issue.has_attachments():
                    attachments = issue.get_attachments()
                    total_attachments += len(attachments)

                    logger.info(f"  添付ファイル数: {len(attachments)}")

                    # チケットIDごとのディレクトリを作成（既存のディレクトリを削除して再作成）
                    issue_dir = Path(config["download_dir"]) / f"{issue.id}"
                    if issue_dir.exists():
                        import shutil

                        shutil.rmtree(issue_dir)
                    issue_dir.mkdir(parents=True)

                    # 添付ファイルをダウンロード
                    try:
                        issue.download_attachments(
                            str(issue_dir),
                            download_interval,
                            retry_count,
                            retry_interval,
                        )
                        downloaded_attachments += len(attachments)
                        logger.info(f"  ダウンロード完了: {issue_dir}")

                        # ダウンロード間隔を設定
                        if download_interval > 0:
                            logger.debug(
                                f"  ダウンロード間隔待機: {download_interval}秒"
                            )
                            time.sleep(download_interval)

                    except Exception as e:
                        logger.error(f"  ダウンロードエラー: {e}")
                else:
                    logger.info("  添付ファイルなし")

            # 次のバッチのためにオフセットを更新
            current_offset += limit

            # 取得件数がlimitより少ない場合は最後のバッチ
            if len(issues) < limit:
                logger.info(
                    f"最後のバッチです (取得件数={len(issues)} < limit={limit})"
                )
                break

            # リクエスト間隔を設定（最後のバッチでない場合）
            if request_interval > 0:
                logger.info(f"リクエスト間隔待機: {request_interval}秒")
                time.sleep(request_interval)

        logger.info(
            f"ダウンロード完了: {downloaded_attachments}/{total_attachments}件の添付ファイルをダウンロードしました"
        )
        logger.info(f"処理したバッチ数: {batch_count}")

    except Exception as e:
        logger.error(f"ダウンロード処理中にエラーが発生しました: {e}")
        raise


def main():
    try:
        # 設定を取得
        config = setup_environment()

        # ダウンロードディレクトリを作成・クリア
        create_download_directory(config["download_dir"], config["clear_downloads"])

        # Redmineクライアントを初期化
        logger.info("Redmineクライアントを初期化中...")
        client = RedmineClient(
            base_url=config["base_url"],
            api_key=config["api_key"],
            username=config["username"],
            password=config["password"],
            verify_ssl=config["verify_ssl"],
        )

        # 添付ファイルをダウンロード
        download_attachments(client, config)

        logger.info("処理が正常に完了しました")

    except KeyboardInterrupt:
        logger.info("ユーザーによって処理が中断されました")
        sys.exit(1)
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
