# Contract: `chatbot.txt` — định dạng mở rộng (fact, placeholder, status)

Kế thừa toàn bộ hợp đồng từ `specs/005-unified-text-source/spec.md` (header `CHATBOT-SOURCE v1`, UTF-8 không BOM, LF, NFC, ≤ 20 MB, trường lạ → cảnh báo bỏ qua, lỗi kèm số dòng). Tệp này chỉ đặc tả **phần mở rộng** của feature 007.

## Ngữ pháp bổ sung

```text
record      = "=== RECORD ===", newline, kind-line, newline,
              id-line, newline,
              ( fact-fields | qa-doc-fields ),
              [ status-line, newline ],
              "=== END ===", newline ;

kind-line   = "kind:", ws, ("qa" | "doc" | "fact"), newline ;
id-line     = "id:", ws, slug, newline ;
status-line = "status:", ws, ("active" | "archived") ;
fact-fields = "label:", ws, text, newline,
              "value:", ws, text, newline,
              [ "snapshot:", ws, date, newline ] ;
```

- `slug`: `^[a-z0-9][a-z0-9_-]{0,63}$`, duy nhất toàn tệp trên **mọi** kind.
- `date`: `YYYY-MM-DD`.
- `fact` chỉ dùng các trường `label`, `value`, `snapshot`, `source`, `status`; không dùng `questions`/`answer`/`bullets`/`content`.
- `qa`/`doc` giữ nguyên trường cũ và **được phép** thêm `status` (mặc định `active`).

## Ví dụ fact

```text
=== RECORD ===
kind: fact
id: gpa-10
label: GPA tích lũy (thang 10)
value: 8.51
snapshot: 2026-11-07
source: bang-diem.pdf
=== END ===
```

## Placeholder `{{id}}`

- Chỉ có hiệu lực trong khối nội dung của `qa` (answer/bullets) và `doc` (content).
- `{{id}}` tham chiếu đúng một fact có trạng thái `active`.
- Lỗi khi validate nếu tham chiếu không tồn tại → `E_PLACEHOLDER_UNKNOWN` (severity `error`, kèm số dòng và id record chứa placeholder); tệp không được nạp.
- Thoát theo nghĩa đen: `\{{id}}` → hiển thị `{{id}}` mà không thay thế (cùng quy tắc dấu `\` đã có ở feature 005).

## Mã lỗi mở rộng (bổ sung cho bảng lỗi của 005)

| Tình huống | Mã | Mức | Hành vi |
|---|---|---|---|
| `{{id}}` không tồn tại | `E_PLACEHOLDER_UNKNOWN` | error | không nạp; ghi số dòng + id |
| Hai fact cùng `id` khác `value` | `E_CONFLICT` | error | không nạp; ghi hai số dòng |
| `kind: fact` thiếu `label`/`value` | `E_MISSING_FIELD` | error | không nạp; ghi id + số dòng |
| `kind: fact` có `questions`/`answer`… | `E_FIELD_NOT_ALLOWED` | error | không nạp |
| `status` khác `active`/`archived` | `E_BAD_ENUM` | error | không nạp |
| Số tổng hợp tính từ `courses.csv` lệch giá trị fact tương ứng | `W_CONFLICT` | warning | vẫn nạp; in hai giá trị |

## Quy tắc runtime

1. Record `archived` (mọi kind): không vào KB engine, không vào khớp mờ, không vào RAG, không vào gợi ý/menu chủ đề.
2. Khi trả lời, mọi `{{id}}` được thay bằng `value` của fact tại thời điểm nạp gần nhất (không cache cũ).
3. Sửa một fact → mọi câu trả lời dùng `{{id}}` đổi theo ở request kế tiếp (reload theo signature).
