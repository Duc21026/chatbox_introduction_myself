# Quickstart — Triển khai và nghiệm thu

**Feature**: `008-vercel-cloudflare-deploy`
**Mục đích**: Hướng dẫn chạy/kiểm tra end-to-end, không phải tài liệu triển khai code chi tiết.
**Tham chiếu**: [spec.md](./spec.md), [plan.md](./plan.md), [contracts/](./contracts/), [data-model.md](./data-model.md)

---

## 0. Điều kiện tiên quyết

- Tài khoản GitHub, Vercel (Hobby), Cloudflare (free) — **không cần thẻ**.
- Python 3.12, Node 22, Git, Vercel CLI (`npm i -g vercel`).
- `CF_ACCOUNT_ID` và `CF_API_TOKEN` có quyền Workers AI.
- Đã đọc lại giới hạn miễn phí tại thời điểm làm (10.000 neurons/ngày; Vercel Hobby).

Kiểm tra nhanh:

```bash
python --version          # 3.12.x
node --version            # v22.x
vercel --version
```

---

## 1. Chuẩn bị máy local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest
```

Nếu cần chạy nhánh Docker/Ollama cũ, cài thêm `backend/requirements.txt` và chạy
`docker compose up`. **Không** cài các gói đó cho đường deploy Vercel.

Đặt biến môi trường (không commit):

```bash
export CF_ACCOUNT_ID="..."
export CF_API_TOKEN="..."
export CHATBOT_EMBEDDING_PROVIDER=cloudflare
export CHATBOT_SOURCE_PATH=data/chatbot.txt
export CHATBOT_VECTORS_PATH=data/vectors.json
```

Kiểm tra `.env` nằm trong `.gitignore` và không có token trong mã nguồn/frontend.

---

## 2. Kiểm tra dữ liệu nguồn

```bash
python scripts/check_chatbot.py data/chatbot.txt
```

**Kỳ vọng**: in tóm tắt số bản ghi/câu hỏi, exit code `0`, không có lỗi. Nếu có lỗi:
dừng, sửa `data/chatbot.txt` (hoặc courses/aliases), không build vector.

---

## 3. Build chỉ mục vector

```bash
python scripts/build_vectors.py
```

**Kỳ vọng**:
- Tạo `data/vectors.json` với `model=@cf/baai/bge-m3`, `dim=1024`,
  `normalizer_version=2`, `source_sha256`, `source_kb_hash`.
- `question_count` khớp số câu hỏi `qa` active.
- Lần đầu cần mạng; nếu Cloudflare lỗi, script dừng và không ghi tệp dở.

Kiểm tra nhanh:

```bash
python - <<'PY'
import json
p = json.load(open("data/vectors.json", encoding="utf-8"))
print(p["model"], p["dim"], p["question_count"], p["normalizer_version"])
print(p["source_sha256"][:12], p["source_kb_hash"][:12])
print(len(p["entries"]), len(p["entries"][0]["vector"]))
PY
```

---

## 4. Chạy local

API:

```bash
flask --app api.chat run --port 5000
```

Frontend (terminal khác):

```bash
VITE_API_BASE_URL=http://127.0.0.1:5000 npm --prefix frontend run dev
```

Mở `http://localhost:5173`, hỏi thử:

- "GPA của bạn là bao nhiêu?" → 8.51/10 (≈ 8.5), 3.63/4.0, 87 tín chỉ, 24 học phần.
- "điểm oop" → 6.9 (B, 4 tín chỉ).
- "mục tiêu" → ≥ 2 gợi ý + "Câu hỏi khác".
- "asdf" → menu chủ đề, không có "không biết".

Kiểm tra health:

```bash
curl -s http://127.0.0.1:5000/health | python -m json.tool
```

**Kỳ vọng**: `status=ok`, `vectors_loaded=true`, `source_hash_matches=true`,
`provider_ready=true`.

---

## 5. Kiểm thử tự động

```bash
pytest -q
npm --prefix frontend test -- --run
npm --prefix frontend run lint
npm --prefix frontend run build
```

**Kỳ vọng**: toàn bộ xanh; test fallback provider không gọi mạng thật; test import
`api.chat` không kéo `langchain`/`faiss`.

---

## 6. Deploy lên Vercel

