# Feature Specification: Luôn gợi ý & nạp tài liệu đa định dạng

**Feature Branch**: `006-tiered-suggest-ingest`

**Created**: 2026-11-12

**Status**: Draft

**Input**: User description: "Plan v2: Xử lý text – luôn gợi ý, nạp được PDF / XLSX / CSV / DOCX. Bỏ câu 'tôi không biết', thay bằng thang gợi ý nhiều bậc; gợi ý khi câu mơ hồ; nạp tài liệu offline; ưu tiên tốc độ, không gọi LLM trên đường chính."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mọi câu hỏi đều có bước tiếp theo (Priority: P1)

Người dùng nhập bất kỳ câu gì — khớp rõ, mơ hồ, lạc đề, thậm chí gõ vô nghĩa — và luôn nhận được một phản hồi hữu ích kèm ít nhất một lựa chọn có thể bấm. Chatbot không bao giờ kết thúc bằng câu "mình không biết".

**Why this priority**: Đây là thay đổi cốt lõi của feature; loại bỏ ngõ cụt là điều kiện để mọi luồng khác có giá trị. Nếu chỉ làm được một việc, đây là việc đó.

**Independent Test**: Gửi lần lượt một câu khớp rõ, một câu mơ hồ ("mục tiêu"), một câu lạc đề ("hôm nay ăn gì") và chuỗi vô nghĩa ("asdf") → mỗi phản hồi thuộc một trong ba loại `answer` / `suggest` / `clarify`, và mọi phản hồi không phải `answer` đều chứa ít nhất một nút hành động.

**Acceptance Scenarios**:

1. **Given** câu hỏi khớp rõ với một mục kiến thức, **When** người dùng gửi câu hỏi, **Then** nhận `type: "answer"` với nội dung trả lời (gạch đầu dòng hoặc đoạn văn) và điểm tin cậy.
2. **Given** câu hỏi mơ hồ hoặc chỉ có một từ khoá, **When** người dùng gửi câu hỏi, **Then** nhận `type: "suggest"` với 2–4 câu hỏi đầy đủ kèm điểm, và luôn có nút "Câu hỏi khác".
3. **Given** câu hỏi không khớp mục nào và không có đoạn tài liệu phù hợp, **When** người dùng gửi câu hỏi, **Then** nhận `type: "clarify"` với menu chủ đề, câu hỏi mẫu và nút "Hỏi lại cách khác".
4. **Given** chuỗi vô nghĩa, **When** người dùng gửi, **Then** nhận `type: "clarify"` — tuyệt đối không trả `unknown` và không có câu "không biết".

---

### User Story 2 - Làm rõ theo cấp, không lặp lại (Priority: P2)

Người dùng gõ một từ khoá ngắn như "mục tiêu" và thấy vài gợi ý chưa đúng ý. Họ bấm "Câu hỏi khác" và được dẫn dần: chọn chủ đề → xem các câu hỏi chưa từng hiển thị trong chủ đề đó → cuối cùng là lời mời mô tả tự do kèm ví dụ. Không gợi ý nào bị lặp lại trong cùng phiên.

**Why this priority**: Biến phản hồi "gợi ý" thành một cuộc hội thoại có đường đi rõ ràng thay vì một danh sách chết. Phụ thuộc trực tiếp vào User Story 1.

**Independent Test**: Từ câu "mục tiêu", bấm "Câu hỏi khác" ba lần liên tiếp → lần 1 ra menu chủ đề, chọn một chủ đề ra câu hỏi chưa hiển thị, cạn câu trong chủ đề thì ra lời mời mô tả tự do với ví dụ; không câu nào lặp lại.

**Acceptance Scenarios**:

1. **Given** đang ở phản hồi `suggest`, **When** người dùng bấm "Câu hỏi khác", **Then** nhận `clarify` cấp 1 với danh sách chủ đề có sẵn (tối thiểu 3 chủ đề).
2. **Given** đang ở `clarify` cấp 1, **When** người dùng chọn một chủ đề, **Then** nhận `suggest` gồm các câu hỏi thuộc chủ đề đó **chưa** hiển thị trong phiên.
3. **Given** các câu hỏi của chủ đề đã hiển thị hết, **When** người dùng tiếp tục bấm "Câu hỏi khác", **Then** nhận `clarify` cấp 3 với lời mời mô tả cụ thể hơn và 2–3 ví dụ.
4. **Given** một phiên mới, **When** người dùng hỏi lại cùng từ khoá, **Then** các gợi ý đã hiển thị ở phiên trước được phép xuất hiện lại.

