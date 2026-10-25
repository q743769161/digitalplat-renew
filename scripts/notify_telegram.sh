#!/usr/bin/env bash
# Telegram notification for DigitalPlat Auto Renew.
# Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, RENEW_OUTCOME, COMMIT_OUTCOME,
#      RUN_NUMBER, EVENT_NAME, RUN_URL. State file: state/domains-state.json
# Exits 0 even if Telegram delivery fails, so a notification failure never
# turns a successful renewal run into a failed job. It only prints a warning
# and the HTTP code (never the token).
if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
  echo "Telegram secrets not set, skipping notification."
  exit 0
fi
SUMMARY=$(python3 -c "import json; d=json.load(open('state/domains-state.json')); print('\n'.join('• ' + k + '：' + str(v.get('last_action', '-')) + ' / 到期 ' + str(v.get('expiry_date', '-')) + ' / 剩 ' + str(v.get('days_remaining', '-')) + ' 天' for k, v in d.get('domains', {}).items()))" 2>/dev/null || echo "状态文件未生成或无法读取")
MSG="<b>DigitalPlat 自动续期</b>
运行：#${RUN_NUMBER}（${EVENT_NAME}）
续期步骤：${RENEW_OUTCOME}，提交状态步骤：${COMMIT_OUTCOME}
${SUMMARY}
详情：${RUN_URL}"
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" -d chat_id="$TELEGRAM_CHAT_ID" -d parse_mode="HTML" --data-urlencode "text=$MSG")
echo "Telegram notify HTTP $CODE"
if [ "$CODE" != "200" ]; then
  echo "::warning::Telegram notification failed with HTTP $CODE"
fi
exit 0
