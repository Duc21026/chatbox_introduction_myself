# Feature Specification: Thống nhất dữ liệu đầu vào + dữ liệu mở/động

**Feature Branch**: `007-unify-data-facts`

**Created**: 2026-11-12

**Status**: Draft

**Input**: User description: "Plan: Thống nhất dữ liệu đầu vào + dữ liệu mở/động (thêm mới dễ dàng)" — dùng toàn bộ đáp án đề xuất Q1–Q16 và sửa dữ liệu theo bản `CHATBOT-SOURCE v1` mới đã được duyệt. Cụ thể: bảng điểm PDF 07/11/2026 là nguồn sự thật duy nhất cho số liệu học tập; mỗi con số chỉ nằm một chỗ (facts + placeholder); hỏi-đáp từng môn và các số tổng hợp được sinh tự động từ danh sách môn học; chủ chatbot thêm mới dữ liệu mà không cần sửa code; mọi nguồn cũ mang số liệu lệch bị loại bỏ hoặc cách ly.

## Mục tiêu

- Một chatbot giới thiệu bản thân mà **mọi câu trả lời về cùng một sự kiện đều giống hệt nhau**, không còn chỗ nào trả số cũ (`8.30`, `62 tín chỉ`, `17 môn`, `3.7/4.0`).
- Số liệu học tập có đúng một nguồn: danh sách môn học; GPA, tổng tín chỉ, số học phần, môn cao nhất/thấp nhất, GPA xét chuyên ngành đều được **tính ra** chứ không gõ tay.
- Chủ chatbot có thể **thêm môn, sửa một giá trị, thêm chủ đề mới, thả tệp mới** mà không cần viết code; dữ liệu sai thì hệ thống **dừng và báo lỗi**, không bao giờ nạp một phần.
- Giọng văn, định dạng điểm, câu trả lời đồng nhất trên toàn bộ tri thức.

## Phạm vi

**Trong phạm vi**

- Chuẩn hoá toàn bộ giá trị hồ sơ theo bảng điểm PDF ngày 07/11/2026 (24 học phần, 87 tín chỉ, GPA 8.514 thang 10 / 3.634 thang 4, xếp loại Giỏi).
- Thêm loại bản ghi **fact** và cơ chế placeholder `{{id}}` trong câu trả lời.
- Danh sách môn học làm nguồn duy nhất cho điểm, tín chỉ, xét chuyên ngành và các số tổng hợp.
- Bí danh (viết tắt / tên gọi khác) cho môn và chủ đề.
- Trạng thái `active | archived` để gỡ nội dung mà không xoá.
- Ba cách thêm dữ liệu: sửa tệp viết tay, thả tệp vào thư mục chờ nạp, lệnh thêm nhanh.
- Kiểm tra hợp lệ tự động: placeholder không tồn tại, giá trị mâu thuẫn, dữ liệu rác (`nan`, `Unnamed`, `about:blank`, `[...]`, "(ví dụ)").
- Cập nhật `PLAN_MASTER.md` (mục 3, 5, 6) cho khớp thiết kế mới.

**Ngoài phạm vi**

- Trang quản trị giao diện web (làm sau).
- Sửa lại bảng điểm PDF gốc (giữ nguyên làm nguồn sự thật).
- Đồng bộ nhiều người cùng sửa, xác thực đăng nhập.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mọi câu hỏi về hồ sơ trả một giá trị duy nhất (Priority: P1)

Người xem hỏi bất kỳ câu nào về GPA, tín chỉ, số môn, ngành, tốt nghiệp, điểm từng môn — dù hỏi bằng từ khoá, tên đầy đủ hay viết tắt — và luôn nhận đúng một giá trị duy nhất khớp với bảng điểm PDF 07/11/2026, không còn giá trị cũ ở bất kỳ nguồn nào.

**Why this priority**: Toàn bộ mục đích của feature; hiện nay cùng một con số (GPA) sai khác ở ít nhất 6 chỗ nên câu trả lời phụ thuộc vào chỗ tìm được.

