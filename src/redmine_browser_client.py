"""
Redmineブラウザクライアント
Playwrightを使用してRedmineのWebインターフェースを操作し、添付ファイルを削除するクラス
"""

import asyncio
import base64
import logging
import os
import time
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Page, Playwright, async_playwright

logger = logging.getLogger(__name__)


def get_browser_settings() -> tuple[str, bool, int, float, int, float, str]:
    """
    環境変数からブラウザ設定を取得

    Returns:
        (browser_base_url, headless, timeout, delete_interval, retry_count, retry_interval, auth_method):
        ブラウザベースURL、ヘッドレスモード、タイムアウト、削除間隔、リトライ回数、リトライ間隔、認証方式のタプル
    """
    # ブラウザのベースURL、デフォルトはローカルのブラウザ
    browser_base_url = os.getenv("REDMINE_BROWSER_BASE_URL", "")

    # ヘッドレスモード、デフォルトTrue
    headless = os.getenv("REDMINE_BROWSER_HEADLESS", "true").lower() == "true"

    # ブラウザ操作のタイムアウト（秒）、デフォルト30秒
    timeout = int(os.getenv("REDMINE_BROWSER_TIMEOUT", "30"))

    # 削除操作間の待機時間（秒）、デフォルト1.0秒
    delete_interval = float(os.getenv("REDMINE_DELETE_INTERVAL", "1.0"))

    # 削除失敗時のリトライ回数、デフォルト3回
    retry_count = int(os.getenv("REDMINE_DELETE_RETRY_COUNT", "3"))

    # リトライ間隔（秒）、デフォルト2.0秒
    retry_interval = float(os.getenv("REDMINE_DELETE_RETRY_INTERVAL", "2.0"))

    # 認証方式、デフォルトは"login_page"（ログインページ認証）
    # "basic" または "login_page" を指定可能
    auth_method = os.getenv("REDMINE_AUTH_METHOD", "login_page").lower()

    return (
        browser_base_url,
        headless,
        timeout,
        delete_interval,
        retry_count,
        retry_interval,
        auth_method,
    )


