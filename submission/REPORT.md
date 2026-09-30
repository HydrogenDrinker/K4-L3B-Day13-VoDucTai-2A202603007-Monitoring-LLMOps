# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:** Võ Đức Tài
- **MSSV:** 2A202603007
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/HydrogenDrinker/K4-L3B-Day13-VoDucTai-2A202603007-Monitoring-LLMOps
- **Commit SHA cuối:** 9cf04d42f7bca61ccb8ecd6b995c62f0aa188af7
- **Challenge ID:** day13-k4-l3b-monitoring-llmops-v1
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202603007`

## 2. Evidence index

Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/pytest.txt` |
| Log validator | `evidence/log-validator.txt` |
| Dashboard validator | `evidence/dashboard-validator.txt` |
| Structured log + incident log | `evidence/01-incident-log.png` |
| Trace list | `evidence/02-trace-list.png` |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png` |
| Prompt versions + promote/rollback | `evidence/04-prompt-versioning.png` |
| Dashboard + incident metric | `evidence/05-dashboard-incident.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 20/100 | 100/100 | Đạt chuẩn 100/100 tuyệt đối sau khi enrich context, bind correlation ID và scrub PII |
| `validate_dashboard.py` | 6/6 panel | 6/6 panel | Hợp lệ toàn bộ 6/6 panel theo dashboard contract trong config/dashboard.yaml |
| `pytest` | 16 passed | 22 passed | Hoàn thành và vượt qua 22/22 unit tests |
| Số traces hợp lệ | 0 | 44 | Đã tạo 44 traces thực tế ghi nhận trên project Langfuse cá nhân (vượt xa mốc tối thiểu 10) |
| Số PII leak | 3 | 0 | Không còn rò rỉ email, số điện thoại, CCCD, credit card trong log |
| Latency P95 / TTFT P95 | 165ms / 50ms | 14,695ms / 50ms | Phản ánh rõ nét latency spike trong đợt challenge do incident rag_slow |
| Retrieval success rate | 100% | 100% | Tỷ lệ truy vấn ngữ cảnh thành công đạt 100% |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  Được cài đặt trong `CorrelationIdMiddleware` (`app/middleware.py`). Với mỗi request HTTP đi vào, middleware gọi `clear_contextvars()` để dọn dẹp context rò rỉ từ request trước, kiểm tra header `x-request-id` của client (nếu không có thì tự sinh chuỗi chuẩn `req-<8-hex>` thông qua `uuid.uuid4().hex[:8]`), sau đó gọi `bind_contextvars(correlation_id=correlation_id)` và lưu vào `request.state.correlation_id`. Khi trả về response, middleware gắn correlation ID vào header `x-request-id` và thời gian thực thi vào header `x-response-time-ms`.
- **Các metadata được ghi vào structured log:**
  Log toàn cục chứa: `ts` (ISO 8601 UTC), `level` (INFO/ERROR), `service` ("api"), `event` (`request_received`, `response_sent`, `request_failed`), và `correlation_id`. Tại endpoint `/chat`, log được enrich thêm: `user_id_hash` (SHA-256 tóm tắt 12 ký tự), `session_id`, `feature`, `model`, và `env`. Với event `response_sent`, log ghi chi tiết: `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success` và `payload.answer_preview`.
- **Cách bảo đảm PII được scrub trước khi ghi:**
  Processor `scrub_event` trong `app/logging_config.py` được đăng ký vào danh sách structlog processors trước khi dữ liệu được chuyển đến `JsonlFileProcessor()` và `JSONRenderer()`. `scrub_event` duyệt đệ quy qua các cấu trúc dữ liệu, sử dụng bộ mẫu regex trong `app/pii.py` (`credit_card`, `cccd`, `email`, `phone_vn`, `passport`) để thay thế thông tin nhạy cảm bằng nhãn `[REDACTED_<TYPE>]`.
- **Cách kiểm chứng kết quả:**
  Chạy `python scripts/validate_logs.py` kiểm tra toàn bộ file `data/logs.jsonl` đạt điểm 100/100, xác nhận không có bản ghi nào bị thiếu trường bắt buộc, không thiếu ngữ cảnh và số PII leak phát hiện bằng 0.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  Trong file `.env`, khóa `LANGFUSE_PUBLIC_KEY` và `LANGFUSE_SECRET_KEY` được liên kết trực tiếp với project cá nhân mang tên `day13-k4-l3b-2A202603007`. Các trace xuất hiện trên UI Langfuse mang đúng tên project, tags chứa thông tin bài lab, và trường metadata chứa correlation ID trùng khớp với file `data/logs.jsonl` cục bộ.