**Independent Test**: Quét toàn bộ nội dung chatbot phục vụ (câu trả lời soạn sẵn, mục do dữ liệu sinh, nội dung tìm kiếm ngữ nghĩa) → không còn chuỗi `8.30`, `8.3`, `62 tín chỉ`, `62 TC`, `17 môn`, `3.7/4.0`; hỏi "GPA bao nhiêu" và "điểm trung bình hiện tại" cùng trả về 8.51.

**Acceptance Scenarios**:

1. **Given** dữ liệu đã nạp, **When** người dùng hỏi "GPA của bạn là bao nhiêu?", **Then** nhận `type: "answer"` ghi GPA tích lũy 8.51 / 10 (≈ 8.5), thang 4: 3.63, 87 tín chỉ, 24 học phần, xếp loại Giỏi.
2. **Given** dữ liệu đã nạp, **When** hỏi "tổng tín chỉ bao nhiêu" hoặc "học bao nhiêu môn", **Then** lần lượt trả 87 tín chỉ và 24 học phần — các số này được tính ra từ danh sách môn, không gõ tay.
3. **Given** dữ liệu đã nạp, **When** hỏi "điểm oop", "điểm phương pháp lập trình hướng đối tượng" hay "điểm PPLT HĐT", **Then** đều trả 6.9 (B, 4 tín chỉ) với tên môn đầy đủ.
4. **Given** dữ liệu đã nạp, **When** hỏi "bạn học ngành gì?", **Then** trả ngành đào tạo Khoa học Máy tính và Khoa học Dữ liệu; hỏi "chuyên ngành dự kiến" trả Máy tính, Trí tuệ nhân tạo (AI), Kỹ thuật phần mềm.
5. **Given** dữ liệu đã nạp, **When** hỏi "khi nào tốt nghiệp?" hoặc "mục tiêu IELTS?", **Then** trả tháng 8/2028 và IELTS Academic 6.5 – 7.0, dự kiến thi cuối 2027 hoặc đầu 2028.

---

### User Story 2 - Chủ chatbot thêm môn / sửa giá trị không cần code (Priority: P1)

Chủ chatbot thêm một dòng môn học mới hoặc sửa một giá trị đơn lẻ (ví dụ tốt nghiệp đổi tháng). Ngay yêu cầu tiếp theo, chatbot đã trả lời được điểm, số tín chỉ, có xét chuyên ngành không của môn mới, và các số tổng hợp (GPA, tổng tín chỉ, số môn, môn cao nhất/thấp nhất) tự cập nhật theo.

**Why this priority**: Đây là phần "dữ liệu mở/động" — lý do để làm feature; không có nó thì mỗi kỳ học lại phải sửa tay hàng chục chỗ.

**Independent Test**: Thêm 1 môn giả định vào danh sách môn → hỏi "điểm môn mới" trả đúng điểm; hỏi GPA/tổng tín chỉ → các số đổi theo đúng phép tính; thêm 1 bản ghi hỏi-đáp chủ đề hoàn toàn mới → menu chủ đề và gợi ý tự có chủ đề đó, không cần sửa danh sách chủ đề cứng.

**Acceptance Scenarios**:

1. **Given** thêm một môn có mã, tên, tín chỉ, điểm, **When** người dùng hỏi "điểm <tên môn>", **Then** nhận câu trả lời đầy đủ: "Điểm <tên môn> là <điểm> (<điểm chữ>, <tín chỉ> tín chỉ)".
2. **Given** thêm môn đó, **When** hỏi "<tên môn> xét chuyên ngành không", **Then** trả đúng theo cờ xét chuyên ngành của dòng dữ liệu.
3. **Given** thêm môn đó, **When** hỏi GPA hoặc tổng tín chỉ, **Then** số tổng hợp được tính lại và khớp với phép tính thủ công trên toàn bộ danh sách môn.
4. **Given** sửa một giá trị đơn lẻ (ví dụ tháng tốt nghiệp), **When** hỏi bất kỳ câu nào có chứa giá trị đó, **Then** mọi câu trả lời dùng giá trị mới — chỉ cần sửa đúng một chỗ.

---

### User Story 3 - Thêm mới chủ đề và nội dung tự do (Priority: P2)

