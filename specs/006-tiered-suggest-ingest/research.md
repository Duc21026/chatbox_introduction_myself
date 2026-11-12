# Research & Decisions: Luôn gợi ý & nạp tài liệu đa định dạng

**Feature**: `006-tiered-suggest-ingest` | **Date**: 2026-11-12

Tài liệu này chốt các quyết định kỹ thuật cho plan. Không còn mục `NEEDS CLARIFICATION`.

---

## D1. Thang quyết định 3 tầng và ngưỡng

**Decision**: Dùng đúng các ngưỡng trong spec làm mặc định, cấu hình qua env:

| Ngưỡng | Mặc định | Ý nghĩa |
|--------|----------|---------|
| `HIGH` | 0.78 | Trả lời trực tiếp từ KB |
| `SUGGEST_FLOOR` | 0.45 | Dưới ngưỡng này mới tìm tài liệu |
| `DOC` | 0.55 | Đoạn tài liệu đủ liên quan |
| `GAP` | 0.05 | Chênh top1–top2 bị coi là mơ hồ |

**Rationale**: Kế thừa ngưỡng 0.78/0.55 đang dùng ở 004; thêm sàn 0.45 để tách "gợi ý" khỏi "tìm tài liệu" theo spec. Điểm vẫn là hybrid `0.8*cosine + 0.2*WRatio` để không thay đổi hành vi khớp rõ đã kiểm thử. Vùng gợi ý mở rộng 0.45–0.78 (thay vì 0.55–0.78) để câu không dấu/teencode dễ được gợi ý hơn.

**Alternatives considered**:
- Giữ MID = 0.55 như 004: bỏ lỡ nhiều câu mơ hồ rơi vào 0.45–0.55.
- Dùng cosine thuần: bỏ tín hiệu khớp chuỗi tiếng Việt, tệ với teencode ngắn.

---

## D2. Một lần embed câu hỏi, chia sẻ cho KB và tài liệu

**Decision**: `assistant` chuẩn hoá câu hỏi một lần, gọi `kb_engine.evaluate(norm)` để lấy `query_vec` + ứng viên, rồi truyền cùng `query_vec` cho `doc_index.search()`. Không embed lại cho từng nhánh.

**Rationale**: Embedding là bước đắt nhất (50–200 ms). Tránh gọi 2 lần giúp giữ p95 < 500 ms. `kb_engine` hiện đã có `_embed_query`; refactor để trả vector thay vì chỉ điểm.

**Alternatives considered**:
- Mỗi module tự embed: đơn giản nhưng tăng gấp đôi độ trễ.
- Cache vector theo câu: hữu ích cho câu lặp, nhưng vẫn cần đường chính một lần embed.

---

## D3. Refactor `kb_engine` thành `evaluate()` + giữ `query()` tương thích

**Decision**: Thêm `evaluate(message)` trả:

```python
{
  "norm": str,
  "query_vec": np.ndarray | None,
  "top1": float,
  "top2": float,
  "candidates": [
      {"item_id", "topic", "question", "score", "source": "kb"}
  ],
  "answer_item": dict | None,
  "embeddings_ready": bool
}
```

`query()` cũ được giữ làm wrapper (dùng cho test/CLI cũ) nhưng `app.py` chuyển sang `assistant`.

**Rationale**: Cần top1/top2 và toàn bộ ứng viên cho luật mơ hồ và gợi ý; API cũ chỉ trả response cuối. Giữ wrapper tránh phá test 004.

**Alternatives considered**:
- Viết engine mới hoàn toàn: lặp code embed/score/cache.
- Trả response từ `kb_engine` rồi vá ở `app.py`: khó tách trách nhiệm và khó test.

---

## D4. Lưu chỉ mục tài liệu: JSON + NPZ + FAISS dựng lại trong RAM

**Decision**: Ba tệp trong `CHATBOT_DOC_INDEX_DIR`:

