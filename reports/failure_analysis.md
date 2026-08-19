# Failure Analysis — Flat RAG và GraphRAG

**Học viên:** Nguyễn Trần Gia Phụng
**MSSV:** 2A202601286

## Phạm vi thực nghiệm

Pipeline đã chạy 1.500 bản ghi HackerNoon, tối đa 3.000 vector chunk và sample extraction 12 chunk do quota Groq. Neo4j có 4 node, 2 edge và 0 edge thiếu provenance. Vì graph nhỏ, phân tích dưới đây tách rõ kết quả quan sát với failure mode kiến trúc dự kiến.

## Ca 1 — Flat RAG không nối được evidence multi-hop

- Triệu chứng: câu hỏi yêu cầu quan hệ A→B→C nhưng top-k chỉ chứa một trong hai quan hệ.
- Root cause: semantic search xếp hạng từng chunk độc lập; chunk trung gian có thể không chứa từ khóa của câu hỏi.
- Ảnh hưởng: câu trả lời thiếu một điều kiện hoặc kết luận dựa trên liên tưởng thay vì evidence.
- Cách phát hiện: đối chiếu `retrieved` với `reference_evidence`, kiểm tra cả hai source chunk có nằm trong top-k không.
- Mitigation: resolve seed entity, BFS hai hop, linearize từng edge kèm chunk/date/evidence; giữ vector fallback.

## Ca 2 — GraphRAG thiếu cạnh do extraction

- Triệu chứng: vector context có câu chứa sự kiện nhưng graph traversal không trả relation tương ứng.
- Root cause: input chỉ có trường `description`, sample extraction nhỏ, LLM có thể trả JSON rỗng hoặc relation ngoài allowlist.
- Ảnh hưởng: seed hợp lệ nhưng subgraph rỗng; GraphRAG không hơn Flat RAG.
- Cách phát hiện: kiểm tra `extraction_errors_df`, so sánh raw chunk với `raw_triples_df`, thống kê relation bị loại.
- Mitigation: cache theo chunk, retry có backoff theo 429, schema-preserving empty DataFrame, tăng sample khi quota phục hồi và kiểm thử extraction trên bộ nhãn nhỏ.

## Ca 3 — Rate limit làm evaluation không hoàn tất

- Triệu chứng: Groq trả 429 TPM/TPD; chạy song song làm TPM tăng nhanh.
- Root cause: mỗi golden question cần seed extraction, hai answer và hai judge; 25 câu tạo hơn 100 lượt gọi.
- Ảnh hưởng: notebook crash nếu không checkpoint; CSV cuối có thể chỉ phản ánh một phần dataset.
- Mitigation đã áp dụng: checkpoint theo ID, resume chỉ câu chưa chạy, model fallback, đọc `try again in ...s`, giới hạn một worker. Chỉ xuất báo cáo cuối khi checkpoint đủ 25 ID.

## Ca 4 — Super-node temporal cap làm mất evidence lịch sử

- Triệu chứng dự kiến: câu hỏi về sự kiện cũ không tìm thấy cạnh dù cạnh tồn tại trong graph.
- Root cause: chính sách ưu tiên 50 cạnh mới nhất tại node degree > 100.
- Mitigation: parse khoảng thời gian từ query, lọc temporal trước cap; dành quota theo relation type; fallback vector hoặc hop 3 khi context-sufficiency check thất bại.

## Kết luận

GraphRAG không tự động tốt hơn Flat RAG. Chất lượng phụ thuộc coverage extraction, entity resolution và chính sách traversal. Hệ thống production cần provenance, audit, checkpoint và hybrid fallback; điểm judge phải được đọc cùng retrieval coverage, latency và token usage.
