#!/usr/bin/env python3
import ctypes
import os
import sys


def available_memory_gb():
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise RuntimeError("Không đọc được thông tin bộ nhớ trên Windows")
        return status.ullAvailPhys / (1024**3)

    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        available_pages = os.sysconf("SC_AVPHYS_PAGES")
        return page_size * available_pages / (1024**3)
    except (ValueError, OSError) as exc:
        raise RuntimeError(
            "Không đọc được thông tin bộ nhớ trên hệ điều hành này"
        ) from exc


def recommended_model(gb):
    if gb < 4:
        return "qwen2.5:1.5b"
    if gb < 8:
        return "qwen2.5:3b"
    if gb < 16:
        return "qwen2.5:7b"
    return "qwen2.5:14b"


def main():
    try:
        gb = available_memory_gb()
    except RuntimeError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1

    model = recommended_model(gb)
    print(f"RAM còn trống: {gb:.1f} GB")
    print(f"Model trả lời đề xuất: {model}")
    if gb < 4:
        print(
            "Cảnh báo: RAM dưới 4 GB. Nên nâng cấp máy hoặc dùng dịch vụ trả lời bên ngoài."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
