#!/usr/bin/env python3
"""
Playwrightブラウザインストールスクリプト
Playwrightで使用するブラウザをインストールするスクリプト
"""

import logging
import subprocess
import sys

# ログ設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def install_playwright_browsers():
    """Playwrightのブラウザをインストール"""
    try:
        logger.info("Playwrightのブラウザをインストール中...")

        # playwright install コマンドを実行
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            check=True,
        )

        logger.info("Playwrightのブラウザインストールが完了しました")
        logger.info("出力:")
        logger.info(result.stdout)

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Playwrightのブラウザインストールに失敗しました: {e}")
        logger.error(f"エラー出力: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"予期しないエラーが発生しました: {e}")
        return False


def main():
    """メイン処理"""
    logger.info("Playwrightブラウザインストールスクリプトを開始します")

    success = install_playwright_browsers()

    if success:
        logger.info("インストールが正常に完了しました")
        sys.exit(0)
    else:
        logger.error("インストールに失敗しました")
        sys.exit(1)


if __name__ == "__main__":
    main()
