# Contract: Document Index schema

**Feature**: `006-tiered-suggest-ingest` | **Version**: 1

Chỉ mục tài liệu là **dữ liệu phái sinh** trong `CHATBOT_DOC_INDEX_DIR` (mặc định `backend/doc_index/`). Ba tệp luôn được ghi/đọc như một bộ; không sửa tay khi server đang chạy.

```text
backend/doc_index/
├── manifest.json     # phiên bản schema + thống kê
├── files.json        # trạng thái từng tệp
├── chunks.json       # metadata từng đoạn
└── vectors.npz       # vector theo chunk_id
```

Định dạng: JSON UTF-8 (NFC, không BOM), indent 2; NPZ nén (numpy). Ghi atomic: tạo tệp tạm cùng thư mục, `fsync`, rồi `os.replace` từng tệp theo thứ tự `vectors.npz` → `chunks.json` → `files.json` → `manifest.json`. Nếu tiến trình dừng giữa chừng, lần khởi động sau phát hiện lệch phiên bản/kích thước và dựng lại từ `chunks.json` + `vectors.npz`; nếu vẫn lệch, đánh dấu chỉ mục hỏng và yêu cầu `ingest` lại (không tự xoá dữ liệu).

---

## 1. `manifest.json`

```json
{
  "schema_version": 1,
  "created_at": "2026-11-12T09:00:00Z",
  "updated_at": "2026-11-12T09:00:04Z",
  "embedding_model": "bge-m3",
  "normalizer_version": "1",
  "chunk_size": 500,
  "chunk_overlap": 50,
  "file_count": 3,
  "chunk_count": 46,
  "vector_dim": 1024
}
```

| Field | Bắt buộc | Ràng buộc |
|-------|----------|-----------|
| `schema_version` | Có | Hiện tại `1`; lệch → từ chối nạp, yêu cầu ingest lại |
| `created_at` / `updated_at` | Có | ISO-8601 UTC |
| `embedding_model` | Có | Phải khớp `CHATBOT_EMBEDDING_MODEL`; lệch → yêu cầu `ingest --full` |
| `normalizer_version` | Có | Phải khớp `text_normalization.NORMALIZER_VERSION` |
| `chunk_size` / `chunk_overlap` | Có | Phải khớp cấu hình hiện tại |
| `file_count` / `chunk_count` | Có | Dùng kiểm tra tính toàn vẹn |
| `vector_dim` | Có | Chiều vector; kiểm tra với NPZ |

**Bất biến**: `embedding_model`, `normalizer_version`, `chunk_size`, `chunk_overlap` thay đổi → toàn bộ chỉ mục phải được embed lại. Khi đó `ingest` bỏ qua cache chunk và tính lại vector.

---

## 2. `files.json`

Mảng hoặc object theo `file`; chọn **object** để tra cứu O(1):

```json
{
  "CV.pdf": {
    "file": "CV.pdf",
    "type": "pdf",
    "file_hash": "a3f5...",
    "size_bytes": 183402,
    "status": "indexed",
    "chunk_ids": ["cv_pdf_p1_c0_ab12", "cv_pdf_p2_c1_cd34"],
    "ingested_at": "2026-11-12T09:00:03Z",
    "error": null,
    "mtime_ns": 1762938003000000000
  }
}
```