- **Cấu trúc root/retrieval/generation observations:**
  Trace gốc mang tên `day13-agent-request` với root observation `lab-agent-run` (type `agent`). Dưới root observation, hệ thống phân rã thành hai child observations chuẩn Langfuse SDK v4:
  1. `retrieval` (type `retriever`): đo thời gian tìm kiếm tài liệu context, ghi nhận metadata `doc_count` và `query_preview`.
  2. `generation` (type `generation`): ghi nhận lệnh gọi mô hình sinh văn bản, ghi lại `model`, `usage` (input, output, total tokens), `cost_usd`, `ttft_ms` và liên kết với prompt version.
- **Cách nối trace với log:**
  Trong `app/agent.py`, `correlation_id` được trích xuất từ `request.state.correlation_id` và đưa vào `propagate_attributes(metadata={"correlation_id": correlation_id})`. Nhờ vậy, mỗi trace trên Langfuse có trường `correlation_id` ánh xạ 1-1 với `correlation_id` trong từng dòng structured log.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1 (v1), được gắn label `baseline` và `production` ban đầu.
- **Version/label candidate:** Version 2 (v2), được gắn label `candidate` (với ràng buộc câu trả lời ngắn gọn xúc tích và giữ nguyên 3 biến `feature`, `docs`, `message`).
- **Trace ID của mỗi version:**
  - Baseline v1: Ghi nhận trong trace list với `prompt_version=1`, `prompt_label=baseline`.
  - Candidate v2: `7926f93a04a60273b27191acc79ea8b0` (ghi nhận `prompt_version=2`, `prompt_label=production` trước khi rollback).
- **Cách promote và rollback `production`:**
  - Promote: Trên Langfuse Prompt Management, chuyển label `production` trỏ vào version 2 để hệ thống chuyển sang dùng prompt mới.
  - Rollback: Khi phát hiện prompt mới gây latency cao hoặc giảm quality proxy, ta chuyển nhãn `production` từ version 2 quay trở lại version 1 trực tiếp trên giao diện Langfuse mà không cần thay đổi source code hay khởi động lại app.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  Hệ thống cấu hình 6 panel chuẩn theo `config/dashboard.yaml` và hiển thị trực tiếp tại `http://127.0.0.1:8000/dashboard`:
  1. Latency: Percentiles P50, P95, P99 và TTFT P95.
  2. Traffic: Lưu lượng request theo phút và tổng số request đã tiếp nhận.
  3. Errors: Tỷ lệ lỗi (Error rate %) và tỷ lệ retrieval thành công (Retrieval success rate %).
  4. Cost: Tổng chi phí ($ USD) và biến thiên chi phí theo thời gian.
  5. Tokens: Tổng số lượng input tokens và output tokens.
  6. Quality: Điểm đánh giá chất lượng trung bình `quality_score` (0.0 đến 1.0).
- **SLO và lý do chọn:**
  SLO chính: `fast_successful_requests` với mục tiêu 99.5% request hoàn thành thành công và có `latency_ms <= 3000ms` trong cửa sổ 28 ngày. Lý do: Đối với AI API phục vụ người dùng thực tế, độ trễ vượt quá 3 giây gây suy giảm đáng kể trải nghiệm tương tác, và tỷ lệ thành công 99.5% là tiêu chuẩn tin cậy cho dịch vụ phụ trợ quan trọng.
- **Cách tính error budget:**
  Với SLO 99.5% trong 28 ngày, error budget cho phép là `0.5%`. Nếu hệ thống tiếp nhận 10,000 requests trong cửa sổ đó thì tối đa 50 requests được phép bị lỗi hoặc có độ trễ lớn hơn 3000ms.
- **Ba alert và runbook tương ứng:**
  1. `HighLatencyP95` (Warning, `p95(latency_ms) > 3000ms` trong 5 phút, owner `student-2A202603007`): Phát hiện chậm đuôi. Runbook: `docs/alerts.md#alert-1`.
  2. `HighErrorRate` (Critical, `error_rate_pct > 2%` trong 3 phút, owner `student-2A202603007`): Phát hiện lỗi dịch vụ tăng cao. Runbook: `docs/alerts.md#alert-2`.
  3. `LowRetrievalSuccess` (Warning, `tool_success_rate_pct < 90%` trong 5 phút, owner `student-2A202603007`): Phát hiện lỗi vector store/RAG. Runbook: `docs/alerts.md#alert-3`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 2026-09-30 07:56:00Z - 07:57:00Z (khoảng 14:56 - 14:57 giờ VN)