---

### User Story 3 - Nạp tài liệu PDF / DOCX / XLSX / CSV (Priority: P3)

Chủ chatbot bỏ các tệp hồ sơ (CV PDF, tài liệu Word, bảng Excel, tệp CSV) vào một thư mục và chạy lệnh nạp. Sau đó người xem hỏi nội dung nằm trong các tệp này và nhận câu trả lời trích trực tiếp từ tài liệu, kèm nguồn chính xác (tệp + trang/sheet/dòng).

**Why this priority**: Mở rộng tri thức ngoài danh sách Q&A soạn sẵn, nhưng đứng sau trải nghiệm "luôn gợi ý" vì cần offline ingest và dữ liệu thật.

**Independent Test**: Chuẩn bị 4 tệp mẫu (PDF, DOCX, XLSX, CSV), nạp cả thư mục, rồi hỏi 3 câu có đáp án nằm trong từng tệp → cả 12 câu trả đúng nội dung và hiện đúng nguồn.

**Acceptance Scenarios**:

1. **Given** một thư mục chứa tệp PDF/DOCX/XLSX/CSV, **When** chủ chatbot chạy lệnh nạp thư mục, **Then** hệ thống báo số tệp đã nạp, số đoạn đã tạo và lỗi (nếu có) cho từng tệp.
2. **Given** tài liệu đã nạp, **When** người dùng hỏi một câu có đáp án trong tài liệu, **Then** nhận `type: "answer"` với 3–5 câu trích phù hợp nhất và nguồn dạng `tên-tệp, trang N` hoặc `tên-tệp, sheet X, dòng A–B`.
3. **Given** một tệp đã nạp không thay đổi nội dung, **When** chạy nạp lại, **Then** tệp đó được bỏ qua và không tạo lại dữ liệu tìm kiếm cho nó.
4. **Given** một tệp đã nạp được sửa đổi, **When** chạy nạp lại, **Then** chỉ các đoạn mới hoặc thay đổi của tệp đó được xử lý lại; các đoạn không đổi được giữ nguyên.
5. **Given** tài liệu đã nạp, **When** chủ chatbot chạy lệnh liệt kê, **Then** thấy tên từng tệp đã nạp kèm số đoạn tương ứng.
6. **Given** tệp đã nạp, **When** chủ chatbot yêu cầu xoá tệp, **Then** toàn bộ nội dung của tệp đó không còn được dùng để trả lời.

---

### User Story 4 - Trả lời nhanh, không phụ thuộc LLM (Priority: P4)

Người dùng nhận phản hồi gần như tức thì. Câu trả lời được lấy nguyên văn từ tri thức đã nạp và cắt thành câu/ý phù hợp, không do mô hình ngôn ngữ tự sinh. Tóm tắt bằng LLM là tuỳ chọn và mặc định tắt.

**Why this priority**: Tốc độ là yêu cầu xuyên suốt; nếu phản hồi chậm hoặc nội dung bị "ảo giác", các giá trị ở trên mất đi.

**Independent Test**: Đo thời gian phản hồi cho 3 nhóm (khớp rõ, gợi ý, trả lời từ tài liệu) trên ít nhất 50 lượt, không bật tóm tắt LLM → p50 dưới 300 ms và p95 dưới 500 ms; không có nội dung nào do LLM sinh.

**Acceptance Scenarios**:

1. **Given** hệ thống đã khởi động và mô hình embedding đã sẵn sàng, **When** người dùng gửi câu khớp rõ, **Then** phản hồi trả về trong dưới 300 ms ở p50.
2. **Given** tóm tắt LLM đang tắt, **When** người dùng hỏi bất kỳ câu nào, **Then** toàn bộ nội dung trả lời là trích từ tri thức/tài liệu, không có câu do LLM sinh.
3. **Given** tính năng tìm ngữ nghĩa tạm thời không khả dụng, **When** người dùng gửi câu hỏi, **Then** hệ thống vẫn trả gợi ý theo từ khoá hoặc menu chủ đề — không trả lỗi và không rơi về "không biết".

