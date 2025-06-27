"""
Redmine APIクライアント
requestsライブラリを使用してRedmine REST APIからチケットと添付ファイルを取得するクラス
"""

import json
import logging
import os
import re
import time
import urllib.parse
from collections.abc import Sequence
from pathlib import Path
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def get_timeout_settings() -> tuple[int, int]:
    """
    環境変数からタイムアウト設定を取得

    Returns:
        (base_timeout, timeout_increment): 基本タイムアウト時間と増加時間のタプル
    """
    # 基本タイムアウト時間（秒）、デフォルト15秒
    base_timeout = int(os.getenv("REDMINE_BASE_TIMEOUT", "15"))

    # タイムアウト増加時間（秒）、デフォルト15秒
    timeout_increment = int(os.getenv("REDMINE_TIMEOUT_INCREMENT", "15"))

    return base_timeout, timeout_increment


def get_retry_settings() -> tuple[int, float]:
    """
    環境変数からリトライ設定を取得

    Returns:
        (retry_count, retry_interval): リトライ回数とリトライ間隔のタプル
    """
    # リトライ回数、デフォルト3回
    retry_count = int(os.getenv("REDMINE_RETRY_COUNT", "3"))

    # リトライ間隔（秒）、デフォルト5.0秒
    retry_interval = float(os.getenv("REDMINE_RETRY_INTERVAL", "5.0"))

    return retry_count, retry_interval


