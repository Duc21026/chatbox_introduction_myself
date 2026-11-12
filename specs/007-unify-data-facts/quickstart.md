# Quickstart: Kiểm chứng thống nhất dữ liệu + dữ liệu mở/động

Hướng dẫn chạy nghiệm thu N1–N9 của spec mà không cần đọc code. Tham chiếu: [data-model.md](./data-model.md), [contracts/](./contracts/), [spec.md](./spec.md).

## Chuẩn bị

```bash
# 1. Vào repo, kích hoạt môi trường
cd /run/media/dbin2102/game2/chatbot
source .venv/bin/activate        # hoặc dùng Docker Compose ở bước 5

# 2. (Mốc 1 đã làm xong) xác nhận các tệp dữ liệu mới tồn tại
ls backend/data/chatbot.txt backend/data/sources/courses.csv backend/data/sources/aliases.txt

# 3. Kiểm tra toàn bộ nguồn — không cần Ollama
python backend/scripts/manage_docs.py validate
# Kỳ vọng: exit 0, không có issue; nếu có W_CONFLICT thì in hai giá trị lệch nhau
```

## A. Nghiệm thu dữ liệu thống nhất (N1–N3, N8)

```bash
# N1 — không còn số cũ ở bất kỳ đâu chatbot phục vụ
grep -rEn "8\.30|8\.3 |62 tín chỉ|62 TC|17 môn|3\.7/4\.0" backend/data/chatbot.txt \
  && echo "FAIL: còn số cũ" || echo "PASS N1"

# N2 — số tổng hợp tính từ courses.csv khớp PDF
python backend/scripts/manage_docs.py validate --json
# Kỳ vọng trong kết quả: courses=24, credits=87, gpa10=8.514, gpa4=3.634, 0 W_CONFLICT

# N3 — một fact một giá trị: validate không báo E_CONFLICT (kiểm tra ở trên)

# N8 — nạp sạch: ingest tệp mẫu không còn chuỗi rác
mkdir -p backend/data/inbox
# thử nạp một tệp xlsx/PDF thật, sau đó:
python backend/scripts/manage_docs.py ingest inbox/
# Kỳ vọng: không có đoạn nào chứa nan/Unnamed/about:blank; tệp có [...] bị từ chối E_PLACEHOLDER
```

## B. Hỏi đáp trực tiếp (N4, N5, N9)

```bash
# Khởi động API (cần Ollama cho embedding; KB engine vẫn cần model embedding)
docker compose up -d backend frontend   # hoặc: python backend/app.py

# N5 — bí danh: đều phải ra cùng một môn, "oop" ra 6.9
python backend/scripts/manage_docs.py ask "điểm vtp2"
python backend/scripts/manage_docs.py ask "oop bao nhiêu"
python backend/scripts/manage_docs.py ask "điểm ctdl"
# Kỳ vọng: "Điểm Vi tích phân 2 là 10.0 (A+, 4 tín chỉ)."
#          "Điểm Phương pháp lập trình hướng đối tượng là 6.9 (B, 4 tín chỉ)."
#          "Điểm Cấu trúc dữ liệu và giải thuật là 5.4 (C, 4 tín chỉ)."

# N4 — từ khoá mơ hồ ra ≥ 2 gợi ý
python backend/scripts/manage_docs.py ask "mục tiêu"
# Kỳ vọng: type suggest, ≥ 2 gợi ý (học bổng/TUHH, IELTS, nghề nghiệp) + nút "Câu hỏi khác"

# N9 — giọng văn: không còn "tôi", dùng "mình"
python backend/scripts/manage_docs.py ask "xin chào"
# Kỳ vọng: "Xin chào! Mình là Đức (bản chatbot). Bạn muốn biết gì về mình nào?"

# Định dạng điểm (Q14): GPA 2 chữ số + ≈
python backend/scripts/manage_docs.py ask "gpa bao nhiêu"
# Kỳ vọng: "… 8.51 / 10 (≈ 8.5; thang 4: 3.63), với 87 tín chỉ … 24 học phần, xếp loại Giỏi."
```

