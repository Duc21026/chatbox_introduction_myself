# Phase 0 Research: Unified Text Knowledge Source

**Feature**: `005-unified-text-source` | **Date**: 2026-11-11

Tất cả điểm chưa rõ trong Technical Context đã được giải quyết. Không còn `NEEDS CLARIFICATION`.

## R-001 — Định dạng tệp hợp nhất

- **Decision**: Dùng văn bản thuần, line-oriented, với header `CHATBOT-SOURCE v1` và các khối `=== RECORD === ... === END ===` như đặc tả.
- **Rationale**: Đọc được bằng mắt, `diff` được, không cần thêm dependency, kiểm soát được multiline và thứ tự trường. Phù hợp với yêu cầu "một file text thôi".
- **Alternatives considered**:
  - YAML: dễ đọc nhưng cần PyYAML, dễ nhập nhằng indentation và block scalar.
  - JSON/JSONL: parse chắc chắn nhưng khó đọc, khó sửa tay, diff kém với nội dung nhiều dòng.
  - Markdown thuần: thân thiện nhưng không có grammar đủ chặt để phân biệt Q&A, bullet và nội dung RAG.

## R-002 — Kiến trúc parser

- **Decision**: Một parser một lượt (`backend/source_format.py`) tạo danh sách record bất biến, sau đó chạy toàn bộ validation trước khi sinh derived index. Không nạp từng phần.
- **Rationale**: Đáp ứng FR-003/FR-004 (fail-fast, báo số dòng, không nạp một phần). Parser thuần Python, dễ unit test, không phụ thuộc Ollama.
- **Alternatives considered**:
  - Parse trực tiếp vào KB/RAG trong lúc đọc: khó rollback khi lỗi giữa file.
  - Dùng regex toàn file: khó báo số dòng và dễ sai với nội dung nhiều dòng.
  - Thư viện parser bên ngoài: thêm dependency không cần thiết.

## R-003 — Ánh xạ record sang ba pipeline hiện có

- **Decision**:
  - `kind: qa` → `kb_engine` items, cặp `qa_pairs` cho khớp mờ, và tài liệu RAG (từ `content` nếu có, nếu không từ `topic + questions + answer/bullets`).
  - `kind: doc` → chỉ tài liệu RAG; không tham gia KB Engine hay gợi ý câu hỏi.
- **Rationale**: Giữ nguyên hành vi KB/threshold hiện tại, đồng thời thay thế `qa.txt` và `backend/data/` bằng cùng một nguồn. Tránh `doc` xuất hiện như một câu trả lời soạn sẵn.
- **Alternatives considered**:
  - Mọi record đều vào KB: `doc` không có câu hỏi nên không thể gợi ý, dễ gây nhiễu.
  - Tách hai file (qa + doc): trái yêu cầu một file duy nhất.

## R-004 — Cấu hình đường dẫn và tương thích ngược

- **Decision**: Thêm `CHATBOT_SOURCE_PATH` (mặc định `backend/data/chatbot.txt`). Đánh dấu deprecated `CHATBOT_DATA_DIR`, `CHATBOT_QA_PATH`, `CHATBOT_KB_PATH`; chỉ dùng chúng khi `CHATBOT_LEGACY_SOURCES=true`.
- **Rationale**: Một nguồn cấu hình duy nhất, dễ mount Docker; vẫn có đường lùi trong một phiên bản để migrate.
- **Alternatives considered**:
  - Bỏ ngay các biến cũ: phá vỡ deployment hiện tại.
  - Tự động fallback khi thiếu file mới: che giấu lỗi cấu hình, khó vận hành.

## R-005 — Phát hiện thay đổi và làm mới chỉ mục