- `files.json`: trạng thái từng tệp.
- `chunks.json`: metadata từng đoạn + text gốc.
- `vectors.npz`: `chunk_ids` (unicode) + `vectors` (float32, đã chuẩn hoá L2).

Khi khởi động, đọc ba tệp và dựng `faiss.IndexFlatIP` + `IndexIDMap2` trong RAM. Khi ingest/xoá, cập nhật NPZ/JSON rồi dựng lại index (chỉ build, không embed lại).

**Rationale**: FAISS không lưu metadata và khó cập nhật từng phần; JSON/NPZ là nguồn sự thật dễ kiểm tra, dễ test, dễ rollback. Build lại index từ vài nghìn vector chỉ tốn mili-giây; chi phí thật nằm ở embedding. Dùng `IndexFlatIP` trên vector chuẩn hoá cho cosine chính xác. Tương thích stack `faiss-cpu` sẵn có.

**Alternatives considered**:
- Lưu `index.faiss` nhị phân: khó đọc/kiểm tra, dễ lệch với metadata sau khi sửa tay.
- Chỉ numpy: đủ nhanh cho quy mô nhỏ, nhưng rời khỏi kiến trúc FAISS hiện có; FAISS vẫn đáp ứng < 20 ms.
- Vector DB mới (Qdrant/Chroma): thêm service, trái YAGNI.

---

## D5. Thư viện trích PDF: pypdf trước, PyMuPDF là phương án dự phòng

**Decision**: Dùng `pypdf` (đã có trong requirements) theo từng trang. Nếu chất lượng trích tiếng Việt kém hoặc cần bảng, ghi nhận và cân nhắc thêm `PyMuPDF` ở giai đoạn sau; không thêm dependency trong v1.

**Rationale**: Tránh dependency nặng/Giấy phép AGPL của PyMuPDF; ingest là offline nên tốc độ không phải yếu tố quyết định. `pypdf` đã được dùng ở 002 nên không tăng bề mặt cài đặt.

**Alternatives considered**:
- PyMuPDF: nhanh và chất lượng cao hơn, nhưng thêm dependency + AGPL.
- pdfplumber: tốt cho bảng, chậm hơn và cũng là dependency mới.
- OCR mặc định: quá chậm, ngoài phạm vi v1.

---

## D6. Loader theo định dạng

**Decision**:

| Định dạng | Cách trích | Metadata |
|---|---|---|
| PDF | `pypdf`, từng trang; trang rỗng → đánh dấu scan | `page` (1-based) |
| DOCX | `python-docx`, paragraph + bảng; heading `Heading 1..6` | `heading` |
| DOC cũ | `libreoffice --headless --convert-to docx` nếu có; không có → lỗi rõ | `heading` |
| XLSX | `pandas.read_excel(sheet_name=None)`, tất cả sheet | `sheet`, `row_start`, `row_end` |
| CSV | `pandas.read_csv`; thử `utf-8-sig`, `utf-8`, `cp1258`, `latin-1` | `sheet = "(csv)"`, dòng |
| TXT/MD | UTF-8; MD chia theo heading `#` | `heading` |

**Rationale**: Tận dụng dependency sẵn có; metadata đủ để trích dẫn chính xác. XLSX nhiều sheet là điểm yếu của `documents.py` hiện tại (chỉ đọc sheet đầu), nên loader mới xử lý riêng thay vì sửa hành vi 002.

**Alternatives considered**:
- Sửa `documents.extract_segments`: rủi ro phá 002/legacy; dùng module mới.
- `charset-normalizer`: thêm dependency; danh sách fallback thủ công đủ cho tiếng Việt phổ biến.

---

## D7. Chunking theo cấu trúc, 500/50, có tiền tố ngữ cảnh

**Decision**: Mỗi block được chia bằng `RecursiveCharacterTextSplitter` (đã có) với `chunk_size=500`, `overlap=50`; trước khi embed, ghép tiền tố:

```text
[CV.pdf > Kinh nghiệm > trang 2]
<nội dung đoạn>
```

