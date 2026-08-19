# Thuyết minh kỹ thuật — Lab 19 GraphRAG vs Flat RAG

**Học viên:** Nguyễn Trần Gia Phụng
**MSSV:** 2A202601286
**Ngày:** 19/08/2026

## 1. Vì sao dùng conservative coreference?

Coreference sai tạo false edge, nguy hiểm hơn việc bỏ sót một cạnh. Ví dụ “Microsoft discussed its partnership with OpenAI. The company expanded cloud capacity” có hai tiền ngữ hợp lý. Pipeline chỉ thay đại từ khi tiền ngữ duy nhất xuất hiện trong cùng chunk; nếu mơ hồ thì giữ nguyên và ghi `unresolved_mentions`.

## 2. Coreference failure ảnh hưởng graph thế nào?

Nếu “the company” bị gán thành OpenAI thay vì Microsoft, extractor có thể tạo `OpenAI-USES->Azure`. Cạnh sai sau đó xuất hiện trong mọi traversal qua OpenAI, làm giảm faithfulness và có thể tạo kết luận multi-hop sai. Biện pháp là lưu evidence, confidence, source chunk và audit các mention chưa phân giải.

## 3. Ngưỡng Entity Resolution được chọn thế nào?

Vector candidate threshold là `0.90`; lexical guard yêu cầu SequenceMatcher sau khi bỏ hậu tố doanh nghiệp đạt `0.72`. Threshold cao ưu tiên precision vì false merge có phạm vi ảnh hưởng lớn. ANN chỉ sinh candidate, không tự quyết định merge.

## 4. Ví dụ Lexical Guard chặn merge

`Apple` và `Apple Music` có thể gần về embedding nhưng không phải cùng thực thể; `Sam Altman` và `Steve Altman` cũng không được gộp vì chỉ chung họ. Pipeline còn blocking theo entity type, nên Company không merge với Technology/Person. Quyết định được ghi `MERGE_MANUAL`, `MERGE_VECTOR` hoặc `REJECT_GUARD`.

## 5. Vì sao ingestion dùng UNWIND?

Insert từng row tạo nhiều round-trip và transaction nhỏ. `UNWIND $rows AS row` với batch 1.000 giảm network overhead, cho phép retry theo batch và giữ thao tác idempotent bằng `MERGE`. Constraint `Entity.id` ngăn node trùng; index `name_norm` hỗ trợ seed matching.

## 6. Provenance được bảo đảm ra sao?

Mỗi edge có `source_chunk_id`, `published_date`, `evidence`, `confidence`. Hàm ingestion từ chối DataFrame thiếu cột provenance. Kiểm tra Neo4j thực tế cho kết quả 0 edge thiếu `source_chunk_id` hoặc `published_date`.

## 7. Super-node mitigation hoạt động thế nào?

Node degree > 100 chỉ lấy tối đa 50 cạnh mới nhất. Toàn traversal bị chặn ở 250 cạnh và graph context ở 14.000 ký tự. Ưu điểm là latency/token ổn định; rủi ro là loại mất sự kiện cũ. Với câu hỏi lịch sử nên lọc time range trước cap hoặc lấy mẫu theo relation/time bucket. Graph sample hiện tại chưa có node degree > 100, nên chính sách được kiểm tra bằng test deterministic thay vì tuyên bố có super-node thật.

## 8. Flat RAG và GraphRAG thất bại ở đâu?

Flat RAG thất bại khi hai nửa của chuỗi suy luận nằm ở hai chunk có độ tương đồng riêng lẻ thấp. GraphRAG có thể nối các cạnh qua entity chung. Ngược lại, GraphRAG thất bại khi NER/RE bỏ cạnh, seed không resolve hoặc temporal cap cắt evidence; hybrid vector fallback giảm rủi ro này.

## 9. Benchmark được diễn giải thế nào?

Benchmark 5 câu ban đầu cho Flat/Graph cùng comprehensiveness 4.20, faithfulness 5.00 và multi-hop 4.20. Flat latency 9.367 giây, Graph 10.300 giây; token trung bình lần lượt 1708.0 và 1499.4. Điểm faithfulness cao chủ yếu vì mô hình trung thực nói thiếu evidence, không chứng minh recall cao. Bộ golden first5000 gồm 25 câu đang chạy bằng checkpoint; không thay số liệu báo cáo cho đến khi đủ 25/25.

## 10. Trade-off, agent control và scale 350 MB

Flat RAG rẻ, đơn giản và hợp factoid; GraphRAG tốn extraction/entity resolution/DB nhưng mạnh ở multi-hop và provenance. Tôi từ chối pairwise cosine O(N²), dùng FAISS candidate search + lexical guard + Union-Find. Khi scale 350 MB, kiến trúc cần content-hash cache, queue async có retry/idempotency, batch `UNWIND`, ANN blocking theo type, checkpoint theo chunk, rate limiter và community partitioning.