class RedmineAttachment:
    """Redmineの添付ファイルを表すクラス"""

    def __init__(
        self, attachment_data: Dict, verify_ssl: bool = True, auth=None, headers=None
    ):
        self.id = attachment_data.get("id")
        self.filename = attachment_data.get("filename", "")
        self.content_url = attachment_data.get("content_url", "")
        self.content_type = attachment_data.get("content_type", "")
        self.filesize = attachment_data.get("filesize", 0)
        self.description = attachment_data.get("description", "")
        self.author = attachment_data.get("author", {})
        self.created_on = attachment_data.get("created_on", "")
        self.verify_ssl = verify_ssl
        self.auth = auth
        self.headers = headers or {}

    def download(
        self,
        directory: str,
        filename: str = None,
        retry_count: int = 3,
        retry_interval: float = 5.0,
    ) -> bool:
        """
        添付ファイルをダウンロード

        Args:
            directory: ダウンロードディレクトリ
            filename: 保存するファイル名（Noneの場合は元のファイル名を使用）
            retry_count: リトライ回数
            retry_interval: リトライ間隔（秒）

        Returns:
            ダウンロード成功時はTrue
        """
        if not self.content_url:
            logger.error(f"添付ファイルのURLが取得できません: {self.filename}")
            return False

        # リトライ設定を取得
        retry_count, retry_interval = get_retry_settings()

        # タイムアウト設定を取得
        base_timeout, timeout_increment = get_timeout_settings()

        for attempt in range(retry_count + 1):  # 初回 + リトライ回数
            try:
                # リトライ回数に応じてタイムアウト時間を計算
                current_timeout = base_timeout + (attempt * timeout_increment)

                # ファイル名が指定されていない場合は元のファイル名を使用
                if filename is None:
                    filename = self.filename

                # ダウンロードパスを構築
                download_path = Path(directory) / filename

                # ファイルダウンロード用のヘッダーを準備
                download_headers = {}
                if self.headers:
                    # Content-Typeヘッダーを除外（ファイルダウンロードでは不要）
                    download_headers = {
                        k: v
                        for k, v in self.headers.items()
                        if k.lower() != "content-type"
                    }

                logger.debug(
                    f"添付ファイルダウンロード開始 ({attempt + 1}回目): {self.filename}, タイムアウト: {current_timeout}秒"
                )

                # ファイルをダウンロード（認証情報付き、タイムアウト設定付き）
                response = requests.get(
                    self.content_url,
                    stream=True,
                    verify=self.verify_ssl,
                    auth=self.auth,
                    headers=download_headers,
                    timeout=current_timeout,
                )
                response.raise_for_status()

                with open(download_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                if attempt > 0:
                    logger.info(
                        f"添付ファイルのリトライ成功 ({attempt + 1}回目): {download_path}"
                    )
                else:
                    logger.debug(f"添付ファイルをダウンロードしました: {download_path}")
                return True

            except requests.exceptions.Timeout as e:
                if attempt < retry_count:
                    logger.warning(
                        f"添付ファイルのダウンロードがタイムアウトしました ({attempt + 1}/{retry_count + 1}回目): {self.filename}, タイムアウト: {current_timeout}秒"
                    )
                    logger.info(f"  {retry_interval}秒後にリトライします...")
                    time.sleep(retry_interval)
                else:
                    logger.error(
                        f"添付ファイルのダウンロードが最終的にタイムアウトしました: {self.filename}, 最終タイムアウト: {current_timeout}秒"
                    )
                    return False
            except Exception as e:
                if attempt < retry_count:
                    logger.warning(
                        f"添付ファイルのダウンロードに失敗しました ({attempt + 1}/{retry_count + 1}回目): {self.filename}, エラー: {e}"
                    )
                    logger.info(f"  {retry_interval}秒後にリトライします...")
                    time.sleep(retry_interval)
                else:
                    logger.error(
                        f"添付ファイルのダウンロードに最終的に失敗しました: {self.filename}, エラー: {e}"
                    )
                    return False

        return False


class RedmineIssue:
    """Redmineのチケットを表すクラス"""

    def __init__(
        self, issue_data: Dict, verify_ssl: bool = True, auth=None, headers=None
    ):
        self.id = issue_data.get("id")
        self.subject = issue_data.get("subject", "")
        self.description = issue_data.get("description", "")
        self.status = issue_data.get("status", {})
        self.priority = issue_data.get("priority", {})
        self.author = issue_data.get("author", {})
        self.assigned_to = issue_data.get("assigned_to", {})
        self.created_on = issue_data.get("created_on", "")
        self.updated_on = issue_data.get("updated_on", "")
        self.verify_ssl = verify_ssl
        self.auth = auth
        self.headers = headers

        # 添付ファイルの初期化
        self._attachments = []
        attachments_data = issue_data.get("attachments", [])
        for attachment_data in attachments_data:
            self._attachments.append(
                RedmineAttachment(attachment_data, verify_ssl, auth, headers)
            )

    def get_attachments(self) -> List[RedmineAttachment]:
        return self._attachments

    def has_attachments(self) -> bool:
        return len(self.get_attachments()) > 0

    def _sanitize_filename(self, filename: str) -> str:
        """
        ファイル名を安全な形式に変換

        Args:
            filename: 元のファイル名

        Returns:
            安全なファイル名
        """
        # URLエンコードされたファイル名をデコード
        try:
            decoded_filename = urllib.parse.unquote(filename)
        except Exception as e:
            logger.warning(
                f"ファイル名のデコードに失敗しました: {filename}, エラー: {e}"
            )
            decoded_filename = filename

        # 危険な文字を置換
        # Windows/Unix両方で使用できない文字を除去
        dangerous_chars = r'[<>:"/\\|?*\x00-\x1f]'
        safe_filename = re.sub(dangerous_chars, "_", decoded_filename)

        # 先頭・末尾の空白とドットを除去
        safe_filename = safe_filename.strip(" .")

        # 空のファイル名の場合はデフォルト名を使用
        if not safe_filename:
            safe_filename = "unnamed_file"

        # ファイル名が変更された場合はログに記録
        if safe_filename != decoded_filename:
            logger.info(
                f"ファイル名を安全な形式に変換: '{decoded_filename}' -> '{safe_filename}'"
            )

        return safe_filename

    def download_attachments(
        self,
        download_dir: str,
        download_interval: float = 0.0,
        retry_count: int = 3,
        retry_interval: float = 5.0,
    ):
        """
        添付ファイルをダウンロード（ファイル名をデコードして保存）

        Args:
            download_dir: ダウンロードディレクトリ
            download_interval: ファイルダウンロード間の待機時間（秒）
            retry_count: リトライ回数
            retry_interval: リトライ間隔（秒）
        """
        for i, attachment in enumerate(self.get_attachments(), 1):
            try:
                # 元のファイル名を取得
                original_filename = attachment.filename

                # ファイル名をデコードして安全な形式に変換
                safe_filename = self._sanitize_filename(original_filename)

                # ダウンロードパスを構築
                download_path = Path(download_dir) / safe_filename

                # ファイルが既に存在する場合は連番を付与
                counter = 1
                while download_path.exists():
                    name, ext = os.path.splitext(safe_filename)
                    download_path = Path(download_dir) / f"{name}_{counter}{ext}"
                    counter += 1

                # ファイルをダウンロード
                logger.debug(
                    f"添付ファイルをダウンロード中 ({i}/{len(self.get_attachments())}): {original_filename} -> {download_path.name}"
                )

                if attachment.download(
                    str(download_path.parent),
                    download_path.name,
                    retry_count,
                    retry_interval,
                ):
                    logger.info(
                        f"添付ファイルをダウンロードしました ({i}/{len(self.get_attachments())}): {download_path.name}"
                    )
                else:
                    logger.error(
                        f"添付ファイルのダウンロードに失敗しました: {original_filename}"
                    )

                # ファイルダウンロード間隔を設定（最後のファイル以外）
                if download_interval > 0 and i < len(self.get_attachments()):
                    logger.debug(
                        f"  ファイルダウンロード間隔待機: {download_interval}秒"
                    )
                    time.sleep(download_interval)

            except Exception as e:
                logger.error(
                    f"添付ファイルのダウンロードに失敗しました: {attachment.filename}, エラー: {e}"
                )


class RedmineIssueList(Sequence):
    """Redmineのチケット一覧を表すクラス"""

    def __init__(self, issues: List[RedmineIssue]):
        self.issues = issues

    def __len__(self) -> int:
        return len(self.issues)

    def __getitem__(self, index: int) -> RedmineIssue:
        return self.issues[index]


class RedmineClient:
    """Redmine APIクライアント（requestsライブラリ使用）

    使用例:
        # APIキーでチケット取得、ユーザ名・パスワードでファイルダウンロード
        client = RedmineClient(
            base_url="https://your-redmine.com",
            api_key="your_api_key",           # チケット取得用
            username="your_username",         # ファイルダウンロード用
            password="your_password"          # ファイルダウンロード用
        )

        # チケットを取得
        issues = client.get_issues(limit=10)

        # 添付ファイルをダウンロード（Basic認証で実行）
        for issue in issues:
            if issue.has_attachments():
                issue.download_attachments("./downloads")
    """

    def __init__(
        self,
        base_url: str,
        api_key: str = None,
        username: str = None,
        password: str = None,
        verify_ssl: bool = True,
    ):
        """
        RedmineClientの初期化

        Args:
            base_url: RedmineのベースURL
            api_key: RedmineのAPIキー（チケット取得用）
            username: ユーザ名（ファイルダウンロード用）
            password: パスワード（ファイルダウンロード用）
            verify_ssl: SSL証明書の検証を行うかどうか（デフォルト: True）
        """
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.session = requests.Session()

        # SSL検証設定を適用
        if not verify_ssl:
            # urllib3の警告を無効化（SSL検証を無効にした場合）
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            logger.warning(
                "SSL証明書の検証を無効にしました（セキュリティ上の注意が必要です）"
            )

        # 認証情報の設定
        self.api_key = api_key
        self.username = username
        self.password = password

        # APIキー認証（チケット取得用）
        if api_key:
            self.session.headers.update(
                {"X-Redmine-API-Key": api_key, "Content-Type": "application/json"}
            )
            logger.info("APIキー認証でRedmineクライアントを初期化しました")

        # ユーザ名・パスワード認証（ファイルダウンロード用）
        if username and password:
            # ファイルダウンロード用の認証情報を保存
            self.download_auth = (username, password)
            logger.info(
                "ユーザ名・パスワード認証でファイルダウンロード機能を初期化しました"
            )
        else:
            self.download_auth = None
            logger.warning("ファイルダウンロード用の認証情報が設定されていません")

        # 最低限の認証情報チェック
        if not api_key and not (username and password):
            raise ValueError(
                "認証情報が不足しています。APIキーまたはユーザ名とパスワードを指定してください。"
            )

    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Redmine APIにリクエストを送信（リトライ機能付き）

        Args:
            endpoint: APIエンドポイント
            params: クエリパラメータ

        Returns:
            APIレスポンスのJSONデータ
        """
        url = f"{self.base_url}{endpoint}"

        # リトライ設定を取得
        retry_count, retry_interval = get_retry_settings()

        # タイムアウト設定を取得
        base_timeout, timeout_increment = get_timeout_settings()

        for attempt in range(retry_count + 1):  # 初回 + リトライ回数
            try:
                # リトライ回数に応じてタイムアウト時間を計算
                current_timeout = base_timeout + (attempt * timeout_increment)

                logger.debug(
                    f"APIリクエスト開始 ({attempt + 1}回目): {url}, タイムアウト: {current_timeout}秒"
                )

                response = self.session.get(
                    url, params=params, verify=self.verify_ssl, timeout=current_timeout
                )
                response.raise_for_status()

                # JSONレスポンスを解析
                data = response.json()
                logger.debug(f"APIリクエスト成功: {url}")
                return data

            except requests.exceptions.Timeout as e:
                if attempt < retry_count:
                    logger.warning(
                        f"APIリクエストがタイムアウトしました ({attempt + 1}/{retry_count + 1}回目): {url}, タイムアウト: {current_timeout}秒"
                    )
                    logger.info(f"  {retry_interval}秒後にリトライします...")
                    time.sleep(retry_interval)
                else:
                    logger.error(
                        f"APIリクエストが最終的にタイムアウトしました: {url}, 最終タイムアウト: {current_timeout}秒"
                    )
                    raise
            except requests.exceptions.RequestException as e:
                if attempt < retry_count:
                    logger.warning(
                        f"APIリクエストに失敗しました ({attempt + 1}/{retry_count + 1}回目): {url}, エラー: {e}"
                    )
                    logger.info(f"  {retry_interval}秒後にリトライします...")
                    time.sleep(retry_interval)
                else:
                    logger.error(
                        f"APIリクエストに最終的に失敗しました: {url}, エラー: {e}"
                    )
                    raise

    def get_issues(
        self, limit: int = 10, offset: int = 0, sort: str = "created_on:asc"
    ) -> RedmineIssueList:
        """
        チケット一覧を取得

        Args:
            limit: 取得件数
            offset: オフセット
            sort: ソート順

        Returns:
            チケット一覧
        """
        try:
            # APIパラメータを構築
            params = {
                "limit": limit,
                "offset": offset,
                "sort": sort,
                "include": "attachments",
                "status_id": "*",
            }

            # Redmine REST APIを呼び出し
            data = self._make_request("/issues.json", params)

            # レスポンスからチケット一覧を構築
            issues = []
            for issue_data in data.get("issues", []):
                issues.append(
                    RedmineIssue(
                        issue_data,
                        self.verify_ssl,
                        self.download_auth,  # ファイルダウンロード用の認証情報
                        self.session.headers,
                    )
                )

            logger.debug(
                f"チケット取得リクエスト完了: limit={limit}, offset={offset}, 取得件数={len(issues)}"
            )
            return RedmineIssueList(issues)

        except Exception as e:
            logger.error(f"チケット取得に失敗しました: {e}")
            # エラーが発生した場合は空のリストを返す
            return RedmineIssueList([])