Lưu `text` gốc (không tiền tố) để hiển thị, `embed_text` (đã chuẩn hoá) để embed. Với bảng, mỗi dòng thành câu `Cột: giá trị; ...`, gộp 5–10 dòng ngắn đến ~500 ký tự.

**Rationale**: Tiền tố giúp đoạn tự mang ngữ cảnh khi embedding; giữ text gốc tránh hiển thị tiền tố rác. 500/50 khớp cấu hình dự án.

**Alternatives considered**:
- Chunk cố định theo ký tự: cắt giữa điều khoản/bảng.
- Chunk theo trang nguyên: quá dài, pha loãng embedding.

---

## D8. Tăng dần theo hash tệp + hash đoạn

**Decision**:

- `file_hash = sha256(toàn bộ bytes)`.
- Mỗi chunk có `content_hash = sha256(embed_text đã chuẩn hoá)`.
- Khi ingest: hash tệp trùng → `skipped` (không đọc lại nội dung).
- Tệp đổi → trích lại, tính hash từng đoạn; đoạn có hash đã tồn tại trong tệp đó → tái dùng vector; đoạn mới/đổi → embed; đoạn biến mất → xoá.
- Ghi atomic: tạo ba tệp tạm cùng thư mục, `fsync`, rồi `os.replace`.

**Rationale**: Đúng yêu cầu "chỉ embed phần đổi"; hash nội dung ổn định khi thứ tự đoạn đổi nhẹ. Ghi atomic tránh chỉ mục hỏng khi tiến trình bị dừng.

**Alternatives considered**:
- Chỉ hash tệp: tệp đổi 1 dòng vẫn embed lại toàn bộ.
- So sánh vị trí đoạn: dễ embed lại oan khi chèn/xoá dòng.

---

## D9. Trả lời trích xuất từ tài liệu

**Decision**: Lấy top 1–2 chunk ≥ 0.55; tách câu bằng regex `(?<=[.!?])\s+` và xuống dòng; chấm mỗi câu bằng `0.6*overlap_token + 0.4*fuzzy`; chọn 3–5 câu cao nhất nhưng giữ thứ tự xuất hiện; khử trùng; giới hạn ~600 ký tự. Trả `answer_bullets` + `source`/`sources`.

**Rationale**: Không gọi LLM; câu trích nguyên văn giảm ảo giác và giữ tốc độ. Chấm câu bằng overlap+fuzzy rẻ hơn embed từng câu (tránh N lần gọi Ollama).

**Alternatives considered**:
- Trả nguyên chunk: dài, nhiều thông tin nhiễu.
- Embed từng câu: chính xác hơn nhưng chậm, vi phạm ngân sách.

---

## D10. Sinh gợi ý không dùng LLM

**Decision**: Gộp hai nguồn:

1. **Keyword/topic**: token hoá câu hỏi; tính overlap với `topic` + câu hỏi mẫu (và `keywords` nếu có); cộng fuzzy `WRatio`; chuẩn hoá 0–1.
2. **Embedding**: dùng cùng `query_vec` và ma trận embedding câu hỏi KB, lấy top cosine.

Gộp theo `item_id`/câu hỏi, khử trùng, bỏ `shown_ids`, sắp theo `0.6*embedding + 0.4*keyword`, lấy tối đa 4, nhưng luôn trả ≥ 2 nếu có; nếu < 2 → `clarify`.

**Rationale**: Keyword bắt tín hiệu chủ đề khi câu rất ngắn ("mục tiêu"), embedding bắt cách diễn đạt khác. Không gọi LLM, đáp ứng < 5 ms sau khi có sẵn vector.

**Alternatives considered**:
- Chỉ embedding: câu một từ thường nhiễu.
- Chỉ fuzzy: bỏ lỡ câu diễn đạt lại.

---

## D11. Menu chủ đề & trạng thái phiên

**Decision**: `SessionStore` trong bộ nhớ, khoá theo `session_id`, TTL 30 phút, tối đa 1 000 phiên, `shown_ids` tối đa 200.

