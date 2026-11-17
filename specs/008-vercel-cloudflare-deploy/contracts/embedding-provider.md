# Contract — Embedding Provider

**Feature**: `008-vercel-cloudflare-deploy`
**Module**: `backend/embedding_provider.py`
**Provider mặc định khi deploy**: Cloudflare Workers AI `@cf/baai/bge-m3`

---

## Interface nội bộ

```python
def embed_texts(texts: list[str]) -> list[list[float]] | None: ...
def embed_query(text: str) -> list[float] | None: ...
def provider_status() -> dict: ...
```

- Trả `None` khi provider lỗi, timeout, thiếu cấu hình hoặc hết hạn mức.
- Không raise exception ra ngoài đường trả lời.
- `provider_status()` chỉ trả trạng thái cấu hình, **không** gọi mạng.

---

## Cloudflare REST request

```http
POST https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/@cf/baai/bge-m3
Authorization: Bearer {CF_API_TOKEN}
Content-Type: application/json
```

```json
{
  "text": ["câu hỏi 1", "câu hỏi 2"]
}
```

- `text` là mảng chuỗi; batch mặc định 32, điều chỉnh sau spike nhưng ≤ 50.
- Câu hỏi đơn lẻ vẫn gửi mảng 1 phần tử.
- Timeout: 3 giây cho truy vấn, 30 giây cho build.
- Thử lại: tối đa 1 lần cho lỗi mạng/5xx; **không** thử lại khi 400/401/403/429.
- Tổng payload ≤ 10 MB.

---

## Cloudflare response (kỳ vọng)

Dạng chuẩn của Workers AI là bọc trong `result`:

```json
{
  "result": {
    "data": [[0.12, -0.03, 0.44]],
    "shape": [1, 1024]
  },
  "success": true,
  "errors": [],
  "messages": []
}
```

Bộ phân tích chấp nhận vector ở một trong các vị trí sau và kiểm tra tính hợp lệ:

1. `result.data` (mảng các mảng số)
2. `result.embeddings` (nếu Cloudflare đổi tên trường)
3. `result.response` khi dùng chế độ query/contexts

**Điều kiện hợp lệ**: `success == true`, không có `errors`, số vector = số text gửi lên,
mỗi vector có độ dài `dim` (dự kiến 1024), mọi giá trị là số hữu hạn. Nếu không → coi như
lỗi provider.

> Phase 1 của kế hoạch triển khai phải xác minh tên trường thực tế bằng một lời gọi thật;
> nếu khác, chỉ sửa parser, không đổi contract interface.

---

## Lỗi và fallback

| Tình huống | Hành vi |
|-----------|---------|
| Thiếu `CF_ACCOUNT_ID`/`CF_API_TOKEN` | `provider_ready=false`; `embed_*` trả `None`; log cảnh báo |
| HTTP 401/403 | Trả `None`; log mã lỗi (không log token); không thử lại |
| HTTP 429 / hết hạn mức | Trả `None`; log cảnh báo; không thử lại |
| HTTP 5xx / timeout / mạng lỗi | Thử lại 1 lần; vẫn lỗi → `None` |
| Phản hồi sai schema/độ dài | Trả `None`; log lỗi schema đã lọc |
| `CHATBOT_EMBEDDING_PROVIDER=none` | Luôn `None`; chỉ dùng lexical/fuzzy |

Khi `embed_query` trả `None`, `kb_engine.evaluate` trả `embeddings_ready=False`; `assistant`
dùng `build_fuzzy_suggestions` và các nhánh suggest/clarify hiện có.

---

## Adapter Ollama (local/Docker)

- Chỉ import `langchain_ollama` **bên trong** hàm khi provider=`ollama`.
- Dùng cùng interface; `embed_texts` gọi `embed_documents`, `embed_query` gọi `embed_query`.
- Không có mặt trong `requirements.txt` deploy.

---

## Kiểm thử

- Mock HTTP 200 với `result.data` hợp lệ → trả đúng số vector/độ dài.
- Mock 429/401/500/timeout → trả `None`, không raise.
- Mock response thiếu `result`/sai độ dài → trả `None`.
- `CHATBOT_EMBEDDING_PROVIDER=none` → `None`, không gọi mạng.
- Test import `api.chat` không kéo `langchain_ollama`/`faiss`.
