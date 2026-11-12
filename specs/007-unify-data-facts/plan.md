# Implementation Plan: Thống nhất dữ liệu đầu vào + dữ liệu mở/động

**Branch**: `007-unify-data-facts` | **Date**: 2026-11-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-unify-data-facts/spec.md`

## Summary

Thống nhất toàn bộ dữ liệu hồ sơ của chatbot về một nguồn sự thật duy nhất (bảng điểm PDF 07/11/2026: 24 học phần, 87 TC, GPA 8.514/3.634, xếp loại Giỏi) và biến dữ liệu thành **mở/động**: mỗi con số chỉ nằm một chỗ (fact + placeholder), hỏi-đáp từng môn và các số tổng hợp được sinh tự động từ danh sách môn học, chủ chatbot thêm mới dữ liệu bằng tệp/lệnh mà không cần sửa code, và mọi dữ liệu sai bị từ chối trước khi nạp.

**Cách tiếp cận** (2 mốc, theo đúng lộ trình đã duyệt trong kế hoạch):

- **Mốc 1 — Thống nhất dữ liệu (làm thủ công, không code mới)**: thay `chatbot.txt` bằng bản `CHATBOT-SOURCE v1` mới đã được duyệt (mọi giá trị khớp PDF), gỡ 5 record `doc` cũ mang số lệch, gỡ `contact`, `archived` GDQP, cách ly `data.xlsx`, sửa CV và `data.txt` theo Q2–Q4, thêm `sources/courses.csv` (24 dòng từ PDF) và `sources/aliases.txt` làm nguồn cho mốc 2. Chatbot trả lời đúng mọi số ngay lập tức.
- **Mốc 2 — Dữ liệu mở/động (code)**: parser hỗ trợ `kind: fact` + placeholder `{{id}}` + `status`; bộ dựng hỏi-đáp từ `courses.csv` kèm tính số tổng hợp và đối chiếu cảnh báo mâu thuẫn; bí danh trong chuẩn hoá câu hỏi; lệnh `add fact/qa/course` và `ingest inbox/` với quy trình validate → kiểm tra mâu thuẫn → ghi nguyên tử → tự nạp lại. Sau mốc 2, xoá các bản ghi `diem-*` viết tay và chuyển giá trị sang fact + placeholder (đích cuối N1–N9).

## Technical Context

**Language/Version**: Python 3.11 (backend, image `python:3.11-slim`)

**Primary Dependencies**: Flask, LangChain + FAISS (RAG), rapidfuzz (khớp mờ), pandas/openpyxl/pypdf/python-docx (trích xuất tài liệu — đã có ở feature 006), numpy (embedding cache), pytest

**Storage**: Tệp văn bản thuần `backend/data/chatbot.txt` (viết tay duy nhất) + `backend/data/sources/courses.csv`, `backend/data/sources/aliases.txt` (mới) + `backend/data/inbox/` (mới, chờ nạp) + chỉ mục phái sinh `backend/doc_index/` (FAISS + cache embedding, tự tạo lại khi nguồn đổi)

**Testing**: pytest — `backend/tests/` (đã có 27 tệp test; bổ sung `test_facts.py`, `test_courses.py`, `test_aliases.py`, mở rộng `test_source_format.py`, `test_source_cli.py`)

**Target Platform**: Linux server, Docker Compose (backend + frontend + Ollama); CLI chạy trong container hoặc venv

**Project Type**: Web service (chat API) + CLI vận hành (`manage_docs.py`)

**Performance Goals**: Nạp/kiểm tra toàn bộ nguồn ≤ 1 s (tiêu chí từ feature 005); phản hồi p50 < 300 ms (từ feature 006); sinh hỏi-đáp từ `courses.csv` (≤ 500 dòng) là O(n) khi khởi động

**Constraints**: Parser thuần Python, không gọi Ollama (validate offline); lỗi phải bằng tiếng Việt kèm số dòng/tên tệp; không ghi dở dữ liệu (ghi nguyên tử `os.replace`); dữ liệu mới sai → giữ index cũ đang chạy

**Scale/Scope**: 1 chatbot cá nhân; ~24–100 học phần, ~50–150 bản ghi hỏi-đáp, ≤ 10 tệp inbox; không cần đồng bộ nhiều người dùng

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Tệp `.specify/memory/constitution.md` hiện chỉ là mẫu chưa điền (không có nguyên tắc nào được ban hành) → **không có gate bổ sung từ constitution**. Áp dụng các nguyên tắc đã được thiết lập ở feature 005/006 làm chuẩn bắt buộc của dự án:

| Nguyên tắc (từ spec 005/006) | Đánh giá thiết kế này |
|---|---|
| Một tệp văn bản viết tay duy nhất, không ghi đè khi chạy | ✅ `chatbot.txt` giữ vai trò viết tay; `courses.csv`/`aliases.txt`/`inbox/` chỉ là nguồn đọc để dựng chỉ mục, không ghi ngược vào `chatbot.txt` (Q16) |
| Kiểm tra toàn bộ trước khi thay thế trạng thái đang chạy | ✅ Quy trình add/ingest: validate → kiểm tra mâu thuẫn → ghi nguyên tử → reload; sai thì dừng, giữ index cũ |
| Lỗi tiếng Việt kèm vị trí (số dòng/tên tệp) | ✅ Mã lỗi mới `E_PLACEHOLDER_UNKNOWN`, `E_PLACEHOLDER`, `E_NOISE`, `E_CONFLICT`, `W_CONFLICT` đều kèm vị trí |
| Parser không phụ thuộc LLM, nhanh, kiểm tra được offline | ✅ facts/placeholder/courses/aliases đều thuần Python |
| Không có ngõ cụt trả lời; menu chủ đề tự có chủ đề mới | ✅ `build_topics` đã dựng từ dữ liệu (không hard-code); mốc 1 bổ sung chủ đề "Mục tiêu" với ≥ 2 gợi ý cho từ khoá "mục tiêu" |

**Kết luận gate**: PASS (không vi phạm).

**Re-check sau Phase 1**: vẫn PASS — `data-model.md` giữ "một giá trị một chỗ" (fact + courses.csv), `contracts/` không đổi hợp đồng API 004/006, quy trình ghi nguyên tử + giữ index cũ khi lỗi khớp nguyên tắc 005; không có nguyên tắc constitution nào bị vi phạm vì constitution chưa được điền.

## Project Structure

### Documentation (this feature)

```text
specs/007-unify-data-facts/
├── plan.md              # Tệp này
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── chatbot-source-v2.md   # Ngữ pháp mở rộng: fact, placeholder, status
│   ├── courses-csv.md         # Đặc tả danh sách môn học
│   └── manage-docs-cli.md     # Hợp đồng lệnh vận hành add/ingest/validate
└── tasks.md             # Phase 2 output (/speckit.tasks — chưa tạo)
```

### Source Code (repository root)

```text
backend/
├── source_format.py     # SỬA: kind: fact, placeholder, status, mã lỗi mới
├── courses.py           # MỚI: đọc courses.csv, dựng QA từng môn, tính số tổng hợp, đối chiếu W_CONFLICT
├── aliases.py           # MỚI: đọc aliases.txt, chuẩn hoá bí danh khi khớp câu hỏi
├── chatbox.py           # SỬA: nạp thêm facts + QA sinh từ courses + bí danh; signature đổi theo 3 nguồn mới
├── doc_loaders.py       # SỬA: lọc chuỗi rác (nan/Unnamed/about:blank), đánh số trang từ 1, làm tròn số nhiễu
├── scripts/manage_docs.py  # SỬA: subcommand add fact/qa/course, ingest inbox/, validate mở rộng, ghi nguyên tử
├── data/
│   ├── chatbot.txt      # SỬA (mốc 1): bản nội dung mới đã duyệt
│   ├── sources/         # MỚI: courses.csv, aliases.txt
│   ├── inbox/           # MỚI: tệp chờ nạp
│   └── data.xlsx        # Cách ly (giữ file, không nạp)
└── tests/
    ├── test_facts.py            # MỚI
    ├── test_courses.py          # MỚI
    ├── test_aliases.py          # MỚI
    ├── test_source_format.py    # MỞ RỘNG
    └── test_source_cli.py       # MỞ RỘNG (add/ingest atomic, mã lỗi)
```

**Structure Decision**: Giữ cấu trúc hiện có (backend đơn + CLI nằm trong `backend/scripts/`). Thêm 2 module thuần Python (`courses.py`, `aliases.py`) để tránh phình `chatbox.py` (đã ~900 dòng); không tạo project mới, không đổi layout frontend.

## Complexity Tracking

> Không có vi phạm constitution nào cần biện minh (constitution chưa được điền).