---

### Edge Cases

- Câu hỏi rỗng hoặc chỉ có ký tự đặc biệt: bị từ chối ở tầng kiểm tra đầu vào với thông báo rõ ràng (không tạo phản hồi `clarify`).
- Câu ≤ 3 từ nhưng khớp rất cao: vẫn ưu tiên gợi ý nếu có từ 2 ứng viên trở lên, để người dùng chọn đúng ý.
- Điểm top 1 và top 2 chênh nhau dưới 0.05: coi là mơ hồ dù top 1 cao.
- Không có đoạn tài liệu nào đạt ngưỡng khớp: chuyển sang `clarify`, không trả đoạn tài liệu yếu.
- Tệp PDF bị mã hoá/mật khẩu, tệp hỏng, hoặc định dạng không hỗ trợ: ghi nhận lỗi cho tệp đó, các tệp khác vẫn nạp bình thường; chỉ mục hiện có không bị hỏng.
- PDF scan không có lớp văn bản: báo "không trích được văn bản"; OCR là tuỳ chọn ngoài phạm vi v1.
- Bảng tính có sheet rỗng, dòng toàn ô trống hoặc cột không tên: bỏ qua dòng rỗng và dùng tên cột thay thế rõ ràng.
- CSV sai bảng mã: thử các bảng mã phổ biến cho tiếng Việt; nếu vẫn lỗi thì báo lỗi kèm tên tệp, không nạp dữ liệu rác.
- Tệp vượt giới hạn kích thước: từ chối kèm thông báo, không làm treo tiến trình nạp.
- Nhiều tệp trùng nội dung hoặc nhiều đoạn trùng nhau: khử trùng lặp khi gợi ý và khi trả lời.
- Người dùng bấm liên tiếp "Câu hỏi khác" đến khi cạn gợi ý: luôn dừng ở cấp mô tả tự do, không lặp vô hạn.
- Hai phiên người dùng cùng lúc: trạng thái hiển thị của phiên này không ảnh hưởng phiên kia.
- Câu hỏi dạng tính toán/tổng hợp trên bảng (ví dụ "tổng doanh thu"): chưa hỗ trợ trong v1; trả về đoạn dữ liệu liên quan hoặc `clarify` thay vì bịa số.

## Requirements *(mandatory)*

### Functional Requirements

**Thang xử lý & loại phản hồi**

- **FR-001**: Hệ thống PHẢI trả về đúng một trong ba loại phản hồi: `answer`, `suggest`, `clarify`. Hệ thống KHÔNG ĐƯỢC trả loại `unknown` và KHÔNG ĐƯỢC dùng câu "mình không biết"/"chưa biết" làm kết thúc.
- **FR-002**: Mọi phản hồi `suggest` và `clarify` PHẢI chứa ít nhất một hành động bấm được (gợi ý câu hỏi, nút chủ đề, hoặc nút hỏi lại). Phản hồi `answer` PHẢI chứa nội dung trả lời và, nếu lấy từ tài liệu, nguồn trích dẫn.
- **FR-003**: Hệ thống PHẢI phân nhánh theo điểm khớp tổng hợp S: `S ≥ 0.78` → `answer`; `0.45 ≤ S < 0.78` → `suggest`; `S < 0.45` → tìm trong tài liệu. Ba ngưỡng này PHẢI cấu hình được mà không sửa mã.
- **FR-004**: Khi `S < 0.45`, hệ thống PHẢI tìm trong tài liệu đã nạp; nếu có đoạn đạt ngưỡng tài liệu (mặc định 0.55) thì trả `answer` kèm nguồn; nếu không thì trả `clarify`.
- **FR-005**: Hệ thống PHẢI coi câu hỏi là mơ hồ nếu thoả một trong các điều kiện: tối đa 3 từ sau tiền xử lý; chênh lệch điểm top 1 và top 2 nhỏ hơn 0.05; hoặc điểm rơi vào vùng gợi ý 0.45–0.78.
- **FR-006**: Hệ thống PHẢI áp dụng cùng một quy trình chuẩn hoá cho câu hỏi và nội dung tài liệu, bao gồm Unicode NFC, chữ thường, bỏ dấu, teencode và khớp mờ, để câu không dấu/viết tắt vẫn khớp.

