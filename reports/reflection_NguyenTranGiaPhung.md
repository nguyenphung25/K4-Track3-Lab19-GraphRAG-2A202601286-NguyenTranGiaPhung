# Reflection và Action Plan — Nguyễn Trần Gia Phụng

**MSSV:** 2A202601286

## Mapping bài giảng vào code

| Khái niệm | Module | Hàm/khối code | Bài học |
|---|---|---|---|
| Exact dedup/chunking | M1 | `standardize_news`, `chunk_text`, `build_chunks` | Hash chính xác rẻ nhưng không bắt near-duplicate |
| Conservative coreference | M1 | `resolve_coref_batch`, `run_coref` | False edge nguy hiểm hơn giảm recall |
| Schema allowlist | M2 | `ALLOWED_NODE_TYPES`, `ALLOWED_RELATIONS` | Validation phải diễn ra trước ingestion |
| Entity resolution | M3 | `build_resolution_map`, `merge_guard`, `UF` | ANN sinh candidate, guard quyết định merge |
| Bulk ingestion | M2/M3 | `bulk_insert_nodes`, `bulk_insert_edges` | `UNWIND` giảm round-trip và hỗ trợ retry |
| Flat retrieval | M4 | `build_flat_index`, `retrieve_flat_context` | Nhanh nhưng không biểu diễn chuỗi quan hệ |
| Graph traversal | M4 | `retrieve_graph_context`, `textualize` | BFS cần degree/global/context cap |
| Evaluation | M5 | `judge_answer`, `run_evaluation` | Cần checkpoint, rationale và phân nhóm |
| Self-correction | Bonus | `self_correcting_context` | Hop 2 → hop 3 → vector fallback |

## Lỗi khó nhất và cách xử lý

Lỗi khó nhất không phải cú pháp mà là sự kết hợp giữa schema dữ liệu thực tế và quota dịch vụ. HackerNoon dùng `description`, không có cột `text`; loader ban đầu thất bại. Sau khi sửa schema, Groq trả 429 khi extraction/evaluation dài. Tôi xử lý bằng cách đọc schema trước, giữ DataFrame rỗng đúng cột, checkpoint theo question ID, resume, adaptive backoff và giảm concurrency để tuân thủ TPM.

Bài học chính là pipeline production phải thiết kế cho partial failure. Một notebook chỉ chạy được khi mọi API hoàn hảo chưa phải pipeline có thể vận hành.

## Action plan đồ án

Đồ án đề xuất là trợ lý tra cứu hồ sơ dự án và nhân sự nội bộ. Hybrid GraphRAG phù hợp vì câu hỏi thường nối người–team–dự án–khách hàng–công nghệ, trong khi mô tả dài vẫn cần vector retrieval.

- Nodes: `Person`, `Team`, `Project`, `Client`, `Technology`, `Document`.
- Relations: `MEMBER_OF`, `WORKED_ON`, `OWNED_BY`, `USES`, `DELIVERED_TO`, `MENTIONED_IN`.
- Entity keys: employee ID, project ID và CRM ID là khóa mạnh; email/tên viết tắt là alias.
- Resolution: blocking theo type, ANN candidate, lexical guard và manual review cho merge confidence trung bình.
- Super-node: cap theo ACL, time range và relation bucket; không chỉ lấy cạnh mới nhất một cách cố định.
- Governance: mọi edge có source, date, evidence, confidence; ACL được áp dụng trước traversal.

## Việc sẽ cải tiến

1. Chạy extraction trên đủ dữ liệu first5000 khi quota cho phép.
2. Hoàn tất 25/25 golden questions từ checkpoint.
3. Thêm near-dedup bằng MinHash/SimHash.
4. Đánh giá retrieval coverage riêng, không chỉ dựa vào LLM Judge.
5. Thêm dashboard theo dõi rate limit, lỗi batch và provenance integrity.