Chủ chatbot thêm một chủ đề hoàn toàn mới (ví dụ một dự án, một sở thích) bằng một bản ghi hỏi-đáp ngắn, hoặc thả một tệp mới vào thư mục chờ nạp rồi chạy lệnh nạp. Chủ đề mới tự xuất hiện trong menu chủ đề và gợi ý; nội dung tệp mới có thể hỏi-đáp bằng tìm kiếm ngữ nghĩa với nguồn ghi rõ.

**Why this priority**: Đặt sau 2 story trên vì giá trị cốt lõi (một giá trị duy nhất, thêm môn không code) phải có trước; story này mở rộng chủ đề ngoài hồ sơ học tập.

**Independent Test**: Thêm một bản ghi hỏi-đáp với `topic` chưa từng tồn tại → mở menu chủ đề thấy chủ đề đó; hỏi bằng từ khoá ngắn "mục tiêu" → nhận ≥ 2 gợi ý (học bổng, IELTS, nghề nghiệp) và luôn có nút "Câu hỏi khác".

**Acceptance Scenarios**:

1. **Given** thêm bản ghi hỏi-đáp chủ đề mới, **When** người dùng mở menu chủ đề, **Then** chủ đề mới xuất hiện kèm các câu hỏi của nó.
2. **Given** hỏi "mục tiêu", **When** có nhiều mục có thể là ý người dùng, **Then** nhận gợi ý ≥ 2 câu hỏi đầy đủ (học bổng Thạc sĩ Đức/TUHH, IELTS, định hướng nghề nghiệp) và nút "Câu hỏi khác".
3. **Given** thả một tệp mới (PDF/DOCX/XLSX/CSV/TXT) vào thư mục chờ và chạy nạp, **When** hỏi nội dung chỉ có trong tệp đó, **Then** nhận câu trả lời trích đúng nội dung, nguồn ghi tên tệp và trang/sheet/dòng nếu có.
4. **Given** tệp đã nạp được sửa đổi, **When** chạy nạp lại, **Then** chỉ phần thay đổi được xử lý lại; tệp không đổi thì bỏ qua.

---

### User Story 4 - Dữ liệu sai thì hệ thống từ chối, không nạp một phần (Priority: P2)

Chủ chatbot vô tình thêm một giá trị mâu thuẫn với giá trị hiện có, dùng một placeholder không tồn tại, hoặc thả tệp chứa dữ liệu rác. Lệnh thêm/nạp báo lỗi cụ thể kèm vị trí (số dòng / tên tệp), **không ghi gì**, và chatbot tiếp tục dùng dữ liệu cũ đang chạy.

**Why this priority**: Bảo vệ tính "một giá trị duy nhất" — một lần thêm sai có thể phá hỏng toàn bộ sự thống nhất; phải chặn từ cửa vào.

**Independent Test**: Thêm một giá trị mâu thuẫn (ví dụ GPA 8.30 trong khi đang là 8.51) → lệnh dừng, báo lỗi rõ; dùng `{{khong-ton-tai}}` trong câu trả lời → lệnh kiểm tra báo lỗi kèm số dòng; thả tệp có chuỗi `nan`/`Unnamed`/`[...]` → lệnh nạp báo lỗi; chatbot vẫn trả lời bằng dữ liệu cũ.

**Acceptance Scenarios**:

1. **Given** thêm một giá trị trùng tên nhưng khác giá trị hiện có, **When** chạy lệnh thêm, **Then** lệnh dừng và báo mâu thuẫn, không có thay đổi nào được ghi.
2. **Given** câu trả lời soạn sẵn chứa placeholder không tồn tại, **When** chạy lệnh kiểm tra, **Then** báo lỗi kèm số dòng và tên placeholder; dữ liệu không được nạp.
3. **Given** tệp chờ nạp chứa chuỗi rác (`nan`, `Unnamed`, `about:blank`, `[...]`, "(ví dụ)"), **When** chạy nạp, **Then** lệnh báo lỗi và từ chối; nội dung rác không xuất hiện trong bất kỳ đoạn nào phục vụ trả lời.
4. **Given** dữ liệu mới sai, **When** có yêu cầu tiếp theo, **Then** chatbot vẫn trả lời bằng dữ liệu cũ còn hợp lệ.

