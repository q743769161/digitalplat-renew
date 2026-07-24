#!/usr/bin/env python3

import html
import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote

import cloudscraper
import requests

API_BASE = "https://domain-api.digitalplat.org/api/v1"
PANEL_BASE = "https://dash.domain.digitalplat.org"

RENEWAL_WINDOW_DAYS = 120
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
TIMEOUT = 30


def get_env(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def create_scraper():
    return cloudscraper.create_scraper(
        browser={
            "browser": "chrome",
            "platform": "linux",
            "desktop": True,
        }
    )


def get_domains(api_key):
    scraper = create_scraper()

    response = scraper.get(
        f"{API_BASE}/domains",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        timeout=TIMEOUT,
    )

    response.raise_for_status()
    data = response.json()

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("data", "domains", "results"):
            if isinstance(data.get(key), list):
                return data[key]

    raise RuntimeError("Unknown domain API response format")


def get_domain_name(item):
    return str(
        item.get("name")
        or item.get("domain")
        or ""
    ).strip()


def get_expiry(item):
    for key in (
        "expiry_date",
        "expiration_date",
        "expires_at",
        "expiry",
        "expire",
    ):
        value = item.get(key)
        if value:
            return str(value)

    return ""


def parse_expiry(value):
    value = value.strip()

    if not value:
        return None

    if value.lower() in (
        "permanent",
        "never",
        "null",
    ):
        return None

    normalized = value.replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y-%m-%d %H:%M:%S",
        ]

        dt = None

        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                break
            except ValueError:
                pass

        if dt is None:
            raise ValueError(
                f"Unable to parse expiry: {value}"
            )

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def days_left(expiry):
    now = datetime.now(timezone.utc)

    return int(
        (expiry - now).total_seconds()
        // 86400
    )


def get_cookie(session, name):
    values = [
        cookie.value
        for cookie in session.cookies
        if cookie.name == name
    ]

    return values[-1] if values else ""