1. Import repo vào Vercel. Repo dùng **Services mode** trong `vercel.json`:
   - `backend` (Flask, root `.`) phục vụ public dưới `/api/*`
   - `frontend` (Vite, root `frontend`) phục vụ public dưới `/`
   - Không cần chọn framework preset thủ công.
2. Thêm Environment Variables cho **Production** và **Preview**:
   - `CF_ACCOUNT_ID`, `CF_API_TOKEN` (secret)
   - `CHATBOT_EMBEDDING_PROVIDER=cloudflare`
   - `CHATBOT_VECTORS_PATH=data/vectors.json`
   - `HIGH`, `MID`, `FUZZY_W` theo kết quả tuning (hoặc tên biến `CHATBOT_KB_HIGH_THRESHOLD`,
     `CHATBOT_SUGGEST_THRESHOLD`, `CHATBOT_FUZZY_WEIGHT`)
3. Chạy `vercel dev` để kiểm tra cả hai service + routing trước khi deploy.
4. Deploy:

```bash
vercel --prod
```

**Kỳ vọng**: build backend service (Flask) và frontend service (Vite) độc lập; request
`/api/*` vào backend, còn lại vào frontend. Bundle backend không chứa `frontend/`,
`backend/tests`, `library`, PDF lớn.

**Bindings**: hiện không cần binding vì frontend gọi backend từ trình duyệt qua public path
`/api/*`; backend không gọi service nội bộ nào khác.

Kiểm tra:

```bash
curl -s https://<project>.vercel.app/api/health | python -m json.tool
curl -s https://<project>.vercel.app/api/chat \
  -X POST -H 'Content-Type: application/json' \
  -d '{"message":"GPA của bạn là bao nhiêu?"}'
```

---

## 7. Tạo rule rate limit (Vercel WAF)

Dashboard → Project → **Firewall** → **Configure** → **+ New Rule**:

- Tên: `rate-limit-chat`
- Điều kiện: `Path equals /api/chat` **và** `Method equals POST`
- Hành động: **Rate Limit**
- Giới hạn: **30 requests / 60 seconds**, key **IP**
- Phản hồi: **429 Too Many Requests**
- Bấm **Review Changes** → **Publish** (rule nháp không có hiệu lực)

Kiểm tra (cẩn thận, đừng spam quá lâu):

```bash
for i in $(seq 1 35); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://<project>.vercel.app/api/chat \
    -H 'Content-Type: application/json' \
    -d '{"message":"test"}'
done | sort | uniq -c
```

**Kỳ vọng**: xuất hiện `429` sau khi vượt ngưỡng; các IP khác không bị ảnh hưởng; hạn mức
Cloudflare không bị đốt hết.

---

## 8. Nghiệm thu T1–T8

| # | Kiểm tra | Cách làm | Đạt khi |
|---|----------|----------|---------|
| T1 | Dữ liệu mẫu | Hỏi GPA, OOP, tốt nghiệp | 8.51/10 (≈ 8.5), 3.63/4.0, 87 tín chỉ, 24 học phần, OOP 6.9, tốt nghiệp 8/2028 |
| T2 | Câu mơ hồ | Hỏi "mục tiêu" | ≥ 2 gợi ý + nút "Câu hỏi khác" |
| T3 | Ngoài chủ đề | Hỏi "asdf" | Menu chủ đề; **không** có "không biết" |
| T4 | Provider lỗi | Tạm dùng token sai hoặc tắt mạng ở local | Vẫn ra gợi ý/clarify; **không** 500 |
| T5 | Đầu vào xấu | Gửi `""`, toàn khoảng trắng, chuỗi > 200 ký tự | 400/422 kèm thông báo rõ |
| T6 | Tốc độ | Đo 10 câu khi function ấm; 1 câu sau khi nghỉ lâu | p95 < 1,5 giây; lần đầu < 5 giây |
| T7 | Spam | 35 request/phút từ một IP | Bị 429; hạn mức Cloudflare còn |
| T8 | Bảo mật | Tìm token trong bundle frontend, repo, log, response | Không thấy token/bí mật |

Ghi kết quả vào PR/release notes. Chỉ promote production khi **tất cả** đạt.

---

## 9. Quy trình cập nhật dữ liệu (vận hành)