---

### User Story 5 - Giọng văn và định dạng đồng nhất (Priority: P3)

Người xem đọc mọi câu trả lời và thấy chatbot luôn nói ở ngôi thứ nhất ("mình", như chính Đức), không còn chữ "tôi"; điểm môn luôn một chữ số thập phân (10.0, 5.4), GPA luôn hai chữ số kèm làm tròn gần đúng (8.51, ≈ 8.5); mọi câu trả lời là câu đầy đủ có ngữ cảnh, không có câu trả lời trơ trọi như "10" hay "Có".

**Why this priority**: Chất lượng cảm nhận; không ảnh hưởng tính đúng của dữ liệu nhưng quyết định độ tin cậy của chatbot.

**Independent Test**: Quét mọi câu trả lời phục vụ được → không còn "tôi"; mọi câu về hồ sơ dùng "mình"; mọi điểm môn hiển thị đúng một chữ số thập phân; mọi câu trả lời về điểm có dạng "Điểm <môn> là <điểm> (<điểm chữ>, <tín chỉ> tín chỉ)".

**Acceptance Scenarios**:

1. **Given** dữ liệu đã nạp, **When** hỏi "xin chào", **Then** trả "Xin chào! Mình là Đức (bản chatbot). Bạn muốn biết gì về mình nào?".
2. **Given** hỏi "Văn Phú Đức", **When** trả lời, **Then** dùng ngôi thứ nhất "Mình là Văn Phú Đức, sinh viên…", không dùng "tôi".
3. **Given** hỏi "điểm vi tích phân 2", **When** trả lời, **Then** hiển thị 10.0 (A+, 4 tín chỉ) — kể cả khi dữ liệu gốc ghi "10".
4. **Given** hỏi "gpa bao nhiêu", **When** trả lời, **Then** hiển thị 8.51 / 10 (≈ 8.5) với đủ 2 chữ số thập phân cho GPA.

---

### Edge Cases

