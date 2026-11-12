# Contract: `manage_docs.py` — lệnh vận hành (mở rộng feature 007)

CLI hiện có: `python backend/scripts/manage_docs.py <command>` (chạy trong container `backend` hoặc venv). Tệp này đặc tả **subcommand mới** và hợp đồng hành vi; các subcommand cũ (`add|replace|delete|list|ingest|remove|ask|validate|migrate`) giữ nguyên.

## Nguyên tắc chung cho mọi lệnh ghi

1. `validate` → kiểm tra mâu thuẫn với facts/courses hiện có → ghi tệp tạm cùng thư mục → `os.replace()` → server tự nạp lại (signature).
2. Bất kỳ bước lỗi → **dừng, không ghi**, in lỗi ra stderr với mã và vị trí (số dòng / tên tệp), exit code ≠ 0.
3. Đầu ra thành công: dòng tóm tắt ngắn bằng tiếng Việt; thêm cờ `--json` in kết quả có cấu trúc.

## Subcommand mới

### `add fact`

```text
python backend/scripts/manage_docs.py add fact --id gpa-10 \
    --label "GPA tích lũy (thang 10)" --value 8.51 \
    [--snapshot 2026-11-07] [--source bang-diem.pdf]
```

- `--id` bắt buộc, khớp `^[a-z0-9][a-z0-9_-]{0,63}$`, duy nhất toàn tệp nguồn.
- Nếu `--id` đã tồn tại là fact: cập nhật `value` (và các trường đi kèm nếu truyền); nếu `id` đang là record qa/doc → `E_CONFLICT`, dừng.
- Sau khi ghi: validate lại toàn tệp; nếu câu trả lời nào dùng `{{id}}` bị ảnh hưởng, không cần sửa gì thêm.

### `add qa`

```text
python backend/scripts/manage_docs.py add qa --topic "Mục tiêu" \
    --q "Mục tiêu học bổng của bạn?" [--q "Bạn muốn học thạc sĩ ở đâu?"] \
    --a "Mục tiêu dài hạn của mình là săn học bổng Thạc sĩ tại Đức, trường mục tiêu TUHH."
```

- Tự sinh `id` = slug từ `--topic` (viết thường, không dấu, gạch nối); nếu trùng, thêm hậu tố số.
- Cho phép `--a` nhiều dòng (kết thành khối `answer`) hoặc `--bullets "ý 1" --bullets "ý 2"` (không dùng đồng thời với `--a`).
- `--q` tối thiểu 1, tối đa 5 (mỗi câu ≤ 200 ký tự).
- Record mới mặc định `status: active`; menu chủ đề tự có chủ đề mới (không cần cấu hình).

### `add course`

```text
python backend/scripts/manage_docs.py add course --code CSC10010 --name "Tên môn" \
    --credits 4 --score10 8.0 [--score4 3.5] [--letter B+] \
    [--counts-major yes] [--aliases "tm|tên tắt"]
```

- Ghi **thêm một dòng** vào `sources/courses.csv` (không sửa `chatbot.txt`).
- Kiểm tra: không trùng `code`/`name`; nếu trùng → `E_CONFLICT` kèm dòng hiện có.
- Sau khi ghi: tính lại số tổng hợp; nếu lệch dòng tổng kết PDF → `W_CONFLICT` vẫn ghi nhưng in cảnh báo.
- Ngay request kế tiếp, chatbot trả lời được điểm/tín chỉ/xét chuyên ngành của môn mới và GPA/tổng TC đổi theo.

### `ingest inbox/`

```text
python backend/scripts/manage_docs.py ingest inbox/          # nạp cả thư mục
python backend/scripts/manage_docs.py ingest inbox/ten.pdf    # nạp một tệp
```

- Đọc tệp trong `backend/data/inbox/` (PDF/DOCX/XLSX/CSV/TXT), vệ sinh (bỏ `nan`/`Unnamed`/`about:blank`, làm tròn số nhiễu, trang từ 1), chunk và nạp vào chỉ mục RAG.
- Dấu vân tay SHA-256: tệp không đổi → bỏ qua; đổi → nạp lại phần thay đổi.
- Tệp chứa `[...]` → `E_PLACEHOLDER`; còn `nan`/`Unnamed`/`about:blank` sau vệ sinh → `E_NOISE`; tệp đó bị từ chối, các tệp khác vẫn được xử lý, tổng kết cuối lệnh liệt kê từng tệp: đã nạp / bỏ qua / lỗi (kèm mã).
- Không được ghi vào `chatbot.txt`; chỉ ghi chỉ mục phái sinh.

### `validate` (mở rộng)

```text
python backend/scripts/manage_docs.py validate [--source path] [--json]
```

Kiểm tra bổ sung (không cần Ollama):

1. Cú pháp tệp nguồn (kế thừa 005) + `kind: fact` hợp lệ + placeholder đều tồn tại (`E_PLACEHOLDER_UNKNOWN`).
2. `courses.csv`: header, khoảng giá trị, trùng code/name, bí danh trùng.
3. `aliases.txt`: cú pháp từng dòng, không trùng.
4. Đối chiếu số tổng hợp ↔ fact ↔ dòng tổng kết PDF → `W_CONFLICT`.
5. Quét chuỗi rác và giá trị cũ (`8.30`, `62 tín chỉ`, `17 môn`, `3.7/4.0`) trong toàn bộ nội dung sẽ phục vụ trả lời → lỗi `E_STALE_VALUE`.

Exit code: 0 = hợp lệ (có thể kèm warning), ≠ 0 = có lỗi; `--json` in danh sách issue `{severity, code, line/record_id/file, message}`.

## Mã lỗi mới (bảng tổng)

| Mã | Mức | Ý nghĩa |
|---|---|---|
| `E_PLACEHOLDER_UNKNOWN` | error | `{{id}}` không tồn tại |
| `E_PLACEHOLDER` | error | tệp inbox còn `[...]` chưa điền |
| `E_NOISE` | error | tệp inbox còn `nan`/`Unnamed`/`about:blank` |
| `E_CONFLICT` | error | trùng id/giá trị mâu thuẫn/trùng code/name |
| `E_STALE_VALUE` | error | còn giá trị cũ (8.30, 62 TC, 17 môn, 3.7/4.0) |
| `E_BAD_CSV` / `E_BAD_VALUE` / `E_BAD_ENUM` / `E_MISSING_FIELD` / `E_FIELD_NOT_ALLOWED` | error | lỗi dữ liệu courses/fact |
| `W_CONFLICT` | warning | số tổng hợp lệch giá trị fact/PDF |

## Hợp đồng phản hồi API (không đổi)

`POST /chat`, `POST /chat/stream` giữ nguyên lược đồ `type: answer|suggest|clarify`, `topics`, `suggestions` từ feature 004/006. Feature này chỉ thay **dữ liệu nguồn** và cách sinh dữ liệu, không đổi hợp đồng trả lời.
