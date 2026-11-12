# Contract: `manage_docs.py` CLI (ingest / list / remove + lệnh cũ)

**Feature**: `006-tiered-suggest-ingest` | **Version**: 2 | **Extends**: 005 `manage-docs-cli.md`

## 0. Nguyên tắc

- Các lệnh `add`, `replace`, `delete`, `validate`, `migrate`, `ask` giữ nguyên hợp đồng.
- Thêm `ingest` và `remove` cho chỉ mục tài liệu phái sinh.
- `delete` xoá **tệp nguồn** khỏi `data/` (hành vi 002). `remove` chỉ xoá **khỏi chỉ mục**, giữ tệp nguồn.
- Không lệnh nào cần LLM trả lời; `ingest` chỉ cần embedder (`bge-m3` qua Ollama) cho các đoạn mới/đổi.
- In kết quả người đọc mặc định; `--json` cho máy đọc ở các lệnh có hỗ trợ.
- Mọi thao tác ghi dùng file tạm + `os.replace` (atomic). Lỗi một tệp không làm hỏng chỉ mục hiện có.

---

## 1. `ingest`

```bash
python backend/scripts/manage_docs.py ingest PATH
  [--data-dir DIR]
  [--index-dir DIR]
  [--recursive]
  [--full]
  [--json]
```

`PATH` có thể là:

- Một thư mục → nạp mọi tệp được hỗ trợ trong thư mục (mặc định không đệ quy).
- Một tệp → nạp đúng tệp đó.
- Bỏ trống → dùng `CHATBOT_DATA_DIR` (mặc định `backend/data`).

| Option | Mặc định | Mô tả |
|--------|----------|-------|
| `--data-dir DIR` | `CHATBOT_DATA_DIR` | Thư mục gốc chứa tài liệu; dùng để tính đường dẫn tương đối |
| `--index-dir DIR` | `CHATBOT_DOC_INDEX_DIR` | Nơi ghi `files.json`, `chunks.json`, `vectors.npz` |
| `--recursive` | tắt | Quét đệ quy thư mục con |
| `--full` | tắt | Bỏ qua cache vector; embed lại toàn bộ (dùng khi đổi model/chuẩn hoá/chunk) |
| `--json` | tắt | In `IngestReport` JSON ra stdout |

**Định dạng hỗ trợ**: `.pdf`, `.docx`, `.xlsx`, `.csv`, `.txt`, `.md`, `.doc` (DOC cần LibreOffice).

**Hành vi**:

1. Kiểm tra `PATH` tồn tại; nếu không → exit `1`.
2. Với từng tệp:
   - Bỏ qua tệp không hỗ trợ (không tính lỗi).
   - `--full` → bỏ qua so hash tệp và cache vector, embed lại mọi đoạn.
   - Tệp > `CHATBOT_DOC_MAX_BYTES` → `failed` với lỗi kích thước.
   - Tính SHA-256; nếu trùng `file_hash` đã lưu → `skipped`, không đọc nội dung.
   - Trích block theo định dạng; không có văn bản → `failed` (`E_NO_TEXT`), không tạo chunk rỗng.
   - Chunk hoá 500/50 + tiền tố ngữ cảnh; tính `content_hash` từng đoạn.
   - So với chunk cũ của cùng tệp: hash trùng → tái dùng vector; mới/đổi → embed; mất → xoá.
   - Ghi atomic cả ba tệp chỉ mục; dựng lại FAISS trong RAM.
3. In báo cáo; exit code theo mục 5.

**In mặc định**:

```text
Nạp tài liệu từ /app/backend/data
  thêm:     CV.pdf (pdf, 12 đoạn)
  cập nhật: data.xlsx (xlsx, 34 đoạn, 6 đoạn mới, 28 đoạn tái dùng)
  bỏ qua:   research.pdf
  lỗi:      scan.pdf — không trích được văn bản (PDF scan cần OCR)

Tổng: 4 tệp | thêm 1 | cập nhật 1 | bỏ qua 1 | lỗi 1
Đoạn: +46 mới, 28 tái dùng, 0 xoá | Vector đã tính: 46
```

**JSON** (`--json`):

```json
{
  "started_at": "2026-11-12T09:00:00Z",
  "finished_at": "2026-11-12T09:00:04Z",
  "added": [{"file": "CV.pdf", "type": "pdf", "status": "added", "chunks": 12}],
  "updated": [{"file": "data.xlsx", "type": "xlsx", "status": "updated", "chunks": 34}],
  "skipped": [{"file": "research.pdf", "type": "pdf", "status": "skipped", "chunks": 8}],
  "failed": [{"file": "scan.pdf", "type": "pdf", "status": "failed", "chunks": 0, "error": "E_NO_TEXT: ..."}],
  "stats": {
    "files_total": 4,
    "chunks_added": 46,
    "chunks_reused": 28,
    "chunks_removed": 0,
    "embeddings_computed": 46
  }
}
```