- Môn cùng mã nhưng tên khác hoặc ngược lại → kiểm tra trùng mã/tên khi nạp danh sách môn, báo lỗi thay vì trả nhầm môn.
- Placeholder lồng nhau hoặc chứa ký tự lạ (`{{a{{b}}`), placeholder trống `{{}}` → báo lỗi cú pháp kèm số dòng.
- Giá trị fact chứa chính chuỗi `{{...}}` theo nghĩa đen → có cách thoát rõ ràng, không bị hiểu nhầm là placeholder.
- Hai nguồn cùng khai một sự kiện nhưng khác giá trị → báo mâu thuẫn khi kiểm tra, không âm thầm chọn một nguồn.
- Bản ghi bị `archived` → không được dùng để trả lời hay gợi ý, nhưng vẫn còn trong tệp để khôi phục.
- Giáo dục quốc phòng (7.1, không có trên bảng điểm) → chuyển `archived`, không tính vào bất kỳ số tổng hợp nào.
- Tệp bảng tính `data.xlsx` hiện tại (tên sinh viên "Kim Oanh", mã môn lệch) → cách ly, không nạp; chỉ nạp lại sau khi chủ chatbot sửa đúng.
- Tệp văn bản viết tay chỉ là một tệp duy nhất; các tệp gốc khác chỉ được đọc để dựng nội dung tìm kiếm, không bao giờ ghi đè lên tệp viết tay.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Hệ thống MUST lấy bảng điểm PDF 07/11/2026 làm nguồn sự thật duy nhất cho số liệu học tập: 24 học phần, 87 tín chỉ, GPA 8.514 (thang 10), 3.634 (thang 4), xếp loại Giỏi; mọi nguồn khác MUST khớp với các số này.
- **FR-002**: Hệ thống MUST hỗ trợ bản ghi `fact` (một giá trị có tên: mã, nhãn, giá trị, ngày chụp, nguồn) cho các giá trị đơn lẻ: GPA thang 10, GPA thang 4, tổng tín chỉ, số học phần, xếp loại, ngành, tốt nghiệp, IELTS…
- **FR-003**: Câu trả lời soạn sẵn MUST dùng được placeholder `{{id-fact}}`; khi trả lời, placeholder được thay bằng giá trị của fact tương ứng.
- **FR-004**: Hệ thống MUST báo lỗi (kèm số dòng) nếu placeholder tham chiếu fact không tồn tại; dữ liệu chứa lỗi này MUST NOT được nạp.
- **FR-005**: Danh sách môn học MUST là nguồn duy nhất cho điểm từng môn, số tín chỉ từng môn và cờ xét chuyên ngành; mỗi môn gồm: mã, tên, tín chỉ, điểm thang 10, điểm thang 4, điểm chữ, có xét chuyên ngành, bí danh.
- **FR-006**: Từ danh sách môn, hệ thống MUST tự dựng được câu trả lời cho: điểm môn X, môn X mấy tín chỉ, môn X có xét chuyên ngành không — mà không cần bản ghi hỏi-đáp viết tay cho từng môn.
- **FR-007**: Các số tổng hợp (GPA thang 10, GPA thang 4, tổng tín chỉ, số học phần, GPA xét chuyên ngành, môn cao nhất, môn thấp nhất) MUST được tính từ danh sách môn; nếu kết quả tính lệch với dòng tổng kết của bảng điểm thì báo mâu thuẫn.
- **FR-008**: Hệ thống MUST áp dụng bí danh (viết tắt, tên gọi khác — ví dụ `vtp2`, `oop`, `ctdl`, `xstk`, `hđh`) khi khớp câu hỏi; "điểm oop" và "điểm phương pháp lập trình hướng đối tượng" MUST trả cùng kết quả.
- **FR-009**: Bản ghi hỏi-đáp viết tay trùng ý (ví dụ `vtp1`/`vi-tich-phan-1`) MUST được gộp lại thông qua bí danh hoặc xoá, không giữ hai bản sao.
- **FR-010**: Mọi bản ghi MUST có trạng thái `active` hoặc `archived`; bản ghi `archived` MUST NOT được dùng để trả lời hay gợi ý, và MUST giữ lại được để khôi phục.
- **FR-011**: Hệ thống MUST cung cấp ba cách thêm dữ liệu cho chủ chatbot: (a) sửa trực tiếp tệp viết tay, (b) thả tệp vào thư mục chờ rồi chạy lệnh nạp, (c) lệnh thêm nhanh cho fact / hỏi-đáp / môn học.
- **FR-012**: Mọi lệnh thêm MUST chạy theo thứ tự: kiểm tra hợp lệ → kiểm tra mâu thuẫn với giá trị hiện có → ghi trọn vẹn (không ghi dở) → hệ thống tự nạp lại. Nếu bất kỳ bước nào sai, lệnh MUST dừng và không ghi gì.
- **FR-013**: Hệ thống MUST tự nhận biết tệp dữ liệu thay đổi và dùng dữ liệu mới cho yêu cầu kế tiếp mà không cần khởi động lại thủ công; tệp mới sai thì giữ nguyên dữ liệu cũ đang chạy.
- **FR-014**: Hệ thống MUST loại bỏ khỏi tri thức: mọi số liệu cũ (GPA 8.30, 62 tín chỉ, 17 môn, 3.7/4.0), các bản ghi hỏi-đáp điểm từng môn viết tay, 5 bản ghi tài liệu cũ mang số lệch, bản ghi liên hệ dùng dữ liệu ví dụ.
- **FR-015**: Hệ thống MUST kiểm tra và từ chối dữ liệu chứa chuỗi rác (`nan`, `Unnamed`, `about:blank`, `[...]`, "(ví dụ)") và tệp có ô trống dạng placeholder (`[HỌ VÀ TÊN]`…) khi nạp.
- **FR-016**: Mọi câu trả lời về hồ sơ MUST dùng ngôi thứ nhất ("mình"), MUST NOT dùng "tôi"; câu chào MUST là "Xin chào! Mình là Đức (bản chatbot). Bạn muốn biết gì về mình nào?".
- **FR-017**: Điểm môn MUST hiển thị đúng một chữ số thập phân (10.0, 5.4, 8.1); GPA MUST hiển thị hai chữ số thập phân kèm giá trị làm tròn gần đúng (8.51, ≈ 8.5; 3.63).
- **FR-018**: Mọi câu trả lời về điểm MUST là câu đầy đủ: "Điểm <tên môn> là <điểm> (<điểm chữ>, <tín chỉ> tín chỉ)" — không được trả lời trơ trọi chỉ con số.
- **FR-019**: Hồ sơ MUST ghi: ngành đào tạo "Khoa học Máy tính và Khoa học Dữ liệu"; chuyên ngành dự kiến tách riêng gồm Máy tính, Trí tuệ nhân tạo (AI), Kỹ thuật phần mềm; tốt nghiệp dự kiến tháng 8/2028; GPA thang 4 trong CV là 3.63/4.0.
- **FR-020**: Điểm môn "Phương pháp lập trình hướng đối tượng" MUST là 6.9 (B, 4 tín chỉ); GPA xét chuyên ngành MUST là 8.55 (21 môn, 79 tín chỉ), không tính Kỹ năng mềm, Pháp luật đại cương, Kinh tế đại cương; Triết học và Kinh tế chính trị Mác - Lênin vẫn được tính.
- **FR-021**: Hồ sơ MUST bổ sung các mục hỏi-đáp còn thiếu: học bổng Thạc sĩ Đức (trường mục tiêu TUHH), IELTS Academic 6.5–7.0 (dự kiến thi cuối 2027/đầu 2028), tốt nghiệp, định hướng nghề nghiệp (AI Engineer / Machine Learning / Computer Science Research), phong cách học tập; mỗi mục có 3–5 cách hỏi, trong đó có từ khoá "mục tiêu" để ra gợi ý.
- **FR-022**: Kỹ năng và dự án MUST được gộp từ cả tri thức hiện có và CV: kỹ năng nhóm theo Ngôn ngữ, Backend, Frontend, AI/ML, Data Engineering, Database, Công cụ, Nguồn dữ liệu; dự án gồm Chatbot giới thiệu bản thân và Vietnam Air Quality & Weather Analytics Platform.
- **FR-023**: Khi hỏi một từ khoá mơ hồ như "mục tiêu", hệ thống MUST đưa ra ít nhất 2 gợi ý và luôn có nút "Câu hỏi khác".
- **FR-024**: Hệ thống MUST cung cấp lệnh kiểm tra toàn bộ dữ liệu (cú pháp, placeholder, trùng mã, mâu thuẫn, chuỗi rác) chạy độc lập, trả danh sách lỗi kèm vị trí, không cần mô hình ngôn ngữ.
- **FR-025**: Khi nạp tệp văn bản/PDF, số trang MUST đánh từ 1 và bỏ phần chân trang/tiêu đề lặp lại; khi đọc bảng tính MUST bỏ cột/dòng trống không tên và làm tròn số thực nhiễu (ví dụ 9.300000000000001 → 9.3).