- **Triệu chứng từ metrics:** Dashboard và metrics ghi nhận độ trễ P95 tăng vọt bất thường (vượt xa ngưỡng SLO 3000ms, request latency đo được lên tới ~8529ms - 14455ms khi chịu tải concurrent). Trong khi đó, TTFT vẫn giữ nguyên 50ms, số token và chi phí không có dấu hiệu tăng vọt, chỉ ra rằng độ trễ bắt nguồn từ thành phần ngoài mô hình LLM.
- **Log line và correlation ID liên quan:**
  Dòng log đại diện:
  `{"service": "api", "latency_ms": 2966, "ttft_ms": 50, "tokens_in": 35, "tokens_out": 116, "cost_usd": 0.001845, "quality_score": 0.8, "tool_name": "retrieval", "tool_success": true, "payload": {"answer_preview": "Starter answer. You should improve this output logic and add better quality chec..."}, "event": "response_sent", "user_id_hash": "4a1a454d70a9", "feature": "monitoring", "env": "dev", "model": "claude-sonnet-4-5", "correlation_id": "req-4e8caebb", "session_id": "k4-l3b-challenge-s01", "level": "info", "ts": "2026-09-30T07:56:43.424533Z"}`
  `correlation_id`: `req-4e8caebb`
- **Trace ID và span gây ảnh hưởng:**
  Trace cùng `correlation_id` (`req-4e8caebb`). Khi mở waterfall span tree trên Langfuse, span `retrieval` bị nghẽn (chiếm hơn 2.5s do `rag_slow`), trong khi span `generation` chỉ mất ~150ms.
- **Root cause:**
  Sự cố `rag_slow` được kích hoạt trên hệ thống, làm cho hàm `retrieve()` trong RAG module bị trễ nghiêm trọng khi xử lý các truy vấn liên quan đến feature `monitoring`.
- **Fix action:**
  Vô hiệu hóa sự cố bằng lệnh `python scripts/inject_incident.py --disable` (endpoint `/incidents/rag_slow/disable`), khôi phục trạng thái hoạt động bình thường của retrieval layer.
- **Preventive measure:**
  1. Cấu hình timeout tối đa 2000ms cho bước retrieval kèm circuit breaker để trả về fallback context thay vì để toàn bộ request bị trễ.
  2. Bật cảnh báo `HighLatencyP95` theo `docs/alerts.md#alert-1` để thông báo qua Slack ngay khi độ trễ P95 vượt 3000ms quá 5 phút.
  3. Thêm integration test kiểm tra hiệu năng retrieval định kỳ trong CI/CD.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  Tách các bước trong `LabAgent` thành hai child observations độc lập (`retrieval` và `generation`) và gắn correlation ID vào trace metadata. Điều này giúp loại bỏ hoàn toàn việc phỏng đoán nguyên nhân khi xảy ra sự cố, cho phép phân biệt rạch ròi giữa việc downstream service (RAG) bị chậm hay do model LLM sinh token chậm.
- **Một lỗi/blocker đã gặp:**
  Xung đột port 8000 do tiến trình nền cũ còn giữ socket và lỗi mã hóa ký tự UTF-8 (mojibake) trên Windows PowerShell khi redirect output ra file `.txt`.
- **Cách tìm nguyên nhân và xử lý:**
  Sử dụng `Get-NetTCPConnection` để phát hiện PID chiếm dụng port 8000 và dừng tiến trình triệt để; sử dụng script Python ghi file dưới dạng binary UTF-8 sạch để đảm bảo các file evidence text không bị lỗi font tiếng Việt.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  Metrics là lớp tín hiệu đầu tiên giúp phát hiện triệu chứng và thời điểm xảy ra sự cố; Logs giúp khoanh vùng và lấy mã `correlation_id` của request cụ thể bị ảnh hưởng; Traces cho phép phóng đại vào request đó để xem từng span con và xác định chính xác bước nào là nguyên nhân gốc rễ.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  Prompt là cấu hình logic quan trọng nhất của ứng dụng GenAI. Việc quản lý prompt theo phiên bản và nhãn (`baseline`, `candidate`, `production`) cho phép kiểm soát chặt chẽ token, chi phí và chất lượng câu trả lời, đồng thời đảm bảo khả năng rollback tức thời khi prompt mới gây hồi quy (regression) mà không cần can thiệp vào code hay hạ tầng.
- **Điều quan trọng nhất đã học:**
  Nắm vững quy trình vận hành và giám sát ứng dụng AI (LLMOps) theo chuẩn công nghiệp, bảo vệ quyền riêng tư người dùng thông qua PII scrubbing và thiết lập chuỗi bằng chứng có thể kiểm chứng được từ Metrics đến Traces.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  Hiện tại ứng dụng sử dụng mock RAG và fake LLM để phục vụ mục đích học tập; trong tương lai cần kết nối tới vector database phân tán thực tế và mô hình LLM production đa vùng.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
