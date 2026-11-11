# Feature Specification: Self-Introduction Chatbot API

**Feature Branch**: `004-self-intro-chatbot-api`

**Created**: 2026-11-10

**Status**: Draft

**Input**: User description: "Chatbot giới thiệu bản thân (Ollama + Qwen) — trả lời từ danh sách soạn sẵn, tiền xử lý tiếng Việt, hybrid scoring, FastAPI backend."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Câu hỏi khớp rõ (Priority: P1)

Người dùng gõ câu hỏi đúng hoặc gần đúng về chủ nhân chatbot (kỹ năng, dự án, học vấn, liên hệ…). Chatbot trả lời ngay lập tức từ danh sách soạn sẵn mà không gọi LLM.

**Why this priority**: Đây là luồng chính chiếm > 80% lượt dùng. Phải đúng và nhanh.

**Independent Test**: Gửi `POST /chat` với câu khớp hoàn toàn → nhận `type: "answer"` với `score ≥ 0.78` trong < 100 ms.

**Acceptance Scenarios**:

1. **Given** câu hỏi "Bạn biết những ngôn ngữ lập trình nào?" đã có trong kb.json, **When** người dùng gửi câu đó qua `/chat`, **Then** API trả về `type: "answer"`, `score ≥ 0.78` và `answer` không rỗng trong < 100 ms.
2. **Given** câu hỏi viết tắt "cv của bạn là j", **When** pipeline tiền xử lý chuẩn hoá thành "công việc của bạn là gì", **Then** kết quả khớp với mục "công việc / kỹ năng" và trả về `type: "answer"`.
3. **Given** câu hỏi có lỗi gõ nhẹ "bạnn biết ngon ngu nào", **When** hybrid score (embedding + fuzzy) ≥ 0.78, **Then** trả về đúng câu trả lời tương ứng.

---

### User Story 2 – Câu hỏi mơ hồ / sai chính tả nặng (Priority: P2)

Người dùng gõ không dấu, teencode hoặc sai chính tả khiến điểm khớp rơi vào vùng trung gian. Chatbot gợi ý top 3 câu hỏi gần nhất dưới dạng nút bấm.

**Why this priority**: Giảm tỉ lệ "unknown" giả, giữ người dùng trong luồng.

**Independent Test**: Gửi câu không dấu "ban biet ngon ngu j" → nhận `type: "suggest"` với ≥ 1 gợi ý. Bấm vào gợi ý → nhận `type: "answer"`.

**Acceptance Scenarios**:

1. **Given** câu "ban biet ngon ngu j" (không dấu + teencode), **When** hybrid score 0.55–0.78, **Then** trả về `type: "suggest"` với 1–3 mục, mỗi mục có `question` và `score`.
2. **Given** người dùng bấm chọn gợi ý "Bạn biết những ngôn ngữ lập trình nào?", **When** gửi lại `/chat` với câu đó, **Then** nhận `type: "answer"` với `score ≥ 0.78`.
3. **Given** sai chính tả nặng vùng MID, **When** Qwen sửa chính tả rồi embed lại vẫn < 0.78, **Then** vẫn trả `type: "suggest"` (không escalate lên "answer" sai).

---

### User Story 3 – Câu hỏi ngoài phạm vi (Priority: P3)

Người dùng hỏi chủ đề không có trong kb.json (thời tiết, lịch sử, v.v.). Chatbot từ chối lịch sự và gợi ý chủ đề có sẵn.

**Why this priority**: Tránh câu trả lời sai hoặc "ảo giác". Trải nghiệm vẫn tốt khi không có câu trả lời.

**Independent Test**: Gửi "Hôm nay thời tiết thế nào?" → nhận `type: "unknown"` với danh sách `topics`.

**Acceptance Scenarios**:

1. **Given** câu hỏi hoàn toàn ngoài phạm vi với hybrid score < 0.55, **When** gửi `/chat`, **Then** trả về `type: "unknown"`, `message` chứa thông báo lịch sự, và `topics` liệt kê ≥ 3 chủ đề có sẵn.
2. **Given** câu hỏi chứa từ tục tĩu, **When** pipeline phát hiện, **Then** trả về `type: "unknown"` với nội dung lịch sự (không xử lý thêm, không lưu log nội dung).
3. **Given** input rỗng hoặc quá dài (> 200 ký tự), **When** gửi `/chat`, **Then** API trả về lỗi validation HTTP 422 với thông báo rõ ràng.

---

### User Story 4 – Vận hành & cập nhật nội dung (Priority: P4)

Chủ nhân chatbot chỉnh sửa `kb.json` để thêm/sửa câu hỏi-đáp mà không cần thay đổi code hay khởi động lại thủ công.

**Why this priority**: Dễ bảo trì; nội dung thay đổi thường xuyên hơn code.

**Independent Test**: Sửa `kb.json` → gọi reload endpoint (hoặc khởi động lại server) → câu hỏi mới có thể trả lời được.

**Acceptance Scenarios**:

1. **Given** `kb.json` được chỉnh sửa thêm mục mới, **When** server khởi động lại, **Then** embedding cache tự build lại và mục mới có thể tìm thấy qua `/chat`.
2. **Given** `kb.json` không thay đổi so với lần trước, **When** server khởi động, **Then** embedding được nạp từ cache (không build lại), thời gian khởi động < 5 s.

---

### Edge Cases