def get_webshare_proxy(proxy_list_url):
    response = requests.get(
        proxy_list_url,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    proxy_lines = [
        line.strip()
        for line in response.text.splitlines()
        if line.strip()
    ]

    if not proxy_lines:
        raise RuntimeError(
            "Webshare proxy list is empty"
        )

    raw_proxy = proxy_lines[0]

    parts = raw_proxy.split(":")

    if len(parts) < 4:
        raise RuntimeError(
            "Unexpected Webshare proxy format"
        )

    host = parts[0]
    port = parts[1]
    username = parts[2]
    password = ":".join(parts[3:])

    proxy_url = (
        f"http://"
        f"{quote(username, safe='')}:"
        f"{quote(password, safe='')}"
        f"@{host}:{port}"
    )

    return proxy_url

def create_dashboard_session(
    remember_token,
    proxy_list_url,
):
    scraper = create_scraper()

    proxy_url = get_webshare_proxy(
        proxy_list_url
    )

    scraper.proxies.update({
        "http": proxy_url,
        "https": proxy_url,
    })

    print(
        "Dashboard proxy: enabled"
    )

    scraper.cookies.set(
        "remember_token",
        remember_token,
        domain=".digitalplat.org",
        path="/",
    )

    headers = {
        "User-Agent":
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/125 Safari/537.36",
        "Accept":
            "application/json, text/plain, */*",
    }

    dashboard = scraper.get(
        f"{PANEL_BASE}/dashboard",
        headers=headers,
        timeout=TIMEOUT,
        allow_redirects=True,
    )

    print(
        "Dashboard check:"
        f" status={dashboard.status_code},"
        f" final_url={dashboard.url}"
    )

    has_session = bool(
        get_cookie(
            scraper,
            "panel_session",
        )
    )

    has_csrf = bool(
        get_cookie(
            scraper,
            "panel_csrf_token",
        )
    )

    print(
        "Dashboard cookies:"
        f" panel_session={'yes' if has_session else 'no'},"
        f" csrf={'yes' if has_csrf else 'no'}"
    )

    check = scraper.get(
        f"{PANEL_BASE}/_panel_api/api/me",
        headers=headers,
        timeout=TIMEOUT,
        allow_redirects=False,
    )

    print(
        "API /me check:"
        f" status={check.status_code}"
    )

    if check.status_code != 200:
        if check.status_code in (401, 302):
            raise RuntimeError(
                "Dashboard authentication failed "
                f"(HTTP {check.status_code}). "
                "remember_token may be invalid or expired."
            )

        if check.status_code == 403:
            raise RuntimeError(
                "Dashboard returned HTTP 403 "
                "while using Webshare proxy."
            )

        raise RuntimeError(
            "Dashboard authentication check failed "
            f"(HTTP {check.status_code})."
        )

    csrf = get_cookie(
        scraper,
        "panel_csrf_token",
    )

    if not csrf:
        raise RuntimeError(
            "Dashboard login succeeded but "
            "panel_csrf_token was not issued."
        )

    return scraper
    scraper = create_scraper()

    scraper.cookies.set(
        "remember_token",
        remember_token,
        domain=".digitalplat.org",
        path="/",
    )

    headers = {
        "User-Agent":
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/125 Safari/537.36",
        "Accept":
            "application/json, text/plain, */*",
    }

    dashboard = scraper.get(
        f"{PANEL_BASE}/dashboard",
        headers=headers,
        timeout=TIMEOUT,
        allow_redirects=True,
    )

    print(
        "Dashboard check:"
        f" status={dashboard.status_code},"
        f" final_url={dashboard.url}"
    )

    has_session = bool(
        get_cookie(
            scraper,
            "panel_session",
        )
    )

    has_csrf = bool(
        get_cookie(
            scraper,
            "panel_csrf_token",
        )
    )

    print(
        "Dashboard cookies:"
        f" panel_session={'yes' if has_session else 'no'},"
        f" csrf={'yes' if has_csrf else 'no'}"
    )

    check = scraper.get(
        f"{PANEL_BASE}/_panel_api/api/me",
        headers=headers,
        timeout=TIMEOUT,
        allow_redirects=False,
    )

    print(
        "API /me check:"
        f" status={check.status_code}"
    )

    if check.status_code != 200:
        if check.status_code in (401, 302):
            raise RuntimeError(
                "Dashboard authentication failed "
                f"(HTTP {check.status_code}). "
                "remember_token may be invalid or expired."
            )

        if check.status_code == 403:
            raise RuntimeError(
                "Dashboard returned HTTP 403. "
                "Possible Cloudflare or access restriction."
            )

        raise RuntimeError(
            "Dashboard authentication check failed "
            f"(HTTP {check.status_code})."
        )

    csrf = get_cookie(
        scraper,
        "panel_csrf_token",
    )

    if not csrf:
        raise RuntimeError(
            "Dashboard login succeeded but "
            "panel_csrf_token was not issued."
        )

    return scraper

def renew_domain(session, domain):
    csrf = get_cookie(
        session,
        "panel_csrf_token",
    )

    url = (
        f"{PANEL_BASE}"
        f"/_panel_api/api/domains/"
        f"{quote(domain, safe='.')}/renew"
    )

    response = session.post(
        url,
        headers={
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": PANEL_BASE,
            "Referer":
                f"{PANEL_BASE}/domains/{domain}",
            "X-Csrf-Token": csrf,
        },
        json={
            "renewal_type": "free",
            "years": 1,
        },
        timeout=TIMEOUT,
    )

    try:
        data = response.json()
    except Exception:
        data = {
            "raw": response.text[:300]
        }

    if 200 <= response.status_code < 300:
        return True, data

    message = ""

    if isinstance(data, dict):
        message = (
            data.get("error")
            or data.get("message")
            or data.get("detail")
            or ""
        )

    return (
        False,
        f"HTTP {response.status_code}: "
        f"{message or data}",
    )


def get_dashboard_domains(session):
    response = session.get(
        f"{PANEL_BASE}/_panel_api/api/domains",
        headers={
            "Accept": "application/json"
        },
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in (
            "data",
            "domains",
            "results",
        ):
            if isinstance(data.get(key), list):
                return data[key]

    raise RuntimeError(
        "Unknown dashboard domain response"
    )


def find_expiry(domains, target):
    for item in domains:
        if get_domain_name(item).lower() == target.lower():
            return get_expiry(item)

    return ""


def telegram(token, chat_id, lines):
    text = "\n".join(lines)

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={
            "chat_id": chat_id,
            "parse_mode": "HTML",
            "text": text[:4000],
        },
        timeout=TIMEOUT,
    )

    if not response.ok:
        try:
            error = response.json()
        except Exception:
            error = response.text[:500]

        raise RuntimeError(
            f"Telegram send failed: HTTP {response.status_code}: {error}"
        )


def main():
    api_key = get_env(
        "DIGITALPLAT_API_KEY"
    )

    remember_token = get_env(
        "DIGITALPLAT_REMEMBER_TOKEN"
    )

    telegram_token = get_env(
        "TELEGRAM_BOT_TOKEN"
    )

    telegram_chat = get_env(
        "TELEGRAM_CHAT_ID"
    )
    
    proxy_list_url = get_env(
        "WEBSHARE_PROXY_LIST_URL"
    )

    domains = get_domains(api_key)

    due = []

    for item in domains:
        domain = get_domain_name(item)
        expiry_raw = get_expiry(item)

        if not domain or not expiry_raw:
            continue

        try:
            expiry = parse_expiry(
                expiry_raw
            )
        except Exception as error:
            print(
                f"Skip {domain}: {error}"
            )
            continue

        if expiry is None:
            continue

        remaining = days_left(expiry)

        if (
            0
            <= remaining
            <= RENEWAL_WINDOW_DAYS
        ):
            due.append(
                (
                    domain,
                    expiry_raw,
                    remaining,
                )
            )

    lines = [
        "<b>DigitalPlat 域名检查</b>",
        f"📊 共检查 {len(domains)} 个域名",
    ]

    if DRY_RUN:
        lines.append(
            "🧪 DRY RUN：不会真正续期"
        )

        # DRY RUN 也验证 Dashboard 登录状态和 CSRF
        try:
            session = create_dashboard_session(
                remember_token,
                proxy_list_url,
            )

            dashboard_domains = get_dashboard_domains(
                session
            )

            lines.append(
                "✅ Dashboard 登录验证成功"
            )

            lines.append(
                f"✅ Dashboard 可读取 "
                f"{len(dashboard_domains)} 个域名"
            )

            lines.append(
                "✅ CSRF Token 获取成功"
            )

        except Exception as error:
            lines.append(
                "❌ Dashboard 登录验证失败"
            )

            lines.append(
                f"原因：{html.escape(str(error))}"
            )

            lines.append(
                "⚠️ 请检查 DIGITALPLAT_REMEMBER_TOKEN"
            )

            telegram(
                telegram_token,
                telegram_chat,
                lines,
            )

            raise

        if not due:
            lines.append(
                "✅ 当前没有进入 "
                "120 天续期窗口的域名"
            )

        else:
            lines.append(
                f"⚠️ 有 {len(due)} 个域名"
                "进入续期窗口"
            )

            for domain, expiry, remaining in due:
                lines.append(
                    f"• <code>{html.escape(domain)}</code>"
                    f" 剩余 {remaining} 天"
                    f" / 到期 {html.escape(expiry)}"
                )

        telegram(
            telegram_token,
            telegram_chat,
            lines,
        )

        return


    if not due:
        lines.append(
            "✅ 当前没有进入 "
            "120 天续期窗口的域名"
        )

        telegram(
            telegram_token,
            telegram_chat,
            lines,
        )

        return


        session = create_dashboard_session(
        remember_token,
        proxy_list_url,
    )

    success = 0
    failed = 0

    for domain, old_expiry, remaining in due:

        ok, result = renew_domain(
            session,
            domain,
        )

        if not ok:
            failed += 1

            lines.append(
                f"❌ <code>"
                f"{html.escape(domain)}"
                f"</code>\n"
                f"{html.escape(str(result))}\n"
                "⚠️ 不自动重试"
            )

            continue

        # 绝不重复 POST。
        # 只重新读取状态进行确认。

        time.sleep(3)

        dashboard_domains = (
            get_dashboard_domains(
                session
            )
        )

        new_expiry = find_expiry(
            dashboard_domains,
            domain,
        )

        verified = False

        try:
            old_dt = parse_expiry(
                old_expiry
            )

            new_dt = parse_expiry(
                new_expiry
            )

            if (
                old_dt
                and new_dt
                and new_dt > old_dt
            ):
                verified = True

        except Exception:
            pass

        if verified:
            success += 1

            lines.append(
                "✅ DigitalPlat 自动续期成功\n"
                f"🌐 <code>"
                f"{html.escape(domain)}"
                f"</code>\n"
                f"旧到期："
                f"{html.escape(old_expiry)}\n"
                f"新到期："
                f"{html.escape(new_expiry)}"
            )

        else:
            failed += 1

            lines.append(
                "⚠️ 续期请求已提交，"
                "但到期时间未确认变化\n"
                f"🌐 <code>"
                f"{html.escape(domain)}"
                f"</code>\n"
                "不会自动重复提交，"
                "请人工检查 Dashboard。"
            )

    lines.append(
        f"\n结果：✅ {success} "
        f"/ ⚠️ {failed}"
    )

    telegram(
        telegram_token,
        telegram_chat,
        lines,
    )

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
