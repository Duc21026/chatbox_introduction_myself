# Contract — Health API

**Feature**: `008-vercel-cloudflare-deploy`
**Endpoint**: `GET /api/health` (Vercel), alias `GET /health` khi chạy local
**Content-Type**: `application/json`

Điểm cuối rẻ, **không gọi Cloudflare**, dùng để làm nóng function, kiểm tra chỉ mục vector
và phát hiện quên build vector.

---

## Response `200`

```json
{
  "status": "ok",
  "vectors_loaded": true,
  "vector_count": 180,
  "model": "@cf/baai/bge-m3",
  "dim": 1024,
  "normalizer_version": "2",
  "source_hash_matches": true,
  "embedding_provider": "cloudflare",
  "provider_ready": true,
  "message": "Sẵn sàng"
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `status` | `ok` \| `degraded` | `degraded` nếu vector không dùng được hoặc thiếu cấu hình provider |
| `vectors_loaded` | boolean | Đã nạp `data/vectors.json` |
| `vector_count` | integer | Số entry |
| `model` | string | Model ghi trong chỉ mục |
| `dim` | integer | Số chiều vector |
| `normalizer_version` | string | Phiên bản chuẩn hoá |
| `source_hash_matches` | boolean | `source_kb_hash` khớp KB hiện tại |
| `embedding_provider` | `cloudflare` \| `ollama` \| `none` | Provider cấu hình |
| `provider_ready` | boolean | Đủ cấu hình (không kiểm tra mạng) |
| `message` | string | Thông điệp ngắn, không chứa bí mật |

---

## Trạng thái suy giảm

| Tình huống | `status` | Ghi chú |
|-----------|----------|---------|
| Không có `vectors.json` | `degraded` | `vectors_loaded=false`; chat dùng lexical/fuzzy |
| Hash lệch | `degraded` | `source_hash_matches=false`; **không** dùng vector cũ |
| Thiếu `CF_ACCOUNT_ID`/`CF_API_TOKEN` | `degraded` | `provider_ready=false`; chat dùng lexical/fuzzy |
| `CHATBOT_EMBEDDING_PROVIDER=none` | `degraded` | Chủ động tắt embedding |
| Mọi thứ khớp | `ok` | |

---

## Bất biến bảo mật

- Không trả `CF_ACCOUNT_ID`, `CF_API_TOKEN`, URL nội bộ, stack trace hoặc nội dung tệp.
- Không gọi Cloudflare, Ollama hoặc bất kỳ dịch vụ ngoài.
- Không ghi log bí mật; nếu có lỗi, chỉ log mã lỗi đã lọc.

---

## Kiểm thử

- Test không có tệp vector → `degraded`, `vectors_loaded=false`.
- Test vector hợp lệ → `ok`, `source_hash_matches=true`.
- Test sửa nguồn nhưng không build lại → `source_hash_matches=false`, `status=degraded`.
- Test thiếu env Cloudflare → `provider_ready=false`, không exception.
- Test xác nhận không có lời gọi mạng (mock `urllib.request.urlopen` phải không được gọi).
