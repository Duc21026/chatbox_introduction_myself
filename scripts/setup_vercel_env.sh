#!/usr/bin/env bash
# Add deployment environment variables to the linked Vercel project.
# Values are read from the root .env (gitignored) or the current shell.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if command -v vercel >/dev/null 2>&1; then
  VERCEL=(vercel)
else
  VERCEL=(npx --yes vercel)
fi

if ! "${VERCEL[@]}" whoami >/dev/null 2>&1; then
  echo "CLI đang chưa đăng nhập. Chạy trước: vercel login" >&2
  exit 1
fi

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if [ ! -d "$ROOT/.vercel" ]; then
  echo "Repo chưa được link với Vercel. Chạy: vercel link" >&2
  exit 1
fi

: "${CF_ACCOUNT_ID:?Thiếu CF_ACCOUNT_ID trong .env hoặc shell}"
: "${CF_API_TOKEN:?Thiếu CF_API_TOKEN trong .env hoặc shell}"
: "${CHATBOT_EMBEDDING_PROVIDER:=cloudflare}"
: "${CHATBOT_VECTORS_PATH:=data/vectors.json}"

VARS=(
  CF_ACCOUNT_ID
  CF_API_TOKEN
  CHATBOT_EMBEDDING_PROVIDER
  CHATBOT_VECTORS_PATH
  CHATBOT_KB_HIGH_THRESHOLD
  CHATBOT_SUGGEST_THRESHOLD
  CHATBOT_FUZZY_WEIGHT
)

for env_name in production preview; do
  for name in "${VARS[@]}"; do
    value="${!name:-}"
    if [ -z "$value" ]; then
      continue
    fi
    printf '%s' "$value" | "${VERCEL[@]}" env add "$name" "$env_name" --force --sensitive --yes >/dev/null
    echo "Đã đặt $name cho $env_name"
  done
done

echo "Xong. Kiểm tra bằng: vercel env ls"
echo "Sau đó deploy: vercel --prod"