## C. Thêm mới không cần code (N6)

```bash
# Thêm một môn giả định rồi kiểm tra ngay
python backend/scripts/manage_docs.py add course --code CSC90001 \
    --name "Môn học thử nghiệm" --credits 3 --score10 9.5 --counts-major yes
python backend/scripts/manage_docs.py ask "điểm môn học thử nghiệm"
python backend/scripts/manage_docs.py ask "tổng tín chỉ bao nhiêu"
# Kỳ vọng: trả 9.5 (A, 3 tín chỉ); tổng tín chỉ tăng đúng 3 (87 → 90) mà không sửa chỗ nào khác

# Thêm chủ đề hoàn toàn mới
python backend/scripts/manage_docs.py add qa --topic "Sở thích" \
    --q "Bạn thích làm gì khi rảnh?" --a "Mình thích đọc tài liệu về AI và chạy thử các mô hình nhỏ."
python backend/scripts/manage_docs.py ask "menu"
# Kỳ vọng: menu chủ đề có "Sở thích" mà không cần cấu hình

# Dọn dẹp mẫu thử (tuỳ chọn): xoá dòng môn + record chủ đề vừa thêm
```

## D. Dữ liệu sai thì dừng (N7)

```bash
# Placeholder không tồn tại
printf '=== RECORD ===\nkind: qa\nid: x-test\ntopic: T\nquestions:\n- t?\nanswer: {{khong-ton-tai}}\n=== END ===\n' >> backend/data/chatbot.txt
python backend/scripts/manage_docs.py validate
# Kỳ vọng: E_PLACEHOLDER_UNKNOWN kèm số dòng; exit != 0; API vẫn trả lời bằng dữ liệu cũ
git checkout -- backend/data/chatbot.txt   # hoàn tác

# Giá trị mâu thuẫn với fact hiện có
python backend/scripts/manage_docs.py add fact --id gpa-10 --label "GPA" --value 8.30
# Kỳ vọng: nếu id đã tồn tại với giá trị khác → báo mâu thuẫn rõ ràng; không ghi (tuỳ chính sách: cập nhật khi chủ chủ đích)

# Tệp inbox chứa placeholder chưa điền
echo "Họ tên: [HỌ VÀ TÊN]" > backend/data/inbox/test.txt
python backend/scripts/manage_docs.py ingest inbox/test.txt
# Kỳ vọng: E_PLACEHOLDER, tệp bị từ chối, chỉ mục không đổi
rm backend/data/inbox/test.txt
```

## E. Bộ test tự động

```bash
cd backend && python -m pytest tests/ -q
# Kỳ vọng: toàn bộ xanh, gồm các tệp mới:
#   test_facts.py, test_courses.py, test_aliases.py,
#   test_source_format.py (mở rộng), test_source_cli.py (mở rộng)
```

## Bảng nghiệm thu cuối cùng (ánh xạ tiêu chí spec)

| N | Kiểm tra | Lệnh | Kỳ vọng |
|---|---|---|---|
| N1 | không còn số cũ | grep (mục A) | 0 kết quả |
| N2 | số tính ra khớp PDF | validate --json | 24 HP, 87 TC, 8.514, 3.634 |
| N3 | một fact một giá trị | validate | 0 W/E_CONFLICT |
| N4 | "mục tiêu" ra ≥ 2 gợi ý | ask "mục tiêu" | suggest + nút "Câu hỏi khác" |
| N5 | bí danh vtp2/oop/ctdl | ask | đúng môn, oop = 6.9 |
| N6 | thêm môn/chủ đề không code | add course / add qa | trả lời đúng, GPA/TC đổi theo, menu có chủ đề mới |
| N7 | sai thì dừng | mục D | lỗi kèm vị trí, giữ index cũ |
| N8 | nạp sạch | ingest inbox/ | 0 chuỗi rác trong chunk |
| N9 | giọng văn | ask "xin chào"… | "mình", không "tôi"; định dạng điểm chuẩn |