```bash
# 1. Sửa data/chatbot.txt (hoặc data/sources/courses.csv, aliases.txt)
# 2. Kiểm tra
python scripts/check_chatbot.py data/chatbot.txt

# 3. Build lại vector (BẮT BUỘC mỗi khi sửa câu hỏi)
python scripts/build_vectors.py

# 4. Commit + push (Vercel tự deploy)
git add data/chatbot.txt data/vectors.json
git commit -m "data: update chatbot source"
git push

# 5. Hỏi thử T1–T3 trên URL công khai
```

Nếu quên bước 3: `health` báo `source_hash_matches=false`, `status=degraded`; chat dùng
lexical/fuzzy thay vì vector cũ. **Không** deploy khi `check_chatbot.py` còn lỗi.

---

## 10. Hiệu chỉnh ngưỡng

```bash
python scripts/tune_weights.py --questions backend/evaluation/questions.json
```

**Kỳ vọng**: in bộ `FUZZY_W`, `HIGH`, `MID` đề xuất kèm tỷ lệ câu đúng/ngoài chủ đề. Cập
nhật biến môi trường Vercel; **không** dùng lại 0.78/0.55 của Ollama.

---

## 11. Quay lui

- **Một bản deploy lỗi**: Vercel → Deployments → chọn bản trước → **Promote to Production**
  (hoặc `vercel rollback`).
- **Cloudflare sự cố kéo dài**: đặt `CHATBOT_EMBEDDING_PROVIDER=none` trong Vercel env để
  chỉ dùng lexical/fuzzy, không cần deploy code.
- **Quay lại toàn bộ Ollama**: checkout nhánh `ollama-version` và deploy theo
  `docker compose`; nhánh này MUST được giữ.

---

## 12. Xử lý sự cố nhanh

| Hiện tượng | Nguyên nhân thường gặp | Xử lý |
|-----------|------------------------|-------|
| `health` degraded, `source_hash_matches=false` | Chưa build lại vector | Chạy `build_vectors.py`, commit `data/vectors.json` |
| `provider_ready=false` | Thiếu/sai env Cloudflare | Kiểm tra `CF_ACCOUNT_ID`, `CF_API_TOKEN`; redeploy |
| 401/403 từ Cloudflare | Token sai/hết quyền | Tạo token mới, cập nhật env, thu hồi token cũ |
| 429 quá sớm | Rule WAF quá chặt hoặc spam | Kiểm tra rule 30/60s/IP; không hạ thấp hơn nhu cầu thật |
| Cold start > 5 giây | Function chưa được làm ấm | Gọi `/api/health` khi tải trang; chấp nhận lần đầu chậm |
| Build lỗi vượt 500 MB | Bundle kéo tests/docs/PDF | Kiểm tra `includeFiles`/`excludeFiles`, requirements deploy |
| Câu trả lời vẫn dùng dữ liệu cũ | Chưa commit/deploy `data/vectors.json` | Commit và push; kiểm tra deployment mới nhất |

---

## 13. Kết quả kiểm chứng cục bộ (2026-11-17)

- `pytest backend/tests -q`: **230 passed** (bao gồm các test cần Ollama đang chạy).
- `npm --prefix frontend test -- --run`: **50 passed**.
- `npm --prefix frontend run lint`: pass.
- `npm --prefix frontend run build`: pass (Vite build ~779 ms).
- `python scripts/check_chatbot.py data/chatbot.txt`: 0 lỗi, 0 cảnh báo.
- `python scripts/check_secrets.py`: không phát hiện bí mật.
- Smoke local với vector Ollama `bge-m3` (`/tmp/vectors-ollama.json`): T1–T3 **PASS**;
  `/health` trả `ok`.
- Hash-mismatch, provider 401/403/429/5xx/timeout, `provider=none`, và import guard
  `api.chat` đã được kiểm thử tự động.

**Chưa chạy được trong môi trường này (cần tài khoản Cloudflare/Vercel):**

- Build `data/vectors.json` bằng Cloudflare `@cf/baai/bge-m3` (T044).
- `vercel build`/kiểm tra bundle thật (T036, T065).
- Hiệu chỉnh ngưỡng trên vector Cloudflare (T059).
- Nghiệm thu T1–T8, rollback và đo tốc độ/bundle trên preview (T054, T066–T068).
