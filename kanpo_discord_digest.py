#!/usr/bin/env python3
"""
官報 前日まとめ Discord自動配信スクリプト (kanpo_discord_digest.py)

内閣府 官報発行サイト (https://www.kanpo.go.jp/) から前営業日分の
全体目次を取得・整形し、Discord Webhook経由でリッチなEmbedメッセージとして配信します。
"""

import os
import re
import sys
import json
import urllib.request
import urllib.parse
from html.parser import HTMLParser

DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1539938881158385674/4Q2eroMuOzFhRLFn6ujxK-JSNqarPOVW3CX9bLRX99FEUICPnvB86Yf3FiiwuDfREG5W"
)

class KanpoIndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = []
        self.in_dt = False
        self.current_dt_text = []
        self.current_href = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "dt":
            self.in_dt = True
            self.current_dt_text = []
            self.current_href = None
        elif self.in_dt and tag == "a":
            href = attrs_dict.get("href", "")
            if "fullcontents.html" in href:
                self.current_href = href

    def handle_endtag(self, tag):
        if tag == "dt":
            self.in_dt = False
            text = "".join(self.current_dt_text).strip()
            # 「全体目次はこちら」などのノイズ文字を整形
            clean_date = re.sub(r'全体目次.*$', '', text).strip()
            if self.current_href:
                self.days.append((clean_date, self.current_href))

    def handle_data(self, data):
        if self.in_dt:
            self.current_dt_text.append(data)


class KanpoContentsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_main = False
        self.in_dt = False
        self.in_li = False
        self.current_book = ""
        self.current_text = []
        self.data = {}

    def handle_starttag(self, tag, attrs):
        if tag == "main":
            self.in_main = True
        if not self.in_main:
            return
        if tag == "dt":
            self.in_dt = True
            self.current_text = []
        elif tag == "li":
            self.in_li = True
            self.current_text = []

    def handle_endtag(self, tag):
        if tag == "main":
            self.in_main = False
        if not self.in_main:
            return
        if tag == "dt":
            self.in_dt = False
            title = re.sub(r'\s+', ' ', "".join(self.current_text)).strip()
            if title:
                self.current_book = title
                if self.current_book not in self.data:
                    self.data[self.current_book] = []
        elif tag == "li":
            self.in_li = False
            item_text = re.sub(r'\s+', ' ', "".join(self.current_text)).strip()
            # 末尾のページ番号を除去（例: "告示（総務四〇一） 1" -> "告示（総務四〇一）"）
            clean_item = re.sub(r'\s+\d+$', '', item_text)
            if clean_item and self.current_book:
                self.data[self.current_book].append(clean_item)

    def handle_data(self, data):
        if self.in_main and (self.in_dt or self.in_li):
            self.current_text.append(data)


def fetch_kanpo_days():
    url = "https://www.kanpo.go.jp/"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
    parser = KanpoIndexParser()
    parser.feed(html)
    return parser.days


def fetch_kanpo_contents(rel_url):
    full_url = urllib.parse.urljoin("https://www.kanpo.go.jp/", rel_url)
    req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
    parser = KanpoContentsParser()
    parser.feed(html)
    return full_url, parser.data


def categorize_items(items):
    """項目の性格（法令、人事、公示・公告など）に応じて分類・選定"""
    laws = []
    regulations = []
    announcements = []
    others = []

    for item in items:
        if "法" in item and ("改正" in item or "公布" in item or "法律" in item):
            laws.append(item)
        elif "政令" in item or "省令" in item or "府令" in item or "規則" in item:
            regulations.append(item)
        elif "告示" in item or "公示" in item or "公告" in item:
            announcements.append(item)
        else:
            others.append(item)

    return laws, regulations, announcements, others


def build_discord_embed(date_str, page_url, kanpo_data):
    fields = []

    for book_name, items in kanpo_data.items():
        if not items:
            continue

        lines = []
        # 政府調達の場合は件数と代表例
        if "政府調達" in book_name:
            for it in items[:5]:
                lines.append(f"• {it}")
            if len(items) > 5:
                lines.append(f"*(他 {len(items) - 5} 件)*")
        else:
            # 号外や本紙は重要度順（法律・省令改正 ＞ 告示・公示 ＞ その他）
            laws, regs, annos, others = categorize_items(items)
            picked = laws + regs + annos + others
            for it in picked[:6]:
                # 長すぎる文字列はトリミング
                short_it = it if len(it) <= 75 else it[:72] + "..."
                lines.append(f"• {short_it}")
            if len(items) > 6:
                lines.append(f"*(計 {len(items)} 項目)*")

        val_text = "\n".join(lines) if lines else "掲載事項なし"
        if len(val_text) > 1024:
            val_text = val_text[:1020] + "..."

        fields.append({
            "name": f"📌 {book_name}",
            "value": val_text,
            "inline": False
        })

    embed = {
        "title": f"📜 官報 前日まとめ（{date_str} 発行分）",
        "url": page_url,
        "description": "内閣府 官報発行サイトより、前営業日に公布・告示された重要事項をダイジェストでお届けします。",
        "color": 3447003,
        "fields": fields,
        "footer": {
            "text": "官報 毎朝ダイジェスト配信 • 内閣府公式準拠"
        }
    }
    return embed


def send_to_discord(embed):
    payload = {
        "username": "官報ダイジェスト Bot",
        "avatar_url": "https://www.kanpo.go.jp/images/head-logo.png",
        "embeds": [embed]
    }
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        return res.status


def main():
    days = fetch_kanpo_days()
    if not days:
        print("Error: No kanpo issue found.")
        sys.exit(1)

    # 毎朝実行される前提：
    # days[0] は当日（本日発行分）、days[1] が前営業日（前日発行分）となる。
    # 週末や早朝（8:30前）で当日分が未発行の場合は days[0] が直近発行分。
    target_idx = 1 if len(days) > 1 else 0
    date_str, rel_url = days[target_idx]

    print(f"Target issue: {date_str} ({rel_url})")
    full_url, kanpo_data = fetch_kanpo_contents(rel_url)
    embed = build_discord_embed(date_str, full_url, kanpo_data)

    status = send_to_discord(embed)
    print(f"Discord notification sent successfully! HTTP Status: {status}")


if __name__ == "__main__":
    main()
