# Contract: Query Normalization Pipeline

**Feature**: `004-self-intro-chatbot-api`

---

## Mô tả

`normalize_query(text)` là hàm chuẩn hoá câu hỏi đầu vào trước khi tính embedding và fuzzy score. Nó **mở rộng** `normalize_text()` hiện tại — không thay thế.

Thứ tự pipeline **bất biến** (thay đổi thứ tự là breaking change):

| Bước | Mô tả | Ví dụ |
|------|-------|-------|
| 1 | Giới hạn độ dài — cắt tại 200 ký tự | Phòng thủ trước bước 2+ |
| 2 | Unicode NFC | Dấu tiếng Việt khác dạng mã hoá → đồng nhất |
| 3 | Lowercase | "BẠN" → "bạn" |
| 4 | Trim whitespace đầu/cuối | "  hello  " → "hello" |
| 5 | Gom ký tự lặp ≥ 3 lần | "giỏiiii" → "giỏi" |
| 6 | Bỏ emoji và ký tự đặc biệt | Giữ chữ cái (Unicode letter), số, dấu `?!.,` |
| 7 | Teencode mapping | "ko" → "không", "dc" → "được", "j" → "gì" |
| 8 | Bỏ từ đệm | "ơi", "nhỉ", "vậy", "à", "nhé" |
| 9 | Collapse whitespace | Nhiều dấu cách → 1 dấu cách |
| 10 | Guard: nếu không còn ký tự alphanumeric → trả `""` | Input toàn ký tự đặc biệt |

---

## Teencode dictionary (v1)

| Input | Chuẩn hoá |
|-------|-----------|
| `ko`, `k`, `hok`, `hông` | `không` |
| `dc`, `đc` | `được` |
| `j` | `gì` |
| `ntn` | `như thế nào` |
| `bn` | `bạn` |
| `mk`, `mik` | `mình` |
| `wa` | `quá` |
| `lh` | `liên hệ` |
| `cv` | `công việc` |
| `btw` | `nhân tiện` |
| `ok`, `oke`, `okie` | `được` |
| `vs` | `với` |
| `trc` | `trước` |
| `sau đó`, `r` (cuối câu) | `rồi` |

Từ điển áp dụng **word-boundary** (regex `\b{word}\b`) để tránh thay thế sai trong từ dài.

---

## Từ đệm bị bỏ

`["ơi", "nhỉ", "vậy", "à", "nhé", "nha", "ha", "hả", "ạ"]`

Áp dụng sau khi tokenize bằng split whitespace; bỏ nếu là token độc lập.

---

## Hành vi khi input không hợp lệ

- Input rỗng sau trim → `""` (caller xử lý là lỗi validation).
- Input toàn emoji → `""`.
- Input toàn số → giữ nguyên số (có thể là năm, điểm số).

---

## Quan hệ với `normalize_text()`

```python
def normalize_query(text: str) -> str:
    """Full pipeline for user query normalization."""
    # Steps 1–6, 9–10 reuse normalize_text() internals
    # Steps 7–8 are new (teencode + filler words)
    ...

def normalize_text(text: str, lowercase: bool = True) -> str:
    """Existing function — unchanged signature, used for document indexing."""
    ...
```

`normalize_text(lowercase=False)` tiếp tục được dùng khi index **tài liệu** (RAG pipeline). `normalize_query` chỉ dùng cho **câu hỏi** từ người dùng.