**Sinh gợi ý & làm rõ**

- **FR-007**: Gợi ý PHẢI được tạo bằng cách kết hợp so khớp chủ đề/từ khoá của mục tri thức với so khớp ngữ nghĩa các câu hỏi mẫu, sau đó khử trùng và chọn 3–4 câu phù hợp nhất; không gọi LLM.
- **FR-008**: Mỗi gợi ý PHẢI gồm mã định danh, câu hỏi đầy đủ và điểm tin cậy; danh sách gợi ý PHẢI kèm hành động "Câu hỏi khác".
- **FR-009**: Phản hồi `clarify` cấp 1 PHẢI liệt kê tối thiểu 3 chủ đề lấy từ tri thức và tài liệu đã nạp, kèm 2–3 câu hỏi mẫu và hành động "Hỏi lại cách khác".
- **FR-010**: Khi người dùng chọn một chủ đề ở cấp 1, hệ thống PHẢI trả các câu hỏi thuộc chủ đề đó mà chưa hiển thị trong phiên; khi đã cạn, PHẢI chuyển sang cấp 3 (mời mô tả tự do kèm ví dụ).
- **FR-011**: Hệ thống PHẢI lưu trạng thái mỗi phiên gồm danh sách mã gợi ý đã hiển thị, câu hỏi gần nhất và cấp làm rõ hiện tại; trạng thái này PHẢI tách biệt giữa các phiên và được đặt lại khi bắt đầu phiên mới.
- **FR-012**: Hệ thống PHẢI không gợi ý lặp lại một câu hỏi đã hiển thị trong cùng phiên cho đến khi danh sách của chủ đề đó cạn.

**Nạp tài liệu**

- **FR-013**: Hệ thống PHẢI hỗ trợ nạp offline từng tệp hoặc cả thư mục cho các định dạng PDF (có lớp văn bản), DOCX, XLSX, CSV, TXT và MD. DOC cũ PHẢI được hỗ trợ khi có công cụ chuyển đổi sẵn; nếu không, báo lỗi rõ ràng.
- **FR-014**: Mỗi tài liệu PHẢI được chia thành các đoạn có siêu dữ liệu: mã đoạn, tên tệp, loại tệp, vị trí (trang/sheet/dòng), tiêu đề mục, nội dung văn bản và dấu vân tay nội dung.
- **FR-015**: Việc chia đoạn PHẢI theo cấu trúc: PDF theo trang và đoạn; DOCX theo tiêu đề mục (cắt nhỏ nếu quá dài); bảng tính chuyển mỗi dòng thành một câu có tên cột. Độ dài đoạn mục tiêu 300–500 ký tự, chồng lấn khoảng 50 ký tự.
- **FR-016**: Mỗi đoạn PHẢI được gắn ngữ cảnh ở đầu đoạn (tên tệp > tiêu đề mục > nội dung) trước khi lập chỉ mục để tăng độ chính xác tìm kiếm.
- **FR-017**: Hệ thống PHẢI lưu chỉ mục tìm kiếm và siêu dữ liệu đoạn bền vững, nạp sẵn vào bộ nhớ khi khởi động; khi người dùng hỏi chỉ xử lý câu hỏi, không xử lý lại tài liệu.
- **FR-018**: Hệ thống PHẢI bỏ qua tệp không thay đổi dựa trên dấu vân tay nội dung; với tệp thay đổi, chỉ xử lý lại các đoạn mới hoặc thay đổi. Khi xoá tệp, toàn bộ đoạn của tệp đó PHẢI bị loại khỏi chỉ mục.
- **FR-019**: Lệnh vận hành PHẢI hỗ trợ nạp thư mục, nạp một tệp, liệt kê tệp đã nạp kèm số đoạn, và xoá một tệp khỏi chỉ mục.
- **FR-020**: Kết quả nạp PHẢI báo rõ số tệp đã thêm, cập nhật, bỏ qua và lỗi; lỗi ở một tệp không được làm hỏng chỉ mục hiện có.

**Trả lời từ tài liệu & tốc độ**

