# Contract: Unified Source File Format v1

**Feature**: `005-unified-text-source` | **Version**: 1

Đây là hợp đồng định dạng cho tệp `chatbot.txt`. Parser và tooling MUST tuân theo hợp đồng này. Đặc tả đầy đủ nằm tại `specs/005-unified-text-source/spec.md`; tệp mẫu tại `specs/005-unified-text-source/template.txt`.

## 1. Encoding và kích thước

- UTF-8, không BOM.
- Unicode NFC.
- Xuống dòng LF (`\n`).
- Kích thước tối đa 20 MB.
- Phần mở rộng `.txt`.

## 2. Header

Dòng đầu tiên (sau BOM nếu có, nhưng BOM là lỗi) MUST là:

```text
CHATBOT-SOURCE v1
```

Dòng trống và chú thích được phép sau header.

## 3. Chú thích

Chú thích chỉ hợp lệ **ngoài** bản ghi: dòng bắt đầu bằng `#` ở cột 0.

## 4. Bản ghi

Mỗi bản ghi bắt đầu bằng dòng đúng:

```text
=== RECORD ===
```

và kết thúc bằng dòng đúng:

```text
=== END ===
```

Thứ tự trường bắt buộc:

```text
kind
id
topic
questions?      # bắt buộc với kind=qa
answer?         # bắt buộc với kind=qa nếu bullets rỗng
bullets?        # chỉ kind=qa
content?        # bắt buộc với kind=doc
source?
```

### 4.1 `kind`

```text
kind: qa
```

hoặc

```text
kind: doc
```

### 4.2 `id`

```text
id: gpa
```

- Regex: `^[a-z0-9][a-z0-9_-]{0,63}$`
- Duy nhất trong toàn tệp.

### 4.3 `topic`

```text
topic: Học tập & Điểm số
```

- Không rỗng, tối đa 120 ký tự.

### 4.4 `questions`

```text
questions:
- GPA của bạn là bao nhiêu?
- Điểm trung bình của bạn?
```

- Mỗi dòng bắt đầu bằng `- ` ở cột 0.
- `kind: qa` cần ít nhất 1 câu.
- Mỗi câu 1–200 ký tự, không trùng trong cùng bản ghi.

### 4.5 `answer`

```text
answer:
GPA hiện tại là 8.30 / 10 với 62 tín chỉ tích lũy.
```

- Khối nhiều dòng, kết thúc ở nhãn trường kế tiếp hoặc `=== END ===`.
- Tối đa 4.000 ký tự.
- `kind: qa` bắt buộc có `answer` hoặc `bullets`.

### 4.6 `bullets`

```text
bullets:
- GPA 8.30/10
- 62 tín chỉ
```

- Chỉ dùng với `kind: qa`.
- Mỗi bullet tối đa 300 ký tự.

### 4.7 `content`

```text
content:
GPA hiện tại của Văn Phú Đức là 8.30/10.
Bạn đã tích lũy 62 tín chỉ.
```

- Khối nhiều dòng, dùng cho RAG.
- `kind: doc` bắt buộc có `content` không rỗng.
- `kind: qa` tuỳ chọn; nếu có, RAG dùng `content`, nếu không dùng `topic + questions + answer/bullets`.

### 4.8 `source`

```text
source: BẢNG ĐIỂM HỌC TẬP - VĂN PHÚ ĐỨC.pdf#page=1
```

- Tuỳ chọn, tối đa 300 ký tự.
- Dùng cho truy vết; nếu có `#page=<n>` thì gán metadata `page`.

## 5. Escaping

Ở cột 0, các chuỗi sau là nhãn và không được xuất hiện như nội dung:

```text
=== RECORD ===
=== END ===
kind:
id:
topic:
questions:
answer:
bullets:
content:
source:
#
```

Trong khối `answer:` và `content:`, dòng nội dung bắt đầu bằng một trong các chuỗi trên MUST được thêm `\` ở đầu. Parser bỏ đúng một `\`.

```text
content:
\=== END ===
\# nội dung, không phải chú thích
\id: nội dung, không phải trường id
\\ dòng bắt đầu bằng một dấu \
```

## 6. Ví dụ hợp lệ tối thiểu

```text
CHATBOT-SOURCE v1

=== RECORD ===
kind: qa
id: gpa
topic: Học tập & Điểm số
questions:
- GPA của bạn là bao nhiêu?
answer:
GPA hiện tại là 8.30 / 10.
=== END ===

=== RECORD ===
kind: doc
id: study-plan
topic: Kế hoạch học tập
content:
Mục tiêu dài hạn là săn học bổng Thạc sĩ tại Đức.
source: data.txt
=== END ===
```

## 7. Ví dụ không hợp lệ

| Nội dung | Lỗi |
|---|---|
| Thiếu `CHATBOT-SOURCE v1` | `E_HEADER` |
| Hai bản ghi cùng `id: gpa` | `E_DUP_ID` |
| `kind: doc` không có `content` | `E_CONTENT` |
| `kind: qa` không có `questions` | `E_QUESTIONS` |
| `kind: qa` không có `answer` và `bullets` | `E_ANSWER` |
| Thiếu `=== END ===` | `E_RECORD_EOF` |
| Dòng `id: x` trong `content:` không escape | Bị hiểu là trường mới → `E_FIELD_ORDER` |
| Tệp có BOM | `E_BOM` |

## 8. Tương thích

- Parser MUST bỏ qua trường lạ với cảnh báo `W_UNKNOWN_FIELD`.
- Parser MUST giữ nguyên nội dung, không tự sửa chính tả, không tự chuẩn hoá dấu.
- Chuẩn hoá tìm kiếm diễn ra sau khi parse, dùng `normalize_text`/`normalize_query` hiện có.