| Field | Kiểu | Bắt buộc | Ràng buộc |
|-------|------|----------|-----------|
| `file` | string | Có | Tên tệp đơn, không chứa `/`, `\`, `..`, `:` |
| `type` | enum | Có | `pdf` \| `docx` \| `xlsx` \| `csv` \| `txt` \| `md` \| `doc` |
| `file_hash` | string | Có | `sha256(bytes)` hex 64 ký tự |
| `size_bytes` | integer | Có | `0 < size ≤ CHATBOT_DOC_MAX_BYTES` |
| `status` | enum | Có | `indexed` \| `skipped` \| `failed` \| `removed` |
| `chunk_ids` | string[] | Có | Mọi id phải có trong `chunks.json`; rỗng nếu `failed` |
| `ingested_at` | string | Có | ISO-8601 UTC |
| `error` | string \| null | Có | Chỉ khác null khi `failed` |
| `mtime_ns` | integer | Có | Chẩn đoán; không dùng để quyết định thay đổi (dùng hash) |

**Bất biến**:
- Tệp `skipped` giữ nguyên bản ghi cũ (không ghi đè `ingested_at`).
- Tệp `failed` giữ bản ghi thành công trước đó nếu có; chỉ thêm `error` vào log, không thay `chunk_ids`.
- Không có `chunk_id` trùng giữa hai tệp.

---

## 3. `chunks.json`

Object theo `chunk_id`:

```json
{
  "cv_pdf_p2_c1_cd34": {
    "chunk_id": "cv_pdf_p2_c1_cd34",
    "file": "CV.pdf",
    "type": "pdf",
    "page": 2,
    "sheet": null,
    "row_start": null,
    "row_end": null,
    "heading": "Kinh nghiệm",
    "text": "2022–nay: Backend developer tại Công ty A...",
    "embed_text": "[CV.pdf > Kinh nghiệm > trang 2] 2022–nay: Backend developer tại Công ty A...",
    "content_hash": "9f2a1b...",
    "char_count": 412
  }
}
```

| Field | Kiểu | Bắt buộc | Ràng buộc |
|-------|------|----------|-----------|
| `chunk_id` | string | Có | Duy nhất; `sha1(file + "|" + vị trí + "|" + content_hash)` (hex, 40 ký tự) |
| `file` | string | Có | Khoá trong `files.json` |
| `type` | enum | Có | Khớp `files[file].type` |
| `page` | int \| null | Có | 1-based; chỉ PDF |
| `sheet` | string \| null | Có | Chỉ XLSX/CSV |
| `row_start` / `row_end` | int \| null | Có | 1-based, tính header; chỉ bảng |
| `heading` | string \| null | Có | Heading gần nhất; có thể null |
| `text` | string | Có | Không rỗng; **không** chứa tiền tố ngữ cảnh |
| `embed_text` | string | Có | `normalize_text(text, lowercase=False)` + tiền tố `[file > heading > vị trí]` |
| `content_hash` | string | Có | `sha256(embed_text)` hex 64 ký tự |
| `char_count` | int | Có | `len(text)` |

**Bất biến**:
- `text` và `embed_text` không rỗng.
- `embed_text` bắt đầu bằng tiền tố ngữ cảnh.
- Vị trí (`page`/`sheet`/`row_start`/`row_end`/`heading`) phản ánh đúng nguồn để trích dẫn.
- `content_hash` không phụ thuộc `chunk_id`; dùng để tái dùng vector khi cùng nội dung ở vị trí mới.

---

## 4. `vectors.npz`

```python
np.savez_compressed(
    path,
    chunk_ids=np.array(list_of_chunk_ids, dtype=object),  # unicode
    vectors=matrix,                                       # float32, shape (N, D)
)
```

| Array | Kiểu | Ràng buộc |
|-------|------|-----------|
| `chunk_ids` | object/unicode array, 1-D | Cùng thứ tự với `vectors`; mỗi id có trong `chunks.json` |
| `vectors` | float32, 2-D `(N, D)` | Đã chuẩn hoá L2; `N = len(chunk_ids)`; `D` khớp `manifest.vector_dim` |

**Bất biến**:
- Không có vector mồ côi (id không tồn tại trong `chunks.json`).
- Không có chunk thiếu vector.
- Vector được tạo bằng cùng `embedding_model` ghi trong manifest.

---

## 5. FAISS runtime (không lưu đĩa)

- `IndexFlatIP(D)` + `IndexIDMap2` để tìm cosine trên vector chuẩn hoá.
- Ánh xạ `faiss_id (int64) ↔ chunk_id` giữ trong bộ nhớ, dựng từ thứ tự `chunk_ids`.
- Dựng lại toàn bộ index sau mỗi thao tác ingest/remove; với ≤ 10 000 vector, chi phí build < 100 ms.
- Tìm kiếm: `scores, ids = index.search(query_vec, k)`; lọc `score < CHATBOT_DOC_THRESHOLD`.

**Không lưu `index.faiss`**: tránh lệch metadata và tránh phụ thuộc phiên bản FAISS khi khôi phục.

---

## 6. Quy tắc chunk id và tái dùng

```text
content_hash = sha256(embed_text)
chunk_id     = sha1(f"{file}|{page}|{sheet}|{row_start}|{row_end}|{heading}|{content_hash}")
```

- Khi tệp đổi: tính toàn bộ chunk mới + `content_hash`.
- Tập `content_hash` cũ của tệp được giữ trong bộ nhớ trong lúc ingest; hash trùng → tái dùng vector cũ (kể cả `chunk_id` đổi do vị trí đổi).
- Hash mới → embed.
- Hash không còn → xoá khỏi chỉ mục.
- Khi đổi `embedding_model`/`normalizer_version`/`chunk_size`/`chunk_overlap`: bỏ qua tái dùng, embed lại toàn bộ.

---

## 7. Kiểm tra toàn vẹn khi khởi động

1. Nếu thiếu bất kỳ tệp nào → chỉ mục rỗng, log info, không lỗi server.
2. `schema_version` lệch → từ chối nạp; `assistant` hạ cấp sang `clarify` (không có tài liệu), log lỗi.
3. `manifest` lệch `embedding_model`/`normalizer_version`/`chunk_size`/`chunk_overlap` → từ chối nạp; yêu cầu `ingest --full`.
4. `file_count`/`chunk_count` không khớp → dựng lại từ JSON; nếu vẫn lỗi → đánh dấu hỏng, hạ cấp.
5. `vectors.npz` không đọc được hoặc `N`/`D` lệch → đánh dấu hỏng; không xoá dữ liệu.
6. Chunk mồ côi/thiếu vector → bỏ qua chunk đó, log warning; nếu quá 1% → đánh dấu hỏng.

---

## 8. Tương thích & rollback

- `doc_index/` là dữ liệu phái sinh; thêm vào `.gitignore`.
- Xoá `doc_index/` (hoặc đặt `CHATBOT_DOC_INDEX_DIR` mới) → chatbot trở về hành vi chỉ dùng KB/tài liệu cũ, không lỗi.
- `chatbot.txt` và các tệp trong `data/` không bị sửa bởi `ingest`/`remove`.
- Nếu đổi model embedding, chạy:

```bash
python backend/scripts/manage_docs.py ingest ./backend/data --full
```

(`--full` là flag bổ sung: bỏ qua cache vector và embed lại toàn bộ; mặc định không cần.)