### Key Entities *(include if feature involves data)*

- **Fact**: một giá trị có tên dùng chung (ví dụ `gpa-10` = 8.51, `graduation` = tháng 8/2028); có ngày chụp dữ liệu và nguồn; được tham chiếu bằng placeholder trong câu trả lời.
- **Course (môn học)**: mã môn, tên, số tín chỉ, điểm thang 10, điểm thang 4, điểm chữ, cờ xét chuyên ngành, bí danh; là nguồn duy nhất của mọi số liệu học tập.
- **QA record (hỏi-đáp viết tay)**: chủ đề, câu hỏi (3–5 cách hỏi), câu trả lời hoặc gạch đầu dòng, trạng thái; dùng placeholder thay vì gõ tay giá trị.
- **Doc record (nội dung tự do)**: đoạn văn dài (CV, bảng điểm) phục vụ tìm kiếm ngữ nghĩa; sinh tự động từ tệp gốc, không gõ tay số liệu.
- **Alias (bí danh)**: ánh xạ viết tắt/tên khác → môn hoặc chủ đề chuẩn (vtp2, oop, ctdl, xstk…).
- **Inbox file (tệp chờ nạp)**: tệp gốc PDF/DOCX/XLSX/CSV/TXT kèm dấu vân tay để chỉ nạp lại khi thay đổi.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Quét mọi nội dung chatbot có thể phục vụ trả lời: 0 lần xuất hiện của `8.30`, `8.3`, `62 tín chỉ`, `62 TC`, `17 môn`, `3.7/4.0` (mục N1).
- **SC-002**: Các số tổng hợp tính từ danh sách môn khớp đúng bảng điểm: 24 học phần, 87 tín chỉ, GPA 8.514 thang 10, 3.634 thang 4 (mục N2).
- **SC-003**: Mỗi giá trị dùng chung xuất hiện với đúng một giá trị trên mọi nguồn; 0 cảnh báo mâu thuẫn khi kiểm tra toàn bộ dữ liệu (mục N3).
- **SC-004**: 100% câu hỏi bằng bí danh ("điểm vtp2", "oop bao nhiêu", "ctdl", "xstk") trả đúng môn và đúng điểm; "oop" trả 6.9 (mục N5).
- **SC-005**: Thêm một môn mới vào danh sách môn rồi hỏi điểm môn đó → trả đúng ngay yêu cầu kế tiếp, và GPA/tổng tín chỉ thay đổi đúng phép tính mà không cần sửa bất kỳ chỗ nào khác (mục N6).
- **SC-006**: 100% lệnh thêm/nạp dữ liệu sai (giá trị mâu thuẫn, placeholder không tồn tại, tệp chứa chuỗi rác) bị từ chối kèm thông báo vị trí lỗi; chatbot vẫn trả lời bằng dữ liệu cũ (mục N7).
- **SC-007**: 0 đoạn nội dung nạp chứa `nan`, `Unnamed`, `about:blank`, `[...]`, "(ví dụ)" (mục N8).
- **SC-008**: 100% câu trả lời về hồ sơ dùng "mình", 0 câu dùng "tôi"; 100% câu trả lời về điểm là câu đầy đủ đúng định dạng (mục N9).
- **SC-009**: Hỏi "mục tiêu" nhận ≥ 2 gợi ý và nút "Câu hỏi khác"; thêm một chủ đề mới thì menu chủ đề tự có chủ đề đó (mục N4 + N6).