- **FR-021**: Câu trả lời từ tài liệu PHẢI mang tính trích xuất: lấy 1–2 đoạn khớp nhất, chọn 3–5 câu liên quan nhất, hiển thị dạng gạch đầu dòng kèm nguồn chính xác. Hệ thống KHÔNG ĐƯỢC tự sinh nội dung bằng LLM trên đường xử lý chính.
- **FR-022**: Tóm tắt bằng LLM PHẢI là tuỳ chọn, mặc định tắt; khi bật, phản hồi phải giới hạn ngắn (không quá 120 token) và không được chặn các phản hồi không dùng LLM.
- **FR-023**: Hệ thống PHẢI đáp ứng ngân sách: tiền xử lý dưới 1 ms, chuẩn bị câu hỏi 50–200 ms trên máy chạy tiêu chuẩn, tra cứu dưới 20 ms, dựng gợi ý dưới 5 ms; tổng thời gian phản hồi không dùng LLM p50 dưới 300 ms và p95 dưới 500 ms.
- **FR-024**: Khi tìm ngữ nghĩa hoặc chỉ mục tạm thời không khả dụng, hệ thống PHẢI hạ cấp sang gợi ý theo từ khoá và `clarify`, không trả lỗi hệ thống và không trả `unknown`.
- **FR-025**: Hệ thống PHẢI khử trùng lặp gợi ý và đoạn trích (theo mã mục/đoạn và theo nội dung gần giống) trước khi hiển thị.

### Key Entities

- **KnowledgeItem** (mục tri thức soạn sẵn): mã, chủ đề, từ khoá, danh sách câu hỏi mẫu, câu trả lời dạng đoạn hoặc gạch đầu dòng.
- **Document**: tệp đã nạp — tên, loại, dấu vân tay nội dung, trạng thái nạp, thời điểm nạp, số đoạn.
- **Chunk** (đoạn tài liệu): mã, thuộc tệp nào, loại, vị trí (trang/sheet/dòng), tiêu đề mục, nội dung, dấu vân tay.
- **MatchCandidate**: ứng viên khớp — tham chiếu mục/đoạn, điểm tổng hợp, điểm thành phần, nguồn gốc (tri thức hay tài liệu).
- **ChatResponse**: một trong ba dạng:
  - `answer`: nội dung trả lời (gạch đầu dòng/đoạn), điểm, nguồn.
  - `suggest`: thông điệp dẫn dắt, danh sách gợi ý (mã, câu hỏi, điểm), hành động "Câu hỏi khác".
  - `clarify`: thông điệp, danh sách chủ đề, câu hỏi mẫu, hành động "Hỏi lại cách khác".
- **SessionState**: trạng thái mỗi phiên — danh sách mã gợi ý đã hiển thị, câu hỏi gần nhất, cấp làm rõ hiện tại (1–3).
- **IngestSummary**: kết quả một lần nạp — số tệp thêm/cập nhật/bỏ qua/lỗi kèm chi tiết từng tệp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% đầu vào hợp lệ — bao gồm câu khớp rõ, câu mơ hồ, câu lạc đề và chuỗi vô nghĩa — nhận được phản hồi thuộc `answer`/`suggest`/`clarify`; 0% phản hồi là `unknown` hoặc chứa câu "không biết".
- **SC-002**: Với câu "mục tiêu", người dùng nhận tối thiểu 2 gợi ý câu hỏi đầy đủ và nút "Câu hỏi khác" trong dưới 300 ms ở p50.
- **SC-003**: 100% lần bấm "Câu hỏi khác" đưa người dùng tới menu chủ đề hoặc lời mời mô tả tự do, không bao giờ là ngõ cụt; không gợi ý nào lặp lại cho tới khi cạn danh sách của chủ đề.
- **SC-004**: Trong bộ kiểm thử mẫu, mỗi định dạng PDF/DOCX/XLSX/CSV đạt 3/3 câu hỏi có đáp án trong tệp được trả đúng nội dung; 100% câu trả lời từ tài liệu hiển thị nguồn khớp đúng vị trí thực tế.
- **SC-005**: Nạp lại một thư mục không thay đổi không tạo lại dữ liệu tìm kiếm cho bất kỳ tệp nào; khi một tệp thay đổi, số đoạn được xử lý lại không vượt quá số đoạn mới hoặc thay đổi của tệp đó.
- **SC-006**: p50 thời gian phản hồi dưới 300 ms và p95 dưới 500 ms khi tắt tóm tắt LLM, đo trên tối thiểu 50 lượt hỏi thuộc cả ba nhánh.
- **SC-007**: 0% nội dung trả lời do LLM sinh khi tắt tóm tắt LLM.
- **SC-008**: Tối thiểu 80% các truy vấn mơ hồ trong bộ kiểm thử (khoảng 25 câu ngắn/không dấu/teencode) có ít nhất một gợi ý đúng với ý định dự kiến.
- **SC-009**: 0% câu hỏi khớp rõ trước đây bị hồi quy sang `clarify` khi tri thức không đổi.
- **SC-010**: Khi tìm ngữ nghĩa không khả dụng, 100% lượt hỏi vẫn nhận phản hồi có thể bấm (không lỗi hệ thống, không `unknown`).