Topics = chủ đề duy nhất từ KB + topic tài liệu:

- KB: `topic` của từng `KnowledgeItem`.
- Tài liệu: heading đã trích; nếu không có heading, dùng tên tệp. Tối đa 8 topic, ưu tiên theo số câu/đoạn.
- Cấp 1 trả topics + 2–3 ví dụ + action `rephrase`.
- Cấp 2 trả câu hỏi chưa hiển thị trong topic; với topic tài liệu, dùng heading làm câu mẫu để tìm.
- Cấp 3 trả ví dụ mô tả tự do; không lặp vô hạn.

**Rationale**: Server giữ trạng thái để mọi client (web, CLI, curl) có cùng hành vi; không cần lưu DB vì phiên ngắn và đơn người dùng.

**Alternatives considered**:
- Client giữ `shown_ids`: dễ mất khi reload, khó tái sử dụng cho CLI.
- Lưu DB: quá mức cho quy mô này.

---

## D12. API transport: `/chat` là chuẩn, `/chat/stream` mở rộng

**Decision**: `/chat` trả đầy đủ `answer|suggest|clarify` + `session_id`. `/chat/stream`:

- Với `answer`: giữ `chunk` + `done` (tương thích).
- Với `suggest`/`clarify`: phát một event `{"type":"result","data":<response>}` rồi `done`.
- Không phát event `unknown`.

Frontend mặc định gọi `/chat` để nhận cấu trúc; stream chỉ dùng khi bật `VITE_CHAT_STREAM=true`. Nếu `/chat` lỗi mạng, không tự chuyển sang stream (tránh gửi trùng).

**Rationale**: Phản hồi chính không dùng LLM nên không cần stream; gọi một lần đơn giản hơn và đảm bảo nhận đủ nút. Vẫn giữ stream cho tương thích và tóm tắt LLM tuỳ chọn.

**Alternatives considered**:
- Chỉ dùng stream: phải thêm nhiều event và xử lý nút giữa luồng.
- Bỏ stream: phá client cũ và mất khả năng tóm tắt LLM.

---

## D13. Hạ cấp khi Ollama/chỉ mục không khả dụng

**Decision**: Nếu embed câu hỏi lỗi:

1. Dùng `normalize_query` + RapidFuzz trên câu hỏi KB để tạo `suggest`.
2. Nếu không đủ 2 gợi ý → `clarify` với topics KB (không cần embedding).
3. Không tìm tài liệu (không có vector câu hỏi); ghi log cảnh báo.
4. Không trả `unknown`, không trả 500 vì lỗi embedding.

**Rationale**: Đáp ứng SC-010 và nguyên tắc "luôn có thứ bấm được". Lỗi hạ tầng không được biến thành ngõ cụt.

**Alternatives considered**:
- Trả lỗi 503: vi phạm yêu cầu không ngõ cụt.
- Tự bịa câu trả lời bằng LLM: vi phạm "không gọi LLM trên đường chính".

---

## D14. Tóm tắt LLM tuỳ chọn

**Decision**: Cờ `ENABLE_LLM_SUMMARY=false`. Khi bật, chỉ dùng cho `answer` từ tài liệu, prompt chỉ chứa các câu đã trích, `num_predict ≤ 120`; nếu `/chat/stream` thì stream, nếu `/chat` thì trả một lần. Lỗi LLM → quay về câu trả lời trích xuất.

**Rationale**: Giữ mặc định nhanh/không ảo giác; người dùng có nhu cầu diễn đạt mượt có thể bật.

**Alternatives considered**:
- Bật mặc định: tăng p95 vượt ngân sách và rủi ro ảo giác.

---

## D15. Đo hiệu năng và kiểm thử không cần Ollama

**Decision**: Cho phép inject embedder:

- `doc_index` nhận `embedder` có `embed_documents`/`embed_query`.
- `kb_engine.evaluate` nhận `query_vec` tuỳ chọn.
- Test dùng embedder giả deterministic (như `FakeEmbeddings` hiện có).
- Benchmark p50/p95 dùng embedder giả để đo phần logic; đo thật với Ollama trong quickstart.

**Rationale**: CI không có Ollama vẫn chạy được; tách chi phí model khỏi chi phí thuật toán.

**Alternatives considered**:
- Mock toàn bộ module: khó phát hiện lỗi tích hợp.
- Bắt buộc Ollama: test chậm, dễ flaky.

---

## D16. Giới hạn & lỗi ingest

**Decision**:

- Mỗi tệp > `CHATBOT_DOC_MAX_BYTES` (20 MB) → lỗi, bỏ qua tệp.
- PDF không trích được chữ → lỗi `E_NO_TEXT` (gợi ý OCR ngoài phạm vi), không tạo chunk rỗng.
- Tệp hỏng/mã hoá/không hỗ trợ → lỗi riêng, không làm hỏng chỉ mục.
- CSV không decode được → lỗi, không nạp dữ liệu rác.
- Bảng tính không có header → dùng `col_1`, `col_2`…; bỏ dòng toàn rỗng.
- Trùng nội dung giữa các đoạn → khử trùng khi gợi ý/trả lời, nhưng vẫn giữ metadata nguồn.

**Rationale**: Lỗi một tệp không được ảnh hưởng tệp khác (FR-020); metadata nguồn phải chính xác.

**Alternatives considered**:
- Dừng cả lô khi một tệp lỗi: trái yêu cầu vận hành.
- Tự động OCR: quá chậm/không có dependency.

---

## D17. Giữ nội dung `kind: doc` của 005

**Decision**: Sau khi `doc_index` không có hit, `assistant` gọi `chatbox.retrieve_rag_documents()` để tìm trong chỉ mục RAG 005 (các bản ghi `kind: doc` trong `chatbot.txt`). Kết quả được trả lời trích xuất như tài liệu, không gọi LLM. FAISS 005 trả L2 distance trên vector đã chuẩn hoá, nên chuyển sang cosine xấp xỉ `max(0, 1 - d²/2)` trước khi so ngưỡng 0.55.

**Rationale**: 005 đã cho phép nội dung văn bản nằm trong `chatbot.txt` (`kind: doc`) và đưa vào RAG. Nếu 006 chỉ tìm `doc_index`, nội dung đó biến mất khỏi câu trả lời — vi phạm SC-009 (không hồi quy). Dùng lại chỉ mục FAISS sẵn có, không cần migrate dữ liệu hay nhân đôi embedding.

**Alternatives considered**:
- Nạp `chatbot.txt` doc records vào `doc_index`: phải đồng bộ khi tệp đổi, tạo khoá ảo và dễ trùng với tệp nhị phân đã migrate.
- Bỏ qua `kind: doc`: hồi quy hành vi 005.
- Gọi LLM trên kết quả RAG cũ: chậm và có thể ảo giác.

---

## Tổng hợp alternative bị loại

| Quyết định | Phương án bị loại | Lý do |
|---|---|---|
| pypdf | PyMuPDF | Dependency mới + AGPL; ingest offline nên không cần tốc độ PyMuPDF |
| JSON+NPZ+FAISS rebuild | Lưu index.faiss | Khó kiểm tra/khôi phục, dễ lệch metadata |
| Numpy thuần | FAISS | FAISS sẵn có, đáp ứng ngân sách và tương thích kiến trúc |
| `/chat` JSON | Chỉ stream | Khó render nút giữa luồng, không cần stream khi không LLM |
| Session server | Session client/DB | Cần nhất quán đa client, DB là quá mức |
| Keyword+embedding | Chỉ embedding/fuzzy | Câu ngắn cần tín hiệu chủ đề, câu diễn đạt lại cần embedding |
| RAG 005 fallback | Bỏ `kind: doc` | Mất nội dung đã migrate ở 005, hồi quy SC-009 |