class RedmineBrowserClient:
    """Redmineブラウザクライアント（Playwright使用）

    使用例:
        async with RedmineBrowserClient(
            base_url="https://your-redmine.com",
            username="your_username",
            password="your_password"
        ) as client:
            # ログイン
            await client.login()

            # チケットの添付ファイルを削除
            await client.delete_attachments_from_issue(123)
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        headless: bool = True,
        timeout: int = 30,
        delete_interval: float = 1.0,
        retry_count: int = 3,
        retry_interval: float = 2.0,
        auth_method: str = "login_page",
    ):
        """
        RedmineBrowserClientの初期化

        Args:
            base_url: RedmineのベースURL
            username: ユーザ名
            password: パスワード
            headless: ヘッドレスモード（デフォルト: True）
            timeout: ブラウザ操作のタイムアウト（秒）
            delete_interval: 削除操作間の待機時間（秒）
            retry_count: 削除失敗時のリトライ回数（デフォルト: 3）
            retry_interval: リトライ間隔（秒）（デフォルト: 2.0）
            auth_method: 認証方式（"basic" または "login_page"）（デフォルト: "login_page"）
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.headless = headless
        self.timeout = timeout * 1000  # Playwrightはミリ秒単位
        self.delete_interval = delete_interval
        self.retry_count = retry_count
        self.retry_interval = retry_interval
        self.auth_method = auth_method.lower()

        self.playwright: Optional[Playwright] = None
        self.browser = None
        self.page: Optional[Page] = None

        logger.info(f"Redmineブラウザクライアントを初期化しました: {base_url}")
        logger.info(f"認証方式: {self.auth_method}")
        logger.info(f"ヘッドレスモード: {headless}, タイムアウト: {timeout}秒")
        logger.info(f"リトライ設定: 回数={retry_count}回, 間隔={retry_interval}秒")

    async def _setup_browser(self):
        """ブラウザをセットアップ"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless, args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            self.page = await self.browser.new_page()

            # Basic認証方式の場合のみヘッダーを設定
            if self.auth_method == "basic":
                token = base64.b64encode(
                    f"{self.username}:{self.password}".encode()
                ).decode()
                self.page.set_extra_http_headers(
                    {
                        "Authorization": f"Basic {token}",
                    }
                )
                logger.info("Basic認証ヘッダーを設定しました")

            self.page.set_default_timeout(self.timeout)

            logger.info("ブラウザをセットアップしました")
        except Exception as e:
            logger.error(f"ブラウザのセットアップに失敗しました: {e}")
            raise

    async def login(self) -> bool:
        """
        Redmineにログイン（認証方式に応じて自動選択）

        Returns:
            ログイン成功時はTrue
        """
        if self.auth_method == "basic":
            # Basic認証の場合はログイン処理は不要（ヘッダーで認証済み）
            logger.info("Basic認証方式のため、ログイン処理をスキップします")
            return True
        elif self.auth_method == "login_page":
            return await self.login_with_page()
        else:
            logger.error(f"サポートされていない認証方式です: {self.auth_method}")
            return False

    async def login_with_page(self) -> bool:
        """
        Redmineにページログイン（従来のログインページ方式）

        Returns:
            ログイン成功時はTrue
        """
        try:
            if not self.page:
                await self._setup_browser()

            # ログインページに移動
            login_url = f"{self.base_url}/login"
            logger.info(f"ログインページに移動中: {login_url}")

            await self.page.goto(login_url)
            await self.page.wait_for_load_state("networkidle")

            # ユーザ名とパスワードを入力
            logger.info("ログイン情報を入力中...")
            await self.page.fill('input[name="username"]', self.username)
            await self.page.fill('input[name="password"]', self.password)

            # ログインボタンをクリック
            await self.page.click('input[type="submit"]')
            await self.page.wait_for_load_state("networkidle")

            # ログイン成功の確認（ダッシュボードまたはマイページにリダイレクトされる）
            current_url = self.page.url
            if "/login" not in current_url:
                logger.info("ページログインに成功しました")
                return True
            else:
                logger.error("ページログインに失敗しました")
                return False

        except Exception as e:
            logger.error(f"ページログイン処理中にエラーが発生しました: {e}")
            return False

    async def delete_attachments_from_issue(self, issue_id: int) -> bool:
        """
        指定されたチケットの添付ファイルを削除

        Args:
            issue_id: チケットID

        Returns:
            削除成功時はTrue
        """
        try:
            # チケットページに移動
            issue_url = f"{self.base_url}/issues/{issue_id}"
            logger.info(f"チケットページに移動中: {issue_url}")

            await self.page.goto(issue_url)
            await self.page.wait_for_load_state("networkidle")

            # 添付ファイルセクションを確認
            attachments_section = self.page.locator(".attachments")
            if not await attachments_section.count():
                logger.info(f"チケット {issue_id} には添付ファイルがありません")
                return True

            # 削除ボタンを探す
            delete_buttons = self.page.locator(".attachments .delete")
            attachment_count = await delete_buttons.count()

            if attachment_count == 0:
                logger.info(
                    f"チケット {issue_id} には削除可能な添付ファイルがありません"
                )
                return True

            logger.info(
                f"チケット {issue_id} の添付ファイル {attachment_count} 件を削除中..."
            )

            # 確認ダイアログのハンドラーを設定
            async def handle_dialog(dialog):
                try:
                    await dialog.accept()
                except Exception as e:
                    logger.warning(f"ダイアログ処理中にエラーが発生しました: {e}")

            self.page.on("dialog", handle_dialog)

            # 各添付ファイルを削除
            failed_attachments = []
            for i in range(attachment_count):
                success = False

                # リトライループ
                for attempt in range(self.retry_count + 1):  # 初回 + リトライ回数
                    try:
                        # 削除ボタンをクリック（常に最初の要素を削除）
                        delete_button = delete_buttons.nth(0)
                        await delete_button.click()

                        # 削除完了を待機
                        await asyncio.sleep(0.5)
                        await self.page.wait_for_load_state("networkidle")

                        if attempt > 0:
                            logger.info(
                                f"  添付ファイル {i + 1}/{attachment_count} のリトライ成功 ({attempt + 1}回目)"
                            )
                        else:
                            logger.info(
                                f"  添付ファイル {i + 1}/{attachment_count} を削除しました"
                            )

                        success = True
                        break

                    except Exception as e:
                        if attempt < self.retry_count:
                            logger.warning(
                                f"  添付ファイル {i + 1}/{attachment_count} の削除に失敗しました ({attempt + 1}/{self.retry_count + 1}回目): {e}"
                            )
                            logger.info(
                                f"    {self.retry_interval}秒後にリトライします..."
                            )
                            await asyncio.sleep(self.retry_interval)
                        else:
                            logger.error(
                                f"  添付ファイル {i + 1}/{attachment_count} の削除に最終的に失敗しました: {e}"
                            )
                            # 失敗した添付ファイルを記録
                            failed_attachments.append(
                                {
                                    "issue_id": issue_id,
                                    "attachment_index": i + 1,
                                    "total_attachments": attachment_count,
                                    "error": str(e),
                                }
                            )
                            continue

                # 削除間隔を設定（最後のファイルでない場合）
                if self.delete_interval > 0 and i < attachment_count - 1:
                    logger.debug(f"  削除間隔待機: {self.delete_interval}秒")
                    await asyncio.sleep(self.delete_interval)

            # ダイアログハンドラーを削除
            self.page.remove_listener("dialog", handle_dialog)

            # 失敗した添付ファイルがある場合は手動削除用のログを出力
            if failed_attachments:
                logger.error(
                    f"=== 手動削除が必要な添付ファイル (チケット {issue_id}) ==="
                )
                for failed in failed_attachments:
                    logger.error(
                        f"[MANUAL_DELETE_REQUIRED] チケット {failed['issue_id']} - 添付ファイル {failed['attachment_index']}/{failed['total_attachments']} - エラー: {failed['error']}"
                    )
                logger.error(f"=== 手動削除対象: {len(failed_attachments)}件 ===")
                return False
            else:
                logger.info(f"チケット {issue_id} の添付ファイル削除が完了しました")
                return True

        except Exception as e:
            logger.error(
                f"チケット {issue_id} の添付ファイル削除中にエラーが発生しました: {e}"
            )
            return False

    async def delete_attachments_from_issues(self, issue_ids: List[int]) -> dict:
        """
        複数のチケットの添付ファイルを削除

        Args:
            issue_ids: チケットIDのリスト

        Returns:
            削除結果の辞書 {issue_id: success}
        """
        results = {}
        all_failed_attachments = []

        logger.info(f"{len(issue_ids)} 件のチケットの添付ファイル削除を開始します")

        for i, issue_id in enumerate(issue_ids, 1):
            logger.info(f"チケット {i}/{len(issue_ids)} を処理中: {issue_id}")

            success = await self.delete_attachments_from_issue(issue_id)
            results[issue_id] = success

            # 最後のチケットでない場合は間隔を設定
            if i < len(issue_ids) and self.delete_interval > 0:
                logger.debug(f"チケット間隔待機: {self.delete_interval}秒")
                await asyncio.sleep(self.delete_interval)

        # 結果を集計
        success_count = sum(1 for success in results.values() if success)
        failed_count = len(issue_ids) - success_count

        logger.info(f"削除完了: {success_count}/{len(issue_ids)} 件のチケットで成功")

        # 失敗したチケットがある場合はサマリーを出力
        if failed_count > 0:
            failed_issue_ids = [
                issue_id for issue_id, success in results.items() if not success
            ]
            logger.error(f"=== 削除失敗チケット一覧 ===")
            for issue_id in failed_issue_ids:
                logger.error(f"[DELETE_FAILED] チケット {issue_id}")
            logger.error(f"=== 削除失敗: {failed_count}件のチケット ===")
            logger.error(
                f"手動削除が必要なチケット: {', '.join(map(str, failed_issue_ids))}"
            )

        return results

    async def close(self):
        """ブラウザを閉じる"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("ブラウザを閉じました")
        except Exception as e:
            logger.error(f"ブラウザのクローズ中にエラーが発生しました: {e}")

    async def __aenter__(self):
        """非同期コンテキストマネージャーのエントリーポイント"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーのエグジットポイント"""
        await self.close()