## Assumptions

- **Cách hiểu ưu tiên**: "ưu tiên đọc độ" trong yêu cầu gốc được hiểu là **ưu tiên tốc độ**. Nếu thực ra là ưu tiên độ chính xác, chỉ cần nới ngân sách thời gian ở FR-023/SC-006.
- **Nền tảng hiện có**: Feature kế thừa chatbot giới thiệu bản thân và kho tri thức soạn sẵn hiện có (spec 004, 005); nạp tài liệu là phần bổ sung, không thay thế kho tri thức soạn sẵn.
- **Từ khoá chủ đề**: Mỗi mục tri thức có `topic`; trường `keywords` là tuỳ chọn. Khi thiếu từ khoá, hệ thống suy ra từ chủ đề và các câu hỏi mẫu để tạo gợi ý.
- **Mô hình embedding**: Ollama với `bge-m3` khả dụng tại thời điểm chạy; dùng cùng mô hình cho tài liệu và câu hỏi. Nếu không khả dụng, áp dụng FR-024.
- **Người dùng & phiên**: Một người dùng duy nhất, không đăng nhập/phân quyền. Trạng thái phiên lưu trong bộ nhớ, không đồng bộ giữa thiết bị và không tồn tại sau khi phiên kết thúc/khởi động lại.
- **Ngôn ngữ**: Tiếng Việt là chính, có hỗ trợ tiếng Anh cơ bản; không yêu cầu đa ngôn ngữ sâu.
- **Ngưỡng mặc định**: 0.78 (trả lời), 0.45 (sàn gợi ý), 0.55 (khớp tài liệu), chênh lệch 0.05 (mơ hồ), 300–500 ký tự/đoạn với chồng lấn 50. Tất cả cấu hình được và có thể tinh chỉnh khi kiểm thử.
- **Giới hạn tệp**: Kích thước tệp tối đa mặc định 20 MB mỗi tệp, cấu hình được; vượt quá thì từ chối kèm thông báo.
- **Nội dung bảng**: Câu hỏi tính toán/tổng hợp trên bảng tính (sum, count, xếp hạng) chưa được hỗ trợ trong v1; sẽ dùng truy vấn có cấu trúc ở giai đoạn sau.
- **PDF scan**: OCR cho PDF không có lớp văn bản là tuỳ chọn ở giai đoạn sau; v1 báo không trích được văn bản.
- **Tóm tắt LLM**: Mặc định tắt; khi bật là tính năng phụ, không nằm trên đường phản hồi bắt buộc.
- **Không nhạy cảm**: Dữ liệu tài liệu không chứa thông tin cần mã hoá đặc biệt; không yêu cầu lưu trữ có kiểm soát truy cập.

### Out of Scope (v1)

- Giao diện quản trị để tải tài liệu qua trình duyệt; chỉ dùng lệnh vận hành offline.
- OCR PDF scan, truy vấn số liệu có cấu trúc và tóm tắt bằng LLM (giai đoạn sau).
- Theo dõi thư mục theo thời gian thực; nạp là thao tác chủ động.
- Lịch sử phiên bản nội dung tài liệu, đồng bộ nhiều người dùng, phân quyền.
- Thay đổi mô hình, thuật toán xếp hạng cốt lõi ngoài việc bổ sung nhánh tài liệu và loại phản hồi `clarify`.
