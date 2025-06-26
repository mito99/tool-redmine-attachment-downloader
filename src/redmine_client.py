"""
Redmine APIクライアント
python-redmineライブラリを使用してRedmineからチケットと添付ファイルを取得するクラス
"""

import logging
import os
import re
import urllib.parse
from collections.abc import Sequence
from pathlib import Path
from typing import Dict, List, Optional

from redminelib import Redmine
from redminelib.resources import Attachment, Issue

logger = logging.getLogger(__name__)


class RedmineIssue:
    def __init__(self, issue: Issue):
        self.issue = issue

    def get_attachments(self) -> List[Attachment]:
        return self.issue.attachments

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

    def download_attachments(self, download_dir: str):
        """
        添付ファイルをダウンロード（ファイル名をデコードして保存）

        Args:
            download_dir: ダウンロードディレクトリ
        """
        for attachment in self.get_attachments():
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
                    f"添付ファイルをダウンロード中: {original_filename} -> {download_path.name}"
                )
                attachment.download(
                    str(download_path.parent), filename=download_path.name
                )

                logger.info(f"添付ファイルをダウンロードしました: {download_path.name}")

            except Exception as e:
                logger.error(
                    f"添付ファイルのダウンロードに失敗しました: {attachment.filename}, エラー: {e}"
                )


class RedmineIssueList(Sequence):
    def __init__(self, issues: List[Issue]):
        # ResultSetを事前に評価してリストに変換
        try:
            # ResultSetをリストに変換して遅延評価を回避
            self.issues = list(issues)
            logger.debug(f"ResultSetをリストに変換しました: {len(self.issues)}件")
        except Exception as e:
            logger.error(f"ResultSetの変換に失敗しました: {e}")
            self.issues = []

    def __len__(self) -> int:
        return len(self.issues)

    def __getitem__(self, index: int) -> RedmineIssue:
        return RedmineIssue(self.issues[index])


class RedmineClient:
    """Redmine APIクライアント（python-redmineライブラリ使用）"""

    def __init__(
        self,
        base_url: str,
        api_key: str = None,
        username: str = None,
        password: str = None,
    ):
        """
        RedmineClientの初期化

        Args:
            base_url: RedmineのベースURL
            api_key: RedmineのAPIキー（オプション）
            username: ユーザ名（オプション）
            password: パスワード（オプション）
        """
        self.base_url = base_url

        # python-redmineクライアントの初期化
        if api_key:
            # APIキー認証
            self.redmine = Redmine(base_url, key=api_key)
            logger.info("APIキー認証でRedmineクライアントを初期化しました")
        elif username and password:
            # ユーザ名・パスワード認証
            self.redmine = Redmine(base_url, username=username, password=password)
            logger.info("ユーザ名・パスワード認証でRedmineクライアントを初期化しました")
        else:
            raise ValueError(
                "認証情報が不足しています。APIキーまたはユーザ名とパスワードを指定してください。"
            )

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
            # python-redmineライブラリを使用してチケットを取得
            issues = self.redmine.issue.filter(
                limit=limit,
                offset=offset,
                sort=sort,
                include=["attachments"],
                status_id="*",
            )
            logger.debug(f"チケット取得リクエスト完了: limit={limit}, offset={offset}")
            return RedmineIssueList(issues)
        except Exception as e:
            logger.error(f"チケット取得に失敗しました: {e}")
            # エラーが発生した場合は空のリストを返す
            return RedmineIssueList([])
