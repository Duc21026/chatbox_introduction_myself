# Feature Specification: Triển khai chatbot trên Vercel + Cloudflare Workers AI

**Feature Branch**: `008-vercel-cloudflare-deploy`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "dac ta lại spec/008 với task tui giao lúc vercal + cloudfalre" — tức kế hoạch triển khai Hướng 2: đưa chatbot lên mạng miễn phí, không cần thẻ, phục vụ 1–2 lượt truy cập mỗi ngày; chỉ làm phần triển khai, các tính năng khác vẫn theo `PLAN_MASTER.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Người xem dùng chatbot qua URL công khai (Priority: P1)

Một người xem mở URL công khai của chatbot, đặt câu hỏi về hồ sơ Văn Phú Đức và nhận câu trả lời đúng, đầy đủ, nhất quán với dữ liệu đã thống nhất. Khi hỏi mơ hồ hoặc ngoài chủ đề, người xem nhận gợi ý hoặc menu chủ đề thay vì câu trả lời cụt. Khi dịch vụ tạo vector tạm thời lỗi, chatbot vẫn phản hồi được.

**Why this priority**: Đây là toàn bộ giá trị của việc triển khai — người xem phải dùng được chatbot ở ngoài máy chủ phát triển.

**Independent Test**: Mở URL công khai trên một thiết bị khác, hỏi bộ câu mẫu T1–T3 và kiểm tra nội dung, gợi ý, và hành vi khi dịch vụ vector bị ngắt.

**Acceptance Scenarios**:

1. **Given** chatbot đã deploy, **When** người xem hỏi "GPA hiện tại?", **Then** nhận câu trả lời GPA 8.51/10 (≈ 8.5), 3.63/4.0, 87 tín chỉ, 24 học phần, xếp loại Giỏi.
2. **Given** chatbot đã deploy, **When** hỏi "điểm oop", **Then** nhận 6.9 (B, 4 tín chỉ) kèm tên môn đầy đủ.
3. **Given** chatbot đã deploy, **When** hỏi "mục tiêu", **Then** nhận ít nhất 2 gợi ý và nút "Câu hỏi khác".
4. **Given** chatbot đã deploy, **When** hỏi chuỗi vô nghĩa "asdf", **Then** nhận menu chủ đề và không có câu "không biết".
5. **Given** dịch vụ tạo vector không phản hồi hoặc báo lỗi, **When** người xem hỏi một câu hợp lệ, **Then** vẫn nhận gợi ý hoặc câu hỏi làm rõ trong thời gian chấp nhận được, không thấy lỗi máy chủ.

---

### User Story 2 - Chủ dự án triển khai miễn phí, không cần thẻ (Priority: P1)

Chủ dự án tạo tài khoản, cấu hình khóa truy cập dịch vụ vector, đẩy mã nguồn lên kho GitHub và nhận một URL công khai chạy được — toàn bộ trong hạn mức miễn phí, không nhập thẻ tín dụng và không phát sinh chi phí định kỳ.

**Why this priority**: Điều kiện tiên quyết để dự án tồn tại lâu dài với ngân sách 0.

**Independent Test**: Từ một máy sạch, làm theo hướng dẫn triển khai và xác nhận URL công khai trả lời đúng; kiểm tra không có yêu cầu thẻ hoặc gói trả phí nào.

**Acceptance Scenarios**:

1. **Given** chỉ có tài khoản miễn phí, **When** làm theo hướng dẫn triển khai, **Then** nhận URL HTTPS công khai hoạt động mà không cần thẻ.
2. **Given** khóa bí mật đã được đặt trong cấu hình môi trường, **When** kiểm tra mã nguồn, giao diện và phản hồi, **Then** không tìm thấy khóa bí mật ở bất kỳ đâu.
3. **Given** một IP gửi quá giới hạn cho phép, **When** tiếp tục gửi, **Then** các yêu cầu vượt bị chặn và hạn mức miễn phí của dịch vụ vector không bị đốt.
4. **Given** dự án chỉ dùng gói miễn phí, **When** kiểm tra bảng chi phí, **Then** chi phí định kỳ là 0 và không có cảnh báo thanh toán.

---

### User Story 3 - Chủ dự án cập nhật tri thức và deploy lại an toàn (Priority: P2)

Chủ dự án sửa hoặc thêm một mục trong tệp dữ liệu duy nhất, chạy kiểm tra dữ liệu, tạo lại chỉ mục vector, đẩy thay đổi lên kho mã và thấy nội dung mới được phục vụ mà không phải thao tác thủ công trên máy chủ. Nếu dữ liệu sai hoặc quên tạo lại vector, hệ thống cảnh báo rõ thay vì âm thầm trả lời bằng dữ liệu cũ.

**Why this priority**: Đây là quy trình vận hành thường xuyên; làm sai sẽ khiến chatbot trả lời lệch dữ liệu.

**Independent Test**: Sửa một mục hỏi-đáp, chạy đúng quy trình và kiểm tra câu trả lời mới; sau đó thử bỏ qua bước tạo vector và xác nhận có cảnh báo.

**Acceptance Scenarios**:

1. **Given** dữ liệu hiện tại hợp lệ, **When** sửa một mục và chạy kiểm tra → tạo vector → đẩy mã, **Then** câu trả lời mới xuất hiện và số vector khớp số mục hỏi-đáp.
2. **Given** dữ liệu mới không qua kiểm tra, **When** chạy quy trình, **Then** quy trình dừng trước bước tạo vector và không deploy dữ liệu lỗi.
3. **Given** dữ liệu đã sửa nhưng chưa tạo lại vector, **When** hệ thống khởi động hoặc kiểm tra sức khỏe, **Then** có cảnh báo chỉ mục đã cũ.
4. **Given** dữ liệu mới đã deploy, **When** hỏi câu liên quan, **Then** chỉ còn giá trị mới, không còn giá trị cũ.

---

### User Story 4 - Chủ dự án xử lý sự cố và quay lui (Priority: P2)

Khi dịch vụ vector hết hạn mức, khóa bị sai, bản deploy mới có lỗi hoặc khóa bí mật bị lộ, chủ dự án có cách phát hiện, khôi phục dịch vụ và quay về phiên bản ổn định mà không mất dữ liệu.

**Why this priority**: Sự cố hạ tầng là không tránh khỏi; khả năng quay lui quyết định dịch vụ có tiếp tục chạy hay không.

**Independent Test**: Cố tình làm sai khóa dịch vụ vector, kiểm tra fallback; sau đó rollback một bản deploy và xác nhận phiên bản trước phục vụ lại.

**Acceptance Scenarios**:

1. **Given** khóa dịch vụ vector sai hoặc hết hạn mức, **When** người xem đặt câu hỏi, **Then** chatbot trả gợi ý bằng khớp từ khoá/fuzzy và không trả lỗi máy chủ.
2. **Given** bản deploy mới trả lời sai hoặc lỗi, **When** chủ dự án chọn phiên bản trước, **Then** URL công khai phục vụ lại phiên bản ổn định.
3. **Given** khóa bí mật bị nghi lộ, **When** chủ dự án thu hồi và tạo khóa mới, **Then** dịch vụ hoạt động lại và khóa cũ không còn hiệu lực.
4. **Given** lần truy cập đầu tiên sau thời gian nghỉ dài, **When** trang tải, **Then** giao diện báo "đang khởi động" nếu chậm và phản hồi đầu tiên đến trong thời gian chấp nhận được.

---

### User Story 5 - Chủ dự án hiệu chỉnh chất lượng trả lời (Priority: P3)

Sau khi chuyển sang dịch vụ vector mới, chủ dự án dùng bộ câu hỏi thật để chọn lại các ngưỡng quyết định, bảo đảm câu đúng được trả lời, câu ngoài chủ đề bị đưa về gợi ý, và không dùng lại ngưỡng cũ vốn được tính cho hệ thống khác.

**Why this priority**: Ảnh hưởng trực tiếp đến độ chính xác nhưng có thể làm sau khi dịch vụ đã chạy được.

**Independent Test**: Chạy hiệu chỉnh trên 30–50 câu thật, áp dụng ngưỡng mới và kiểm tra tỷ lệ câu đúng/ngoài chủ đề.

**Acceptance Scenarios**:

1. **Given** bộ 30–50 câu đúng, sai chính tả, không dấu, viết tắt, mơ hồ, ngoài chủ đề, **When** chạy hiệu chỉnh, **Then** chọn được bộ ngưỡng mới và ghi lại lý do.
2. **Given** ngưỡng cũ của hệ thống trước, **When** triển khai hệ thống mới, **Then** ngưỡng cũ không được dùng nguyên trạng.
3. **Given** các kiểm tra nghiệm thu T1–T8, **When** chạy trước khi đưa lên production, **Then** tất cả đạt.

---

### Edge Cases

- Dịch vụ tạo vector trả lời chậm hơn timeout → fallback ngay, không giữ người xem chờ vô hạn.
- Dịch vụ tạo vector hết hạn mức giữa ngày → fallback cho đến khi hạn mức được đặt lại; không phát sinh chi phí.
- Câu hỏi rỗng, chỉ khoảng trắng, hoặc vượt 200 ký tự → thông báo lỗi rõ ràng, không gọi dịch vụ vector.
- Người dùng gửi liên tục từ một IP → bị giới hạn tần suất; các IP khác không bị ảnh hưởng.
- Gói triển khai vượt giới hạn kích thước do chỉ mục vector lớn → phát hiện trước khi deploy và báo cách xử lý.
- Tệp dữ liệu và chỉ mục vector không khớp → cảnh báo rõ; không âm thầm phục vụ chỉ mục cũ.
- Tạo vector thất bại giữa lô → không ghi tệp chỉ mục dở dang; giữ chỉ mục cũ còn hợp lệ.
- Hai lần deploy sát nhau → phiên bản mới nhất được phục vụ; có thể quay lại bất kỳ phiên bản nào còn lưu.
- Tên miền tùy chỉnh chưa cấu hình → vẫn dùng được tên miền mặc định của nền tảng.
- Hạn mức hoặc chính sách miễn phí thay đổi → có ghi chú kiểm tra lại và phương án dự phòng.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Hệ thống MUST được phục vụ tại một URL HTTPS công khai trên nền tảng Vercel, dùng giao diện hiện có và backend Python hiện có.
- **FR-002**: Giao diện MUST gọi điểm cuối chat cùng tên miền với trang, không yêu cầu cấu hình CORS.
- **FR-003**: Hệ thống MUST tạo vector cho câu hỏi bằng Cloudflare Workers AI với model `@cf/baai/bge-m3`.
- **FR-004**: Vector của toàn bộ mục hỏi-đáp MUST được tính sẵn thành tệp chỉ mục và so khớp trong bộ nhớ khi có yêu cầu; MUST NOT gọi dịch vụ vector cho toàn bộ kho dữ liệu mỗi lần hỏi.
- **FR-005**: Đường triển khai MUST NOT phụ thuộc Ollama, FAISS hoặc LangChain; các phụ thuộc này MUST được loại khỏi backend dùng để deploy.
- **FR-006**: Hệ thống MUST chạy trong hạn mức miễn phí của Vercel Hobby và Cloudflare Workers AI, MUST NOT yêu cầu thẻ tín dụng hoặc gói trả phí bắt buộc.
- **FR-007**: Khi dịch vụ tạo vector lỗi, timeout hoặc hết hạn mức, hệ thống MUST tự động chuyển sang khớp từ khoá + fuzzy trên dữ liệu đã chuẩn hoá.
- **FR-008**: Với câu hỏi hợp lệ, phản hồi MUST luôn thuộc một trong ba loại `answer`, `suggest`, `clarify`; MUST NOT trả lỗi máy chủ hoặc câu "không biết" chỉ vì lỗi dịch vụ vector.
- **FR-009**: Lời gọi dịch vụ tạo vector MUST có timeout ngắn và tối đa một lần thử lại; lỗi mạng MUST không chặn luồng trả lời.
- **FR-010**: Hợp đồng phản hồi hiện có MUST được giữ nguyên; chỉ được bổ sung trường `type` với ba giá trị trên.
- **FR-011**: Đầu vào MUST được giới hạn tối đa 200 ký tự; câu rỗng hoặc quá dài MUST trả lỗi 400 kèm thông báo rõ ràng.
- **FR-012**: Điểm cuối chat MUST có giới hạn tần suất theo IP (mặc định 30 yêu cầu/phút/IP) và MUST trả 429 khi vượt; quy tắc giới hạn MUST được xuất bản, không chỉ lưu nháp.
- **FR-013**: Hệ thống MUST cung cấp điểm cuối kiểm tra sức khỏe xác nhận chỉ mục vector đã nạp và còn khớp dấu vân tay dữ liệu; điểm cuối này MUST NOT gọi dịch vụ tạo vector.
- **FR-014**: Khóa bí mật MUST chỉ nằm trong biến môi trường của nền tảng triển khai và máy cục bộ; MUST NOT xuất hiện trong mã nguồn, giao diện, log hoặc phản hồi.
- **FR-015**: `.env` MUST nằm trong danh sách bỏ qua của Git; khi khóa bị lộ, quy trình MUST yêu cầu thu hồi và tạo khóa mới.
- **FR-016**: Hệ thống MUST cung cấp bước kiểm tra dữ liệu độc lập; dữ liệu MUST đạt 0 lỗi trước khi tạo chỉ mục hoặc deploy.
- **FR-017**: Quy trình tạo chỉ mục MUST đọc tệp dữ liệu duy nhất, gọi dịch vụ vector theo lô, và ghi kèm: mã mục, văn bản gốc, văn bản đã chuẩn hoá, loại, model, số chiều, và dấu vân tay của tệp dữ liệu.
- **FR-018**: Quy trình tạo chỉ mục MUST dùng đúng một hàm chuẩn hoá với lúc trả lời; MUST làm tròn vector để giữ kích thước tệp trong giới hạn triển khai.
- **FR-019**: Các ngưỡng quyết định (`HIGH`, `MID`, trọng số fuzzy) MUST được hiệu chỉnh lại trên vector của dịch vụ mới bằng dữ liệu thật; MUST NOT dùng nguyên ngưỡng cũ.
- **FR-020**: Triển khai MUST diễn ra bằng cách đẩy mã lên kho Git; nền tảng MUST tự tạo bản xem trước và bản production.
- **FR-021**: Mỗi bản deploy MUST có khả năng quay lui về phiên bản trước; nhánh chạy bằng Ollama MUST được giữ cho đến khi bản mới ổn định.
- **FR-022**: Trước khi đưa lên production, hệ thống MUST đạt bộ nghiệm thu T1–T8: dữ liệu mẫu đúng, gợi ý cho câu mơ hồ, menu chủ đề cho câu ngoài chủ đề, fallback khi dịch vụ vector lỗi, 400 cho đầu vào xấu, tốc độ đạt mục tiêu, giới hạn tần suất hoạt động, và không lộ bí mật.
- **FR-023**: Quy trình cập nhật dữ liệu MUST được ghi tài liệu gồm: sửa dữ liệu → kiểm tra → tạo lại chỉ mục → đẩy mã → hỏi thử; MUST nêu rõ bước tạo lại chỉ mục là bắt buộc.
- **FR-024**: Giao diện MUST thông báo công khai rằng câu hỏi được gửi tới Cloudflare để tạo vector.
- **FR-025**: Phiên bản này MUST chỉ hỗ trợ hỏi-đáp từ dữ liệu viết tay; tìm trong tài liệu dài (RAG/doc) nằm ngoài phạm vi.
- **FR-026**: Hệ thống MUST dùng tên miền mặc định của nền tảng; tên miền riêng là tùy chọn và không bắt buộc để đạt nghiệm thu.
- **FR-027**: Khi trang tải, giao diện MUST kiểm tra sức khỏe và hiển thị trạng thái "đang khởi động" nếu phản hồi chậm, thay vì để người xem gặp màn hình trống.
- **FR-028**: Hệ thống MUST ghi nhận lỗi dịch vụ vector, cảnh báo chỉ mục cũ và vượt giới hạn tần suất mà không ghi kèm khóa bí mật hay nội dung nhạy cảm.
- **FR-029**: Hồ sơ vận hành MUST ghi rõ giới hạn miễn phí đang dùng và nhắc kiểm tra lại chính sách trước khi bắt đầu.
- **FR-030**: Hệ thống MUST không tạo chi phí định kỳ trong điều kiện lưu lượng 1–2 lượt truy cập mỗi ngày.

### Key Entities *(include if feature involves data)*

- **Triển khai công khai**: URL HTTPS, môi trường production và xem trước, phiên bản đang phục vụ, khả năng quay lui.
- **Tệp dữ liệu nguồn**: nguồn tri thức viết tay duy nhất, dấu vân tay dùng để phát hiện thay đổi.
- **Chỉ mục vector**: tập vector tính sẵn cho các mục hỏi-đáp, kèm model, số chiều, văn bản gốc, văn bản chuẩn hoá và dấu vân tay dữ liệu nguồn.
- **Cấu hình dịch vụ vector**: mã tài khoản, khóa truy cập, hạn mức còn lại; khóa là bí mật.
- **Trạng thái sức khỏe**: chỉ mục đã nạp hay chưa, có khớp dữ liệu nguồn hay không, phiên bản đang chạy.
- **Quy tắc giới hạn tần suất**: ngưỡng theo IP và trạng thái đã xuất bản.
- **Bộ nghiệm thu**: các ca kiểm tra T1–T8 và kết quả từng lần deploy.
- **Bộ câu hỏi hiệu chỉnh**: 30–50 câu đúng/sai chính tả/không dấu/viết tắt/mơ hồ/ngoài chủ đề dùng để chọn ngưỡng.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% câu mẫu T1 (GPA 8.51/10 ≈ 8.5, 3.63/4.0, 87 tín chỉ, 24 học phần, điểm OOP 6.9, tốt nghiệp 8/2028) nhận câu trả lời đúng qua URL công khai.
- **SC-002**: 100% câu hỏi mơ hồ trong bộ mẫu nhận ít nhất 2 gợi ý và nút "Câu hỏi khác".
- **SC-003**: 100% câu hỏi ngoài chủ đề nhận menu chủ đề; 0 câu trả lời "không biết".
- **SC-004**: Khi dịch vụ tạo vector bị lỗi hoặc hết hạn mức, 100% câu hỏi hợp lệ vẫn nhận gợi ý/làm rõ; 0 lỗi máy chủ.
- **SC-005**: 100% câu rỗng hoặc vượt 200 ký tự nhận lỗi 400 kèm thông báo rõ ràng.
- **SC-006**: 95% câu hỏi nhận phản hồi trong 1,5 giây khi hệ thống đã sẵn sàng; lần đầu sau thời gian nghỉ dài nhận phản hồi trong 5 giây.
- **SC-007**: 100% yêu cầu vượt 30 yêu cầu/phút/IP bị chặn; trong bài kiểm tra spam, hạn mức miễn phí của dịch vụ vector không bị đốt hết.
- **SC-008**: 0 khóa bí mật xuất hiện trong mã nguồn, gói giao diện, log hoặc phản hồi qua kiểm tra tự động và thủ công.
- **SC-009**: Chủ dự án cập nhật một mục dữ liệu và thấy nội dung mới trên URL công khai trong vòng 10 phút chỉ bằng thao tác sửa tệp và đẩy mã.
- **SC-010**: 100% thay đổi dữ liệu không qua kiểm tra bị chặn trước khi tạo chỉ mục; 0 lần deploy âm thầm phục vụ chỉ mục cũ mà không có cảnh báo.
- **SC-011**: 100% hạng mục T1–T8 đạt trước khi promote production.
- **SC-012**: Chi phí định kỳ là 0 và không có bước nào yêu cầu nhập thẻ tín dụng.
- **SC-013**: Khi bản deploy mới có lỗi, quay lui về phiên bản trước hoàn tất trong 10 phút và URL công khai phục vụ lại bình thường.

## Assumptions

- Giới hạn miễn phí (10.000 neurons/ngày của Cloudflare; hàm Vercel ≤ 500 MB gói, ≤ 2 GB bộ nhớ, ≤ 300 giây; 3 rule firewall và 1 rule rate limit) đúng tại thời điểm 11/2026 và sẽ được kiểm tra lại trước khi bắt đầu.
- Lưu lượng mục tiêu là 1–2 lượt truy cập mỗi ngày; không cần mở rộng quy mô trong phạm vi này.
- Backend hiện tại dùng Flask và sẽ giữ nguyên framework, không viết lại.
- Giai đoạn này chỉ hỗ trợ hỏi-đáp (`qa`); tìm trong tài liệu dài (`doc`/RAG) và các tính năng trong `PLAN_MASTER.md` nằm ngoài phạm vi.
- Chủ dự án chấp nhận gửi câu hỏi tới Cloudflare để tạo vector và sẽ có thông báo công khai trên giao diện.
- Dùng tên miền mặc định `*.vercel.app`; tên miền riêng không bắt buộc.
- Chủ dự án có tài khoản GitHub, Cloudflare và Vercel miễn phí; không cần thẻ.
- Dữ liệu nguồn hiện tại (`chatbot.txt`) đã được thống nhất và có thể kiểm tra bằng công cụ kiểm tra dữ liệu.
- Gói Vercel Hobby dành cho dự án phi thương mại; nếu thương mại hóa phải đổi gói và cập nhật hiến pháp.
- Không có yêu cầu đăng nhập cho người xem; giao diện quản trị nội dung không thuộc phạm vi feature này.
- Hiến pháp dự án phiên bản 1.0.0 (một nguồn dữ liệu, miễn phí không thẻ, suy giảm êm, bảo mật, kiểm chứng trước deploy) áp dụng cho toàn bộ feature này.