**Bất biến**:

- `skipped` không làm thay đổi `files.json`/`chunks.json`/`vectors.npz`.
- `failed` không xoá dữ liệu cũ của tệp đó (nếu đã từng nạp thành công).
- Tệp đổi chỉ embed phần mới/đổi; `embeddings_computed = chunks_added + số đoạn đổi`.
- Chạy `ingest` lần hai trên thư mục không đổi: mọi tệp `skipped`, `embeddings_computed = 0`.

---

## 2. `list`

```bash
python backend/scripts/manage_docs.py list [--data-dir DIR] [--index-dir DIR] [--json]
```

**In mặc định** (mỗi dòng một tệp):

```text
CV.pdf	pdf	indexed	12
data.xlsx	xlsx	indexed	34
research.pdf	pdf	not-indexed	0
```

| Cột | Mô tả |
|-----|-------|
| 1 | Tên tệp |
| 2 | Định dạng |
| 3 | `indexed` \| `not-indexed` \| `failed` |
| 4 | Số đoạn trong chỉ mục |

**JSON**:

```json
[
  {"file": "CV.pdf", "type": "pdf", "status": "indexed", "chunks": 12},
  {"file": "research.pdf", "type": "pdf", "status": "not-indexed", "chunks": 0}
]
```

- Liệt kê cả tệp có trong `data/` nhưng chưa nạp (status `not-indexed`).
- Tệp đã nạp nhưng không còn trong `data/` vẫn hiện với status `indexed` (cảnh báo "nguồn không còn") để người vận hành biết cần `remove`.

---

## 3. `remove`

```bash
python backend/scripts/manage_docs.py remove SOURCE
  [--index-dir DIR]
  [--json]
```

| Tham số | Mô tả |
|---------|-------|
| `SOURCE` | Tên tệp đã nạp (ví dụ `cv.pdf`) |
| `--index-dir DIR` | Như `ingest` |
| `--json` | In kết quả JSON |

**Hành vi**:

- Xoá `DocumentFile` + toàn bộ `DocumentChunk` + vector tương ứng khỏi chỉ mục.
- Không xoá tệp trong `data/` (dùng `delete` nếu muốn xoá nguồn).
- Không tồn tại → in lỗi, exit `1`.
- Ghi atomic + dựng lại FAISS.

**Output**:

```text
Đã xoá CV.pdf khỏi chỉ mục (12 đoạn).
```

---

## 4. Lệnh cũ (giữ nguyên)

| Lệnh | Mục đích | Ghi chú |
|------|----------|---------|
| `add INPUT [--name NAME]` | Thêm/cập nhật tệp trong `data/` | Không đổi |
| `replace INPUT --name NAME` | Thay tệp nguồn | Không đổi |
| `delete NAME` | Xoá tệp nguồn khỏi `data/` | Không đổi; **không** tự xoá chỉ mục — chạy `remove` sau |
| `validate [--source PATH] [--json]` | Kiểm tra `chatbot.txt` | Không đổi |
| `migrate ...` | Chuyển dữ liệu cũ sang `chatbot.txt` | Không đổi |
| `ask QUESTION [--debug]` | Hỏi qua CLI | Bổ sung: `--debug` hiển thị type/suggestions/topics/sources |

**Khuyến nghị vận hành**:

```bash
# Xoá hẳn một tài liệu
python backend/scripts/manage_docs.py delete old.pdf
python backend/scripts/manage_docs.py remove old.pdf
```

---

## 5. Exit code

| Code | Ý nghĩa |
|------|---------|
| `0` | Mọi tệp xử lý xong (kể cả `skipped`), không có tệp `failed` |
| `1` | Lỗi vận hành: đường dẫn không tồn tại, không ghi được chỉ mục, không có embedder, lỗi tham số |
| `2` | Có ít nhất một tệp `failed` trong `ingest` |

`list`, `remove` dùng `0`/`1`.

---

## 6. Ví dụ

```bash
# Nạp toàn bộ thư mục dữ liệu
python backend/scripts/manage_docs.py ingest ./backend/data

# Nạp một tệp cụ thể
python backend/scripts/manage_docs.py ingest ./backend/data/CV.pdf

# Kiểm tra tệp đã nạp + số đoạn
python backend/scripts/manage_docs.py list

# Xoá khỏi chỉ mục
python backend/scripts/manage_docs.py remove CV.pdf

# Trong Docker
docker compose exec backend python backend/scripts/manage_docs.py ingest /app/backend/data
```
