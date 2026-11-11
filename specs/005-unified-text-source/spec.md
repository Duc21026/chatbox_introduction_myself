# Feature Specification: Unified Text Knowledge Source

**Feature Branch**: `005-unified-text-source`

**Created**: 2026-11-11

**Status**: Draft

**Input**: User description: "hợp nhất cho tôi 1 file text thôi, cho ra những yêu cầu cần có cho file text đó" — thay ba nguồn `backend/data/`, `backend/qa.txt`, `backend/kb.json` bằng một tệp văn bản duy nhất, đồng thời định nghĩa đầy đủ yêu cầu về định dạng, nội dung, kiểm tra hợp lệ và cách ánh xạ sang KB Engine, khớp mờ và RAG.

## Mục tiêu

- Một nguồn tri thức duy nhất do người vận hành chỉnh sửa: `backend/data/chatbot.txt`.
- Một tệp văn bản thuần (UTF-8) vừa chứa Q&A soạn sẵn, vừa chứa nội dung tự do cho RAG.
- Thay thế dần `kb.json`, `qa.txt` và việc quét nhiều tệp trong `backend/data/`.
- Giữ nguyên hành vi trả lời hiện tại và các hợp đồng `POST /chat`, `POST /chat/stream`.

## Phạm vi

**Trong phạm vi**

- Định dạng tệp, quy tắc mã hoá, cấu trúc bản ghi và cách thoát ký tự.
- Yêu cầu kiểm tra hợp lệ, thông báo lỗi và hành vi khi tệp sai.
- Ánh xạ từng bản ghi sang KB Engine, khớp mờ `qa.txt` và chỉ mục RAG.
- Yêu cầu chuyển đổi dữ liệu từ ba nguồn cũ sang tệp mới.
- Cấu hình đường dẫn tệp và cách vận hành trong Docker.

**Ngoài phạm vi**

- Giao diện quản trị để sửa tệp.
- Đồng bộ nhiều người dùng hoặc lịch sử phiên bản nội dung.
- OCR cho PDF scan.
- Thay đổi mô hình, ngưỡng điểm hoặc thuật toán xếp hạng hiện có.

## Định dạng tệp (chuẩn bắt buộc)

### Tên, vị trí, mã hoá

| Thuộc tính | Yêu cầu |
|---|---|
| Đường dẫn mặc định | `backend/data/chatbot.txt` |
| Cấu hình | `CHATBOT_SOURCE_PATH` (một biến duy nhất) |
| Định dạng | Văn bản thuần, không nén, không nhị phân |
| Mã hoá | UTF-8, **không** BOM |
| Chuẩn hoá Unicode | NFC |
| Xuống dòng | LF (`\n`), không dùng CRLF |
| Kích thước tối đa | 20 MB (vượt quá → từ chối nạp) |
| Phần mở rộng | `.txt` |

### Cấu trúc tổng thể

```text
CHATBOT-SOURCE v1

# chú thích ngoài bản ghi
=== RECORD ===
kind: qa | doc
id: <slug duy nhất>
topic: <chủ đề>
questions:
- <câu hỏi 1>
- <câu hỏi 2>
answer:
<khối văn bản nhiều dòng>
bullets:
- <ý 1>
- <ý 2>
content:
<khối văn bản nhiều dòng dùng cho RAG>
source: <nguồn gốc, tuỳ chọn>
=== END ===
```

### Ngữ pháp rút gọn

```text
file        = header, { blank | comment | record } ;
header      = "CHATBOT-SOURCE v1", newline ;
comment     = "#", { any-char }, newline ;
record      = "=== RECORD ===", newline,
              "kind:", ws, ("qa" | "doc"), newline,
              "id:", ws, slug, newline,
              "topic:", ws, text, newline,
              [ questions-block ],
              [ answer-block ],
              [ bullets-block ],
              [ content-block ],
              [ "source:", ws, text, newline ],
              "=== END ===", newline ;
```

- `questions-block`, `answer-block`, `bullets-block`, `content-block` bắt đầu bằng dòng nhãn ở **cột 0** và kết thúc khi gặp dòng nhãn kế tiếp hoặc `=== END ===`.
- Mọi dòng nhãn phải viết đúng chữ thường, đúng dấu `:`.
- Dòng trống và dòng bắt đầu bằng `#` ở **ngoài** khối nội dung được bỏ qua.
- Thứ tự các trường trong một bản ghi là cố định như ngữ pháp trên.

### Trường bắt buộc