## Assumptions

- Chủ chatbot đã duyệt toàn bộ đáp án đề xuất Q1–Q16 của kế hoạch (nguồn sự thật, cách ghi ngành, tốt nghiệp 8/2028, GPA CV 3.63, điểm OOP 6.9, GPA xét chuyên ngành 8.55, GDQP archived, xlsx cách ly, giọng văn ngôi thứ nhất, gỡ liên hệ ví dụ, gộp kỹ năng/dự án, định dạng điểm, ba cách thêm dữ liệu, một tệp viết tay duy nhất).
- Bảng điểm PDF ngày 07/11/2026 là bản mới nhất và chính xác; chủ chatbot chịu trách nhiệm cập nhật khi có bảng điểm mới hơn.
- Thông tin liên hệ thật (email, GitHub, LinkedIn, số điện thoại) chưa được cung cấp nên chưa xuất hiện ở bất kỳ đâu; sẽ bổ sung khi có.
- Tệp `data.xlsx` hiện tại thuộc về người khác ("Kim Oanh") và không được nạp; nếu là của chủ chatbot thì phải sửa đúng rồi mới nạp lại.
- Các hợp đồng trả lời hiện có (`type: answer/suggest/clarify`, gợi ý, menu chủ đề) và cơ chế tự làm mới theo dấu hiệu thay đổi tệp từ các feature trước vẫn áp dụng; feature này bổ sung nguồn dữ liệu và quy tắc thống nhất.
- Trang quản trị giao diện web nằm ngoài phạm vi bản này; việc thêm dữ liệu dùng tệp và dòng lệnh.
- `PLAN_MASTER.md` sẽ được cập nhật mục 3, 5, 6 cho khớp thiết kế mới (fact, placeholder, danh sách môn, bí danh, thư mục chờ nạp).
