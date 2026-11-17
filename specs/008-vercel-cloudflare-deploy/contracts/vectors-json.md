# Contract — `vectors.json`

**Feature**: `008-vercel-cloudflare-deploy`
**Producer**: `scripts/build_vectors.py`
**Consumer**: `backend/vector_store.py`, `backend/kb_engine.py`, `backend/health.py`
**Vị trí**: `data/vectors.json` (commit cùng repo, không phải bí mật)

---

## Schema

```json
{
  "schema_version": 1,
  "model": "@cf/baai/bge-m3",
  "dim": 1024,
  "normalizer_version": "2",
  "source_sha256": "64-hex",
  "source_kb_hash": "64-hex",
  "question_count": 180,
  "built_at": "2026-11-17T07:00:00Z",
  "entries": [
    {
      "id": "gpa#0",
      "item_id": "gpa",
      "source_type": "qa",
      "topic": "Học tập & Điểm số",
      "question": "GPA của bạn là bao nhiêu?",
      "norm": "gpa cua ban la bao nhieu",
      "vector": [0.01234, -0.05678]
    }
  ]
}
```

| Field | Type | Ràng buộc |
|-------|------|-----------|
| `schema_version` | integer | `1` |
| `model` | string | Khớp `CHATBOT_EMBEDDING_MODEL` / provider |
| `dim` | integer | `len(vector)` của mọi entry; dự kiến 1024 |
| `normalizer_version` | string | Khớp `NORMALIZER_VERSION` lúc chạy |
| `source_sha256` | 64 hex | SHA-256 nội dung `data/chatbot.txt` |
| `source_kb_hash` | 64 hex | Hash KB dẫn xuất (`DerivedSource.kb_hash`) |
| `question_count` | integer | `len(entries)` |
| `built_at` | ISO-8601 UTC | Thời điểm build |
| `entries[].id` | string | Duy nhất |
| `entries[].item_id` | string | Tồn tại trong nguồn `qa` active |
| `entries[].source_type` | `"qa"` | Phạm vi feature này |
| `entries[].question` | string | Câu hỏi gốc |
| `entries[].norm` | string | `normalize_query(question)` |
| `entries[].vector` | number[] | Độ dài `dim`, hữu hạn, làm tròn 5 chữ số |

---

## Quy tắc build

1. Chạy `scripts/check_chatbot.py`; 0 lỗi mới tiếp tục.
2. Đọc nguồn qua `source_store`; chỉ lấy `kind=qa`, `status=active`.
3. Chuẩn hoá câu hỏi bằng **đúng** `normalize_query` dùng lúc trả lời.
4. Gọi Cloudflare theo lô; nếu bất kỳ lô nào lỗi → **không ghi** tệp, giữ bản cũ.
5. Ghi tệp tạm cùng thư mục rồi `os.replace` để thay thế nguyên tử.
6. Làm tròn vector 5 chữ số; kiểm tra lại `len(entries) == question_count`.
7. In tóm tắt: số entry, model, dim, hash, thời gian.

---

## Quy tắc sử dụng lúc chạy

Chỉ nạp chỉ mục khi **tất cả** điều kiện sau đúng:

- `schema_version == 1`
- `model` khớp cấu hình
- `dim` khớp độ dài vector
- `normalizer_version` khớp `NORMALIZER_VERSION`
- `source_kb_hash` khớp KB hiện tại
- Mọi entry có `item_id` tồn tại trong KB hiện tại

Nếu sai bất kỳ điều kiện:

- Không dùng vector (tránh ghép câu hỏi mới với vector cũ).
- Log cảnh báo nêu rõ lý do (không log nội dung nhạy cảm).
- `health` trả `vectors_loaded=false` hoặc `source_hash_matches=false`,
  `status=degraded`.
- Chat chạy lexical/fuzzy.

---

## Kiểm thử

- Build từ nguồn mẫu → schema hợp lệ, số entry khớp.
- Sửa nguồn không build lại → loader từ chối, health `degraded`.
- Đổi `model`/`dim`/`normalizer_version` → loader từ chối.
- Vector có `NaN`/sai độ dài → loader từ chối.
- Build lỗi giữa lô → tệp cũ không bị thay đổi.
- `source_sha256`/`source_kb_hash` khớp sau khi build.
