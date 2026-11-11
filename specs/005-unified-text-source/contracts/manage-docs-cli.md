# Contract: `manage_docs.py` CLI

**Feature**: `005-unified-text-source` | **Version**: 1

Các subcommand hiện có (`add`, `replace`, `delete`, `list`, `ask`) giữ nguyên hợp đồng. Feature này bổ sung `validate` và `migrate`.

## 1. `validate`

```bash
python backend/scripts/manage_docs.py validate [--source PATH] [--json]
```

| Option | Mặc định | Mô tả |
|---|---|---|
| `--source PATH` | `CHATBOT_SOURCE_PATH` hoặc `backend/data/chatbot.txt` | Tệp cần kiểm tra |
| `--json` | tắt | In kết quả dạng JSON ra stdout |

**Điều kiện**:

- Không cần Ollama, không cần model.
- Chỉ đọc tệp, không sửa.
- In tất cả lỗi/cảnh báo, mỗi mục có `severity`, `code`, `line`, `record_id`, `message`.

**Exit code**:

| Code | Ý nghĩa |
|---|---|
| `0` | Hợp lệ, có thể có warning |
| `2` | Có ít nhất một error |
| `1` | Lỗi vận hành ngoài dự kiến (không đọc được, lỗi nội bộ) |

**JSON schema**:

```json
{
  "path": "backend/data/chatbot.txt",
  "valid": true,
  "counts": { "records": 12, "qa": 10, "doc": 2 },
  "errors": [],
  "warnings": [
    {
      "severity": "warning",
      "code": "W_UNKNOWN_FIELD",
      "line": 42,
      "record_id": "gpa",
      "message": "Trường 'foo' không được hỗ trợ, đã bỏ qua"
    }
  ]
}
```

Khi `valid=false`, `errors` chứa các mục cùng cấu trúc.

## 2. `migrate`

```bash
python backend/scripts/manage_docs.py migrate \
  --to backend/data/chatbot.txt \
  [--from-data backend/data] \
  [--qa backend/qa.txt] \
  [--kb backend/kb.json] \
  [--force]
```

| Option | Mặc định | Mô tả |
|---|---|---|
| `--to PATH` | `CHATBOT_SOURCE_PATH` hoặc `backend/data/chatbot.txt` | Tệp đích |
| `--from-data DIR` | `backend/data` | Thư mục tài liệu cũ |
| `--qa PATH` | `backend/qa.txt` | Tệp Q&A cũ |
| `--kb PATH` | `backend/kb.json` | KB cũ |
| `--force` | tắt | Ghi đè tệp đích nếu đã tồn tại |

**Hành vi**:

1. Đọc `kb.json` → record `kind: qa`; giữ nguyên `id`, `topic`, `questions`, `answer`, `answer_bullets` → `bullets`.
2. Đọc `qa.txt` → record `kind: qa`; nếu câu hỏi đã có trong KB thì bỏ qua, không tạo trùng.
3. Đọc các tệp được hỗ trợ trong `--from-data` → record `kind: doc`; `content` là văn bản trích xuất, `source` là tên tệp (PDF kèm `#page=<n>` nếu tách theo trang).
4. Ghi tệp tạm cùng thư mục, `fsync`, rồi `os.replace` để thay thế nguyên tử.
5. Không gọi Ollama, không sửa dữ liệu gốc.
6. Thứ tự record xác định: KB theo thứ tự gốc, QA mới theo thứ tự `qa.txt`, tài liệu theo tên tệp đã sắp xếp.

**Exit code**:

| Code | Ý nghĩa |
|---|---|
| `0` | Migrate thành công |
| `1` | Lỗi (thiếu nguồn, tệp đích tồn tại mà không có `--force`, không ghi được) |

**Output** (text):

```text
Đã ghi 12 bản ghi vào backend/data/chatbot.txt
  qa: 10
  doc: 2
```

## 3. Tương thích

- `add`, `replace`, `delete`, `list` tiếp tục thao tác trên `backend/data/` trong giai đoạn chuyển đổi.

## 4. Ví dụ

```bash
# Kiểm tra mẫu
python backend/scripts/manage_docs.py validate \
  --source specs/005-unified-text-source/template.txt

# Chuyển dữ liệu hiện tại
python backend/scripts/manage_docs.py migrate \
  --to backend/data/chatbot.txt --force

# Kiểm tra lại
python backend/scripts/manage_docs.py validate --json
```
