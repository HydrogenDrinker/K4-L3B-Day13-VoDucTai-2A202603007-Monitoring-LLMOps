# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Latency P95 của `response_sent.latency_ms` (SLO ≤ 3000ms)
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng phải chờ lâu hơn bình thường trước khi nhận được phản hồi từ AI.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Latency để xác định giá trị P50/P95/P99 và thời điểm bắt đầu tăng đột biến.
  2. Lọc `data/logs.jsonl` trong khung giờ đó, tìm các log `response_sent` có `latency_ms > 3000` và trích xuất `correlation_id`.
  3. Mở Langfuse trace tương ứng với `correlation_id` đó để kiểm tra span tree (so sánh duration giữa `retrieval` và `generation`).
- Mitigation tạm thời: Nếu do prompt mới làm tăng token/latency, thực hiện rollback prompt về version cũ; nếu do downstream/RAG bị nghẽn (như incident `rag_slow`), vô hiệu hóa hoặc chuyển sang fallback context.
- Owner: `student-2A202603007`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `3m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Error rate của dịch vụ (`request_failed` / `request_received`)
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` liên tục trong 3 phút
- Ảnh hưởng tới người dùng: Người dùng gặp lỗi 500 hoặc không nhận được câu trả lời từ hệ thống.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Errors để xem biểu đồ tỷ lệ lỗi và danh sách `error_type` phổ biến nhất.
  2. Lọc `data/logs.jsonl` tìm các event `request_failed`, ghi nhận `error_type`, exception detail và `correlation_id`.
  3. Mở Langfuse trace để xác định bước nào kích hoạt ngoại lệ (ví dụ: vector database timeout, LLM rate limit, invalid prompt).
- Mitigation tạm thời: Kích hoạt circuit breaker / fallback responses cho người dùng; khởi động lại service hoặc rollback deployment/prompt gần nhất; liên hệ team phụ trách dependency bị lỗi.
- Owner: `student-2A202603007`

## Alert 3

- Tên: `LowRetrievalSuccess`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Tỷ lệ truy vấn tài liệu thành công (`tool_success == true` / `tool_success != null`)
- Điều kiện và thời gian duy trì: `tool_success_rate_pct < 90%` trong 5 phút
- Ảnh hưởng tới người dùng: Chất lượng câu trả lời bị suy giảm, hệ thống phải dùng câu trả lời chung chung hoặc fallback do thiếu thông tin ngữ cảnh.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Errors/Retrieval kiểm tra xu hướng tỷ lệ `tool_success`.
  2. Kiểm tra log `data/logs.jsonl` các dòng có `tool_name="retrieval"` và `tool_success=false`.
  3. Mở Langfuse trace, kiểm tra span `retrieval` để xem metadata `doc_count` và lỗi timeout/kết nối đến vector store.
- Mitigation tạm thời: Chuyển hướng truy vấn sang cụm vector search dự phòng (failover replica) hoặc bật bộ nhớ đệm (cache) cho các câu hỏi phổ biến.
- Owner: `student-2A202603007`