- **Decision**: Tính signature gồm `mtime_ns`, kích thước, SHA-256 nội dung, embedding model, chunk size/overlap và phiên bản normalizer. Cache parsed source + derived index theo signature; request tiếp theo tự rebuild khi signature đổi.
- **Rationale**: Tái sử dụng mô hình `_source_signature` của `chatbox.get_db()` nhưng mở rộng cho một file. Tránh parse/embed lại mỗi request, vẫn đáp ứng FR-012.
- **Alternatives considered**:
  - Watch file bằng thread riêng: thêm đồng bộ, không cần cho quy mô hiện tại.
  - Chỉ dựa vào `mtime`: có thể bỏ sót khi nội dung đổi nhưng metadata không đổi.
  - Rebuild mỗi request: tốn CPU/embedding.

## R-006 — Chuẩn hoá văn bản

- **Decision**: Giữ `normalize_text()` cho tài liệu và `normalize_query()` cho câu hỏi. Thêm hằng `NORMALIZER_VERSION` để tham gia signature cache. Không đổi thuật toán trong feature này.
- **Rationale**: Tránh thay đổi hành vi trả lời ngoài phạm vi; cho phép vô hiệu cache khi quy tắc chuẩn hoá thay đổi sau này.
- **Alternatives considered**:
  - Hợp nhất hai hàm ngay: rủi ro regression retrieval, cần feature riêng.
  - Bỏ chuẩn hoá: phá vỡ hành vi hiện tại với teencode/không dấu.

## R-007 — Công cụ migrate và validate

- **Decision**: Mở rộng `backend/scripts/manage_docs.py` với hai subcommand:
  - `validate`: parse + validate tệp hợp nhất, không cần Ollama, exit code 0/2.
  - `migrate`: đọc `kb.json`, `qa.txt`, `backend/data/` bằng loader hiện có và ghi tệp hợp nhất, có `--force`.
- **Rationale**: Tận dụng CLI sẵn có, `sys.path` và quy ước vận hành của repo. Người dùng đã quen `manage_docs.py`.
- **Alternatives considered**:
  - Script riêng: tăng số entrypoint, trùng logic đọc dữ liệu.
  - Migrate tự động lúc khởi động: khó kiểm soát, dễ ghi đè nội dung.

## R-008 — Chiến lược kiểm thử

- **Decision**: Bổ sung pytest thuần cho parser/validator/mapping; test tích hợp API dùng monkeypatch để nạp source tạm; test CLI bằng `tmp_path`; smoke test Docker chỉ mount `chatbot.txt`.
- **Rationale**: Khớp cấu trúc `backend/tests` hiện có, không cần Ollama cho phần lớn test. Các test cần model tiếp tục được skip như hiện tại.
- **Alternatives considered**:
  - Chỉ test end-to-end với Ollama: chậm, phụ thuộc môi trường.
  - Test frontend: không cần vì feature thuần backend/dữ liệu.

## R-009 — Xử lý lỗi và rollback

- **Decision**: Khi khởi động, lỗi tệp làm dừng tiến trình với thông báo tiếng Việt. Khi đang chạy và phát hiện tệp đổi nhưng sai, giữ index cũ, log lỗi kèm số dòng; không thay thế trạng thái.
- **Rationale**: Đáp ứng yêu cầu an toàn dữ liệu và tránh chatbot trả lời bằng index rỗng ngoài ý muốn.
- **Alternatives considered**:
  - Luôn dừng server khi file đổi và sai: gián đoạn dịch vụ.
  - Nạp phần hợp lệ còn lại: che giấu lỗi, dễ mất dữ liệu.

## R-010 — Giới hạn và hiệu năng

- **Decision**: Tối đa 20 MB, mỗi câu hỏi 200 ký tự, `answer` 4.000 ký tự, bullet 300 ký tự, topic 120 ký tự. Mục tiêu parse + validate 1 MB dưới 1 giây.
- **Rationale**: Phù hợp chatbot giới thiệu cá nhân, chặn tệp quá lớn hoặc dữ liệu sai định dạng làm chậm khởi động.
- **Alternatives considered**:
  - Không giới hạn: dễ OOM khi chunking/embedding.
  - Giới hạn quá chặt: khó đưa CV/PDF dài vào `content`.
