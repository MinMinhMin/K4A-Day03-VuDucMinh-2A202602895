# 📊 BÁO CÁO THU HOẠCH NGHIỆM THU BÀI LAB 3 (BƯỚC 3 — SUBMISSION ARTIFACT)

> **Họ và Tên Học viên:** Vũ Đức Minh
> **Mã Sinh Viên / Mã Học viên:** 2A202602895
> **Chủ đề Lựa chọn:** Trợ lý Trạm sạc xe điện Vinfast: Đặt trước trạm sạc, tra cứu vị trí, tình trạng trạm và cổng sạc còn trống

---

## 1. BẢNG CHẤM ĐIỂM AGENTIC FIT SCORING MATRIX (ĐÁNH GIÁ CHỦ ĐỀ)

| Tiêu chí Đánh giá | Mức độ (1 - 5) | Giải trình chi tiết lý do chọn điểm |
| :--- | :---: | :--- |
| **1. Multi-step Reasoning** | **4 / 5** | Agent cần thực hiện chuỗi bước: xác định vị trí/thời gian, tra cứu trạm phù hợp, kiểm tra tình trạng và số cổng sạc còn trống, sau đó đặt trước cổng sạc. |
| **2. Tool Interaction** | **5 / 5** | Hệ thống cần kết nối MCP Server hoặc cơ sở dữ liệu bên ngoài để tra cứu vị trí, trạng thái trạm, loại cổng sạc và thực hiện thao tác đặt chỗ. |
| **3. Dynamic Decision** | **5 / 5** | Quyết định tiếp theo phụ thuộc vào khoảng cách, tình trạng hoạt động của trạm, số cổng còn trống và thời gian người dùng yêu cầu. |
| **4. Long Horizon Goal** | **3 / 5** | Bài toán có nhiều bước xử lý liên tiếp trong một phiên, nhưng thông thường chưa cần duy trì mục tiêu qua nhiều phiên hoặc thời gian dài. |
| **TỔNG ĐIỂM AGENTIC FIT** | **17 / 20** | *Tổng điểm trên 12/20, vì vậy bài toán rất phù hợp để triển khai Agentic System.* |

---

## 2. TRÍCH XUẤT KẾT QUẢ WATERFALL TRACE LOG (SAU KHI CHẠY TEST SUITE TRÊN API THẬT)

> ⚠️ **YÊU CẦU NGHIỆM THU:** Mở tệp `.env` điền `GEMINI_API_KEY` (hoặc `OPENAI_API_KEY`) để kết nối LLM thật trước khi thực thi `python src/app.py --all`. Bài nộp chỉ dùng Mock Offline Provider sẽ không đạt điểm nghiệm thực tế.

Dưới đây là đoạn trace tiêu biểu của TC04, được trích xuất từ file `docs/trace_waterfall.json` sau khi chạy trên LLM API thật:

```json
[
  {
    "step": 1,
    "query": "Tìm trạm sạc còn cổng DC Fast trống tại Bình Thạnh, sau đó đặt cổng phù hợp lúc 14:00 ngày 15/09/2026 cho xe VF8-12345.",
    "action_type": "TOOL_EXECUTION",
    "tool_name": "charging_station_query",
    "arguments": {
      "location": "Bình Thạnh",
      "datetime_str": "14:00 15/09/2026",
      "connector_type": "DC Fast"
    },
    "observation": {
      "status": "SUCCESS",
      "location": "Bình Thạnh",
      "datetime": "14:00 15/09/2026",
      "stations": [
        {
          "station_id": "ST001",
          "name": "VinFast Landmark 81",
          "location": "Bình Thạnh, TP.HCM",
          "available_connectors": [
            {
              "connector_id": "C01",
              "type": "DC Fast",
              "status": "AVAILABLE"
            }
          ]
        }
      ]
    },
    "latency_ms": 1124.23
  },
  {
    "step": 2,
    "query": "Tìm trạm sạc còn cổng DC Fast trống tại Bình Thạnh, sau đó đặt cổng phù hợp lúc 14:00 ngày 15/09/2026 cho xe VF8-12345.",
    "action_type": "TOOL_EXECUTION",
    "tool_name": "reserve_charging_slot",
    "arguments": {
      "station_id": "ST001",
      "connector_id": "C01",
      "datetime_str": "14:00 15/09/2026",
      "vehicle_id": "VF8-12345"
    },
    "observation": {
      "status": "SUCCESS",
      "reservation_id": "RS-ST001-C01-001",
      "station_id": "ST001",
      "connector_id": "C01",
      "datetime": "14:00 15/09/2026",
      "vehicle_id": "VF8-12345",
      "message": "Đặt trước cổng sạc thành công."
    },
    "latency_ms": 1047.39
  },
  {
    "step": 3,
    "query": "Tìm trạm sạc còn cổng DC Fast trống tại Bình Thạnh, sau đó đặt cổng phù hợp lúc 14:00 ngày 15/09/2026 cho xe VF8-12345.",
    "action_type": "FINAL_ANSWER",
    "thought": "Đã có đủ kết quả từ Tool để trả lời người dùng.",
    "output": "Đặt trước cổng C01 tại trạm ST001 thành công vào lúc 14:00 15/09/2026. Mã đặt chỗ: RS-ST001-C01-001.",
    "latency_ms": 0.0
  }
]
```

---

## 3. TỔNG KẾT KẾT QUẢ NGHIỆM THU & NỘP BÀI

- [x] Đã điền API Key thật trong `.env` và xác nhận Agent chạy mượt mà trên LLM API thật.
- **Tổng số Test Cases đã chạy thành công:** **5 / 5 test cases**.
- **Số lượt gọi Tool qua MCP Server chính xác:** **5 lượt**.
- **Kết quả đẩy Repo nộp bài:** [x] Đã Commit và Push mã nguồn thành công lên GitHub cá nhân.

---

> ✅ **HOÀN TẤT NỘP BÀI:** Sao chép đường link GitHub Repository cá nhân của bạn và dán vào ô nộp bài trên hệ thống LMS VLearn để hoàn tất Bài Lab 3!
