# Contract: `sources/courses.csv` — danh sách môn học (nguồn mọi số liệu học tập)

**Vị trí mặc định**: `backend/data/sources/courses.csv` (ghi đè bằng `CHATBOT_COURSES_PATH`).
**Mã hoá**: UTF-8, LF, dòng đầu là header đúng thứ tự dưới đây.

## Cột (đúng thứ tự)

```csv
code,name,credits,score10,score4,letter,counts_major,aliases
```

| Cột | Bắt buộc | Quy tắc |
|---|---|---|
| `code` | có | duy nhất; ví dụ `CSC10006` |
| `name` | có | duy nhất; tên đầy đủ có dấu |
| `credits` | có | số nguyên 1–20 |
| `score10` | có | 0–10, tối đa 4 chữ số thập phân |
| `score4` | không | 0–4; để trống thì tính từ `score10` theo bảng quy đổi |
| `letter` | không | `A+, A, B+, B, C+, C, D+, D, F` |
| `counts_major` | có | `yes` hoặc `no` |
| `aliases` | không | chuỗi phân tách `\|`, không trùng nhau, không trùng `code`/`name` |

## Mã lỗi khi nạp/validate

| Tình huống | Mã | Mức |
|---|---|---|
| Trùng `code` hoặc trùng `name` | `E_CONFLICT` | error |
| Thiếu cột bắt buộc / sai header | `E_BAD_CSV` | error |
| `credits`/`score10`/`score4` ngoài khoảng | `E_BAD_VALUE` | error |
| `counts_major` khác yes/no | `E_BAD_ENUM` | error |
| Số tổng hợp tính ra lệch dòng tổng kết PDF (dung sai 0.001) | `W_CONFLICT` | warning |
| `code`/`name`/alias mâu thuẫn với dữ liệu hiện có | `E_CONFLICT` | error |

## Dữ liệu sinh ra từ mỗi dòng

Từ một dòng, hệ thống tự dựng 3 mục hỏi-đáp (không cần record viết tay):

| Hỏi | Câu trả lời (định dạng cố định) |
|---|---|
| "điểm `<name>`" (và mọi bí danh) | "Điểm `<name>` là `<score10>` (`<letter>`, `<credits>` tín chỉ)." |
| "`<name>` mấy tín chỉ" | "`<name>` có `<credits>` tín chỉ." |
| "`<name>` xét chuyên ngành không" | "Có/Không, môn `<name>` được/không được tính khi xét chuyên ngành." |

## Số tổng hợp (luôn tính ra, không gõ tay)

- `credits-total` = Σ credits
- `courses-count` = số dòng
- `gpa-10` = Σ(score10×credits) / Σcredits (làm tròn hiển thị 2 chữ số: 8.51)
- `gpa-4` = Σ(score4×credits) / Σcredits (hiển thị 3.63)
- `gpa-major` = như trên, chỉ các dòng `counts_major=yes`
- `top-subjects` = các dòng có `score10` cao nhất (bằng nhau thì liệt kê hết)
- `bottom-subject` = dòng có `score10` thấp nhất

Đối chiếu: `gpa-10`, `gpa-4`, `credits-total`, `courses-count` phải khớp giá trị fact tương ứng và dòng tổng kết bảng điểm; lệch → `W_CONFLICT` in hai giá trị.

## Mẫu 24 dòng ban đầu

Khớp từng hàng bảng điểm PDF 07/11/2026 (thứ tự theo STT, mã môn theo PDF — ví dụ `CSC10014` Tư duy tính toán, `CSC10012` Cơ sở lập trình; KHÔNG dùng mã cũ `CSC10144`/`CSC10112` của xlsx). Cột `counts_major=no` cho: Kỹ năng mềm, Pháp luật đại cương, Kinh tế đại cương; các môn còn lại là `yes` (Triết học và Kinh tế chính trị Mác - Lênin vẫn tính).

```csv
code,name,credits,score10,score4,letter,counts_major,aliases
CSC00004,Nhập môn Công nghệ Thông tin,4,7.5,3.25,B+,yes,nmcntt
CSC10012,Cơ sở lập trình,4,8.5,3.75,A,yes,cslp
CSC10121,Kỹ năng mềm,3,9.3,4,A+,no,knm|kĩ năng mềm
MTH00009,Toán rời rạc,4,9.4,4,A+,yes,trr
BAA00004,Pháp luật đại cương,3,8.6,3.8,A,no,pháp luật
CSC10004,Cấu trúc dữ liệu và giải thuật,4,5.4,2.2,C,yes,ctdl|dsa
MTH00058,Toán học tổ hợp,4,7.4,3.2,B+,yes,
PHY00005,Vật lý đại cương 1,4,9.1,4,A+,yes,vlđc
CSC10003,Phương pháp lập trình hướng đối tượng,4,6.9,2.95,B,yes,oop|pplt hđt
CSC10009,Hệ thống máy tính,2,7.8,3.4,B+,yes,htmt
MTH00005,Vi tích phân 1,4,9.4,4,A+,yes,vtp1
MTH00008,Đại số tuyến tính,4,10,4,A+,yes,dstt
BAA00005,Kinh tế đại cương,2,5.9,2.45,C,no,
CSC10008,Mạng máy tính,4,7.3,3.15,B+,yes,mmt
CSC10014,Tư duy tính toán,4,9.1,4,A+,yes,tdtt
MTH00006,Vi tích phân 2,4,10,4,A+,yes,vtp2
BAA00101,Triết học Mác - Lênin,3,9,4,A+,yes,triết
CSC10006,Cơ sở dữ liệu,4,9.8,4,A+,yes,csdl
CSC10007,Hệ điều hành,4,8.1,3.55,A,yes,hđh
MTH00007,Xác suất thống kê,4,10,4,A+,yes,xstk
BAA00102,Kinh tế chính trị Mác - Lênin,2,8.9,3.95,A,yes,ktct
CSC14003,Cơ sở trí tuệ nhân tạo,4,7.7,3.35,B+,yes,csai
MTH00057,Toán ứng dụng và thống kê cho Công nghệ thông tin,4,9.3,4,A+,yes,toán ứng dụng
PHY00007,Vật lý cho Công nghệ thông tin,4,8.8,3.9,A,yes,vl cntt
```

*(Bảng đầy đủ được dựng trong mốc 1; bảng trên là mẫu định dạng, luôn kiểm chứng lại với tệp PDF gốc.)*
