#!/usr/bin/env python3
"""
Redmine添付ファイル削除スクリプト
Redmineからチケットとその添付ファイルを削除するメインスクリプト
"""

import argparse
import asyncio
import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# srcディレクトリをPythonパスに追加
sys.path.append(str(Path(__file__).parent.parent / "src"))

from redmine_browser_client import RedmineBrowserClient, get_browser_settings
from redmine_client import RedmineClient

# ログディレクトリの作成
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)


# ログ設定
def setup_logging():
    """ログ設定を初期化"""
    # ログファイルのパス
    log_file = log_dir / "redmine_deleter.log"

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
        "limit": int(os.getenv("REDMINE_LIMIT", "10")),
        "offset_start": int(os.getenv("REDMINE_OFFSET_START", "0")),
        "offset_end": int(os.getenv("REDMINE_OFFSET_END", "0")),
        "sort": os.getenv("REDMINE_SORT", "created_on:asc"),
        "request_interval": float(os.getenv("REDMINE_REQUEST_INTERVAL", "1.0")),
        "verify_ssl": os.getenv("REDMINE_VERIFY_SSL", "true").lower() == "true",
        "retry_count": int(os.getenv("REDMINE_RETRY_COUNT", "3")),
        "retry_interval": float(os.getenv("REDMINE_RETRY_INTERVAL", "5.0")),
    }

    # ブラウザ設定を取得
    (
        browser_base_url,
        headless,
        timeout,
        delete_interval,
        retry_count,
        retry_interval,
    ) = get_browser_settings()
    config.update(
        {
            "browser_base_url": browser_base_url,
            "browser_headless": headless,
            "browser_timeout": timeout,
            "delete_interval": delete_interval,
            "browser_retry_count": retry_count,
            "browser_retry_interval": retry_interval,
        }
    )

    # 必須項目のチェック
    if not config["base_url"]:
        raise ValueError("REDMINE_BASE_URL環境変数が設定されていません")

    if not config["browser_base_url"]:
        raise ValueError("REDMINE_BROWSER_BASE_URL環境変数が設定されていません")

    if not config["username"] or not config["password"]:
        raise ValueError(
            "ブラウザ操作用の認証情報が不足しています。REDMINE_USERNAME/REDMINE_PASSWORDを設定してください"
        )

    if not config["api_key"]:
        logger.warning(
            "REDMINE_API_KEYが設定されていません。チケット取得に影響する可能性があります"
        )

    return config


async def get_issues_with_attachments(client: RedmineClient, config: dict):
    """添付ファイルが存在するチケットを取得"""
    try:
        offset_start = config["offset_start"]
        offset_end = config["offset_end"]
        limit = config["limit"]
        sort = config["sort"]
        request_interval = config["request_interval"]

        logger.info(
            f"チケット取得範囲: offset_start={offset_start}, offset_end={offset_end}"
        )
        logger.info(f"リクエスト間隔: {request_interval}秒")

        issues_with_attachments = []
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

            # 添付ファイルが存在するチケットをフィルタリング
            for issue in issues:
                if issue.has_attachments():
                    attachments = issue.get_attachments()
                    issues_with_attachments.append(
                        {
                            "id": issue.id,
                            "subject": issue.subject,
                            "attachment_count": len(attachments),
                        }
                    )
                    logger.info(
                        f"  添付ファイルあり: チケット {issue.id} ({len(attachments)}件)"
                    )

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
                await asyncio.sleep(request_interval)

        logger.info(f"添付ファイルが存在するチケット: {len(issues_with_attachments)}件")
        logger.info(f"処理したバッチ数: {batch_count}")

        return issues_with_attachments

    except Exception as e:
        logger.error(f"チケット取得処理中にエラーが発生しました: {e}")
        raise


async def delete_attachments_from_issues(
    browser_client: RedmineBrowserClient, issues_with_attachments: list
):
    """添付ファイルを削除"""
    try:
        if not issues_with_attachments:
            logger.info("削除対象のチケットがありません")
            return {}

        # チケットIDのリストを作成
        issue_ids = [issue["id"] for issue in issues_with_attachments]

        logger.info(f"{len(issue_ids)} 件のチケットの添付ファイル削除を開始します")

        # ブラウザクライアントで削除を実行
        results = await browser_client.delete_attachments_from_issues(issue_ids)

        # 結果を詳細にログ出力
        success_count = 0
        for issue_id, success in results.items():
            issue_info = next(
                (issue for issue in issues_with_attachments if issue["id"] == issue_id),
                None,
            )
            if success:
                success_count += 1
                logger.info(
                    f"チケット {issue_id} ({issue_info['subject'] if issue_info else 'Unknown'}): 削除成功"
                )
            else:
                logger.error(
                    f"チケット {issue_id} ({issue_info['subject'] if issue_info else 'Unknown'}): 削除失敗"
                )

        logger.info(f"削除完了: {success_count}/{len(issue_ids)} 件のチケットで成功")
        return results

    except Exception as e:
        logger.error(f"削除処理中にエラーが発生しました: {e}")
        raise


async def main():
    try:
        # 設定を取得
        config = setup_environment()

        # Redmine APIクライアントを初期化
        logger.info("Redmine APIクライアントを初期化中...")
        api_client = RedmineClient(
            base_url=config["base_url"],
            api_key=config["api_key"],
            username=config["username"],
            password=config["password"],
            verify_ssl=config["verify_ssl"],
        )

        # 添付ファイルが存在するチケットを取得
        issues_with_attachments = await get_issues_with_attachments(api_client, config)

        if not issues_with_attachments:
            logger.info("削除対象のチケットがありません。処理を終了します。")
            return

        # 削除確認
        total_attachments = sum(
            issue["attachment_count"] for issue in issues_with_attachments
        )
        logger.warning(
            f"以下の {len(issues_with_attachments)} 件のチケットから {total_attachments} 件の添付ファイルを削除します:"
        )

        for issue in issues_with_attachments:
            logger.warning(
                f"  チケット {issue['id']}: {issue['subject']} ({issue['attachment_count']}件)"
            )

        # ユーザー確認（環境変数でスキップ可能）
        confirm_skip = (
            os.getenv("REDMINE_DELETE_CONFIRM_SKIP", "false").lower() == "true"
        )
        if not confirm_skip:
            try:
                response = input("\n本当に削除しますか？ (yes/no): ").strip().lower()
                if response not in ["yes", "y"]:
                    logger.info("ユーザーによって削除がキャンセルされました")
                    return
            except KeyboardInterrupt:
                logger.info("ユーザーによって削除がキャンセルされました")
                return

        # Redmineブラウザクライアントを初期化
        logger.info("Redmineブラウザクライアントを初期化中...")
        async with RedmineBrowserClient(
            base_url=config["browser_base_url"],
            username=config["username"],
            password=config["password"],
            headless=config["browser_headless"],
            timeout=config["browser_timeout"],
            delete_interval=config["delete_interval"],
            retry_count=config["browser_retry_count"],
            retry_interval=config["browser_retry_interval"],
        ) as browser_client:
            # ログイン
            if not await browser_client.login():
                logger.error("ログインに失敗しました。処理を終了します。")
                return

            # 添付ファイルを削除
            await delete_attachments_from_issues(
                browser_client, issues_with_attachments
            )

        logger.info("処理が正常に完了しました")

    except KeyboardInterrupt:
        logger.info("ユーザーによって処理が中断されました")
        sys.exit(1)
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