| Trường | `kind: qa` | `kind: doc` | Ghi chú |
|---|---|---|---|
| `kind` | Bắt buộc | Bắt buộc | Chỉ nhận `qa` hoặc `doc` |
| `id` | Bắt buộc | Bắt buộc | Duy nhất toàn tệp, `[a-z0-9][a-z0-9_-]{0,63}` |
| `topic` | Bắt buộc | Bắt buộc | Không rỗng, tối đa 120 ký tự |
| `questions` | Bắt buộc, ≥ 1 | Tuỳ chọn | Mỗi câu không rỗng, tối đa 200 ký tự |
| `answer` | Bắt buộc nếu không có `bullets` | Không dùng | Tối đa 4.000 ký tự |
| `bullets` | Tuỳ chọn | Không dùng | Mỗi bullet tối đa 300 ký tự |
| `content` | Tuỳ chọn | Bắt buộc | Khối văn bản tự do cho RAG |
| `source` | Tuỳ chọn | Tuỳ chọn | Nhãn truy vết, ví dụ `data.txt` hoặc `file.pdf#page=2` |

### Quy tắc thoát ký tự

Các chuỗi sau chỉ có ý nghĩa đặc biệt khi nằm ở **cột 0**:

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

Trong các khối `answer:` và `content:`, nếu một dòng nội dung bắt đầu bằng một trong các chuỗi trên, phải thêm tiền tố `\`:

```text
content:
\=== END ===
\# đây là nội dung, không phải chú thích
\id: giá trị ví dụ
```

Parser bỏ đúng một ký tự `\` ở đầu khi gặp các trường hợp trên. Dòng bắt đầu bằng `\\` được hiểu là một ký tự `\` theo sau là nội dung còn lại.

## Yêu cầu chức năng

- **FR-001**: Hệ thống MUST đọc toàn bộ tri thức từ đúng một tệp `CHATBOT_SOURCE_PATH`.
- **FR-002**: Hệ thống MUST từ chối khởi động nếu tệp thiếu, không đọc được, sai mã hoá, hoặc thiếu dòng `CHATBOT-SOURCE v1`.
- **FR-003**: Hệ thống MUST kiểm tra toàn bộ tệp trước khi thay thế trạng thái đang chạy; tệp sai không được nạp một phần.
- **FR-004**: Hệ thống MUST báo lỗi kèm **số dòng** và **id bản ghi** (nếu xác định được) cho mọi lỗi định dạng.
- **FR-005**: Mỗi `id` MUST là duy nhất trong tệp; trùng `id` là lỗi.
- **FR-006**: Một bản ghi `kind: qa` MUST tạo được câu trả lời từ `answer` hoặc `bullets`; nếu cả hai rỗng thì là lỗi.
- **FR-007**: Một bản ghi `kind: doc` MUST có `content` không rỗng; nếu rỗng thì là lỗi.
- **FR-008**: Với `kind: qa`, mọi câu trong `questions` MUST được dùng cho KB Engine và khớp mờ; câu trả lời là `answer`/`bullets`.
- **FR-009**: Với `kind: doc`, nội dung `content` MUST được đưa vào chỉ mục RAG; bản ghi này MUST NOT xuất hiện trong KB Engine hoặc gợi ý câu hỏi.
- **FR-010**: Với `kind: qa`, nội dung RAG MUST lấy từ `content` nếu có; nếu không, lấy từ `topic`, `questions` và `answer`/`bullets`.
- **FR-011**: Hệ thống MUST áp dụng cùng chuẩn hoá văn bản hiện có (`normalize_text` cho tài liệu, `normalize_query` cho câu hỏi) sau khi nạp tệp.
- **FR-012**: Hệ thống MUST tái tạo chỉ mục FAISS và embedding cache khi tệp thay đổi (theo `mtime`/kích thước/hash), không cần khởi động lại thủ công.
- **FR-013**: Hệ thống MUST giữ nguyên `qa.txt` tương thích nghịch đảo trong giai đoạn chuyển đổi nếu cờ `CHATBOT_LEGACY_SOURCES=true`; mặc định là tắt.
- **FR-014**: Hệ thống MUST cung cấp lệnh kiểm tra tệp mà không cần kết nối Ollama (kiểm tra cú pháp, id trùng, trường thiếu).
- **FR-015**: Hệ thống MUST hỗ trợ tối thiểu các loại nội dung hiện có: Q&A soạn sẵn, bullet, văn bản tự do nhiều đoạn, và nhãn nguồn.

## Yêu cầu phi chức năng

- **NFR-001**: Nạp và kiểm tra tệp 1 MB MUST hoàn tất trong vòng 1 giây trên máy phát triển.
- **NFR-002**: Thông báo lỗi MUST bằng tiếng Việt, nêu rõ cách sửa.
- **NFR-003**: Định dạng MUST đọc được bằng mắt thường và so sánh được bằng `diff`.
- **NFR-004**: Việc thêm trường mới trong tương lai MUST không làm hỏng parser cũ; trường lạ bị bỏ qua kèm cảnh báo.
- **NFR-005**: Không được ghi đè hoặc sửa tệp nguồn khi đang chạy; mọi thay đổi do người vận hành thực hiện.
- **NFR-006**: Tệp MUST không chứa bí mật, khoá API, mật khẩu hoặc dữ liệu cá nhân ngoài phạm vi giới thiệu.

## Ánh xạ từ ba nguồn cũ

| Nguồn cũ | Cách chuyển sang tệp hợp nhất |
|---|---|
| Mỗi object trong `backend/kb.json` | Một bản ghi `kind: qa`, giữ `id`, `topic`, `questions`, `answer`, `answer_bullets` → `bullets` |
| Mỗi dòng `câu hỏi\|câu trả lời` trong `backend/qa.txt` | Một bản ghi `kind: qa`; nếu trùng câu hỏi với KB thì gộp vào bản ghi KB, không tạo trùng |
| Mỗi tệp trong `backend/data/` | Một hoặc nhiều bản ghi `kind: doc`; `content` là văn bản đã trích xuất, `source` là tên tệp gốc (kèm số trang PDF nếu có) |

Quy tắc gộp:

1. Ưu tiên nội dung từ `kb.json` khi cùng câu hỏi.
2. Câu hỏi chỉ có trong `qa.txt` được giữ nguyên câu trả lời soạn sẵn.
3. Nội dung tài liệu không bị cắt thành nhiều bản ghi nếu vẫn đọc được trong một khối `content`; việc chia nhỏ cho RAG do hệ thống thực hiện sau khi nạp.
4. Không tự suy diễn hoặc viết lại nội dung khi chuyển đổi.

## Kiểm tra hợp lệ và hành vi khi lỗi

| Tình huống | Kết quả |
|---|---|
| Thiếu tệp | Lỗi khởi động, nêu đường dẫn và biến `CHATBOT_SOURCE_PATH` |
| Sai header/version | Lỗi khởi động, nêu số dòng 1 |
| Thiếu `=== END ===` | Lỗi, nêu số dòng bắt đầu bản ghi |
| `id` trùng | Lỗi, nêu cả hai số dòng |
| `questions` rỗng với `kind: qa` | Lỗi, nêu `id` và số dòng |
| `answer` và `bullets` đều rỗng với `kind: qa` | Lỗi, nêu `id` |
| `content` rỗng với `kind: doc` | Lỗi, nêu `id` |
| Trường lạ | Cảnh báo, bỏ qua, vẫn nạp |
| Dòng nhãn sai chính tả | Lỗi cú pháp, nêu số dòng |
| Tệp > 20 MB | Từ chối nạp, nêu kích thước |
| Tệp có BOM | Từ chối hoặc tự bỏ BOM kèm cảnh báo; không được coi BOM là nội dung |

Khi tệp mới không hợp lệ, hệ thống MUST tiếp tục dùng trạng thái đã nạp gần nhất nếu đang chạy, và MUST báo lỗi rõ nếu đang khởi động.

## Tiêu chí chấp nhận

1. **Given** tệp `chatbot.txt` chứa bản ghi `gpa`, **When** hỏi "GPA của bạn là bao nhiêu?", **Then** câu trả lời giống hệt khi dùng `kb.json` hiện tại và có `type: "answer"`.
2. **Given** câu hỏi chỉ có trong `qa.txt` cũ, **When** chuyển sang tệp hợp nhất, **Then** khớp mờ vẫn trả đúng câu trả lời soạn sẵn.
3. **Given** một `kind: doc` chứa đoạn văn về học bổng, **When** hỏi nội dung chỉ có trong đoạn đó, **Then** RAG truy xuất đúng và trả lời từ nội dung ấy.
4. **Given** tệp có hai bản ghi trùng `id`, **When** khởi động, **Then** hệ thống dừng với lỗi nêu hai số dòng.
5. **Given** tệp sai cú pháp, **When** chạy lệnh kiểm tra, **Then** lệnh trả mã lỗi khác 0 và in số dòng sai, không cần Ollama.
6. **Given** tệp được sửa nội dung, **When** có request tiếp theo, **Then** KB/RAG dùng nội dung mới sau khi chỉ mục được làm mới.
7. **Given** Docker chỉ mount `./backend/data/chatbot.txt`, **When** chạy `docker compose up`, **Then** không cần `qa.txt` hay `kb.json` để trả lời.
8. **Given** một dòng nội dung bắt đầu bằng `=== END ===`, **When** dùng tiền tố `\`, **Then** parser giữ nguyên dòng đó trong câu trả lời.

## Chuyển đổi và vận hành

- Thêm biến `CHATBOT_SOURCE_PATH=backend/data/chatbot.txt`; giữ `CHATBOT_DATA_DIR`, `CHATBOT_QA_PATH`, `CHATBOT_KB_PATH` ở trạng thái deprecated trong một phiên bản.
- Cung cấp lệnh `python backend/scripts/manage_docs.py migrate --to backend/data/chatbot.txt` để sinh tệp từ ba nguồn cũ.
- Cung cấp lệnh `python backend/scripts/manage_docs.py validate` để kiểm tra tệp.
- Docker bind mount một tệp duy nhất; bỏ mount `qa.txt` và `kb.json` sau khi chuyển đổi xong.
- Ghi lại định dạng trong `README.md` và thêm mẫu tại `specs/005-unified-text-source/template.txt`.

## Ví dụ tối thiểu

Xem `specs/005-unified-text-source/template.txt`.