- Câu hỏi chỉ có số hoặc ký tự đặc biệt → validation từ chối (HTTP 422).
- `kb.json` trống hoặc thiếu trường bắt buộc → server log lỗi rõ ràng và từ chối khởi động.
- Ollama không khả dụng lúc khởi động → warm-up thất bại nhưng server vẫn chạy; log cảnh báo; các câu khớp cao (không cần Qwen) vẫn hoạt động.
- Nhiều request đồng thời đến endpoint sửa chính tả (vùng MID) → async xử lý song song, không deadlock.
- IP gửi quá nhiều request trong 1 phút → rate limiter trả HTTP 429.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Hệ thống PHẢI nhận `POST /chat` với body `{ "message": string }` và trả JSON theo đúng một trong ba cấu trúc: `answer`, `suggest`, `unknown`.
- **FR-002**: Hệ thống PHẢI pipeline tiền xử lý theo thứ tự: giới hạn độ dài → Unicode NFC → lowercase/trim → gom ký tự lặp → bỏ emoji/ký tự đặc biệt → chuẩn hoá teencode → chuẩn hoá từ đệm.
- **FR-003**: Hệ thống PHẢI tính hybrid score = `0.8 × cosine_embedding + 0.2 × fuzzy_ratio` cho mỗi câu mẫu trong kb.json.
- **FR-004**: Hệ thống PHẢI trả `type: "answer"` khi hybrid score ≥ 0.78, `type: "suggest"` khi 0.55–0.78, và `type: "unknown"` khi < 0.55.
- **FR-005**: Hệ thống PHẢI gọi LLM sửa chính tả (chỉ với system prompt cố định, không sinh câu trả lời) duy nhất ở vùng MID (0.55–0.78), rồi embed lại và chấm điểm thêm một lần.
- **FR-006**: Hệ thống PHẢI lưu embedding của toàn bộ kb.json vào cache khi khởi động và tự build lại khi `kb.json` thay đổi (dựa trên hash file).
- **FR-007**: Hệ thống PHẢI dùng LRU cache cho các câu hỏi đã xử lý để trả lời tức thì khi gặp lại.
- **FR-008**: Câu trả lời dạng danh sách PHẢI được lưu trong `kb.json` dưới dạng mảng và trả về trong trường `answer_bullets`.
- **FR-009**: Hệ thống PHẢI giới hạn input tối đa 200 ký tự và từ chối input rỗng (HTTP 422).
- **FR-010**: Hệ thống PHẢI có rate limiting theo IP; vượt ngưỡng → HTTP 429.
- **FR-011**: Hệ thống PHẢI warm-up khi khởi động (1 lần embed + 1 lần Qwen) để preload model vào bộ nhớ Ollama.
- **FR-012**: Hệ thống PHẢI lọc từ tục tĩu và trả `type: "unknown"` lịch sự, không xử lý thêm.

### Key Entities

- **KnowledgeItem**: Đơn vị kiến thức gồm `id`, `topic`, `questions` (mảng cách hỏi), `answer` (chuỗi hoặc mảng bullet).
- **EmbeddingCache**: Ánh xạ từ hash của `kb.json` → ma trận embedding được tính sẵn, lưu ra file.
- **QueryCache**: LRU map từ chuỗi câu hỏi đã chuẩn hoá → response đã tính; giới hạn kích thước (ví dụ 512 mục).
- **ChatRequest**: `{ message: string }` — tối đa 200 ký tự, không rỗng.
- **ChatResponse**: Union của `AnswerResponse | SuggestResponse | UnknownResponse`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Câu khớp rõ (score ≥ 0.78 không cần Qwen) trả lời trong < 100 ms ở điều kiện bình thường (Ollama đang chạy, cache đã warm).
- **SC-002**: Câu cần sửa chính tả (vùng MID, có gọi Qwen) trả lời trong < 1 s.
- **SC-003**: ≥ 95% câu hỏi trong bộ test 30–50 câu (đúng, sai chính tả, không dấu, teencode) nhận được `type` đúng (answer/suggest/unknown).
- **SC-004**: 0% câu trả lời chứa nội dung do LLM tự sinh (mọi nội dung đều lấy từ kb.json).
- **SC-005**: Khởi động server lần đầu (build embedding) < 30 s với kb.json ≤ 200 mục.
- **SC-006**: Khởi động lần sau (load cache) < 5 s.
- **SC-007**: API chịu được ≥ 20 request đồng thời mà không trả lỗi 5xx.

---

## Assumptions

- Ollama đang chạy cục bộ (hoặc trong container cùng mạng) với `bge-m3` và `qwen2.5` (1.5b hoặc 3b) đã được pull.
- `kb.json` nằm ở đường dẫn cố định, do chủ nhân chatbot tự biên soạn; không có giao diện admin để chỉnh sửa qua UI.
- Chatbox UI đã tồn tại và chỉ cần giao tiếp qua `POST /chat`; frontend không phải phạm vi của feature này.
- Số lượng mục trong kb.json ≤ 1 000 → numpy đủ dùng cho cosine similarity; không cần vector DB.
- Người dùng duy nhất là người xem hồ sơ của chủ nhân chatbot; không có phân quyền hay đăng nhập.
- Dữ liệu không nhạy cảm; không cần mã hoá lưu trữ.
- Chỉ hỗ trợ tiếng Việt và tiếng Anh cơ bản; không yêu cầu đa ngôn ngữ sâu hơn.
- Triển khai đơn máy; không yêu cầu scale ngang ở giai đoạn này.
