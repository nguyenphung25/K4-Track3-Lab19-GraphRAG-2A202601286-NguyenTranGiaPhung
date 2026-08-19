# Báo cáo Lab 19 — GraphRAG vs Flat RAG

**Học viên:** Nguyễn Trần Gia Phụng

**MSSV:** 2A202601286

**Khóa học:** AICB-K34 · Track 3: GraphRAG

**Ngày thực hiện:** 19/08/2026

> Notebook đã chạy hoàn tất trên 1.500 bản ghi HackerNoon và 3.000 vector chunk. Neo4j giữ graph lab đã ingestion; lần rerun cuối tái sử dụng graph để không tiêu tốn quota extraction. LLM Judge đã hoàn tất 25 câu G5000-26–G5000-50 và hai CSV trong `outputs/` là kết quả chạy thật.

## Phần 1 — Thuyết minh kỹ thuật và phân tích ca lỗi

### 1. Coreference Resolution

Ca khó điển hình: “Microsoft discussed the partnership with OpenAI. The company said it would expand cloud capacity.” Cụm “the company” có thể chỉ Microsoft hoặc OpenAI. Nếu thay sai, extractor có thể tạo `OpenAI-USES->Azure` thay cho phát biểu của Microsoft. Pipeline chỉ thay khi tiền ngữ duy nhất, rõ ràng trong cùng chunk; nếu không giữ nguyên và ghi `unresolved_mentions`. Cách này giảm recall nhưng ngăn false edge lan sang truy vấn nhiều bước.

### 2. Entity Resolution và Lexical Guard

Ngưỡng vector là `0.90`; lexical guard yêu cầu SequenceMatcher sau khi bỏ hậu tố doanh nghiệp đạt `0.72`. `Apple` và `Apple Music` có thể gần nhau về embedding nhưng phải bị từ chối vì một bên là công ty, bên kia là sản phẩm/dịch vụ. `Sam Altman` và `Steve Altman` cũng không được gộp chỉ vì chung họ. Manual alias chỉ dành cho ticker/biến thể đã kiểm chứng; quyết định được audit bằng `MERGE_MANUAL`, `MERGE_VECTOR`, `REJECT_GUARD`.

### 3. Đồ thị và Super-node

Top 3 node đo trực tiếp từ Neo4j sau ingestion:

| Hạng | Thực thể | Type | Degree |
|---:|---|---|---:|
| 1 | Intelligent Technical Solutions | Company | 3 |
| 2 | Zanaris | Company | 1 |
| 3 | EliteSiC | Technology | 1 |

Truy vấn xác nhận:

```cypher
MATCH (n:Entity) OPTIONAL MATCH (n)-[r]-()
RETURN n.name, n.entity_type, count(r) AS degree
ORDER BY degree DESC LIMIT 3
```

Graph hiện có 24 node, 13 edge và 0 edge thiếu provenance; chưa có super-node thực tế. Với degree > 100, hệ thống lấy tối đa 50 cạnh mới nhất; boundary test xác nhận degree 100 không cap còn degree 101/1000 bị cap 50. Ưu điểm là latency/token ổn định và thông tin mới. Rủi ro là mất sự kiện lịch sử; nên lọc theo thời gian trong câu hỏi trước cap hoặc chia cạnh theo relation/time bucket.

### 4. Benchmark và hai ca lỗi

Benchmark LLM-as-a-Judge đã chạy đủ 25 câu. Do graph nhỏ và không chứa các thực thể trong phần lớn golden questions, hai phương pháp thường thiếu evidence; điểm Judge cần được đọc cùng retrieval coverage, không tự nó chứng minh recall cao.

| Tiêu chí | Flat RAG | GraphRAG | Chênh lệch Graph−Flat |
|---|---:|---:|---:|
| Comprehensiveness | 2.28 | 2.24 | -0.04 |
| Faithfulness | 2.44 | 2.56 | +0.12 |
| Multi-hop reasoning | 2.36 | 2.28 | -0.08 |
| Latency trung bình (s) | 7.646 | 6.316 | -1.330 |
| Token trung bình | 1218.16 | 1059.08 | -159.08 |

Flat RAG dễ thất bại ở G02: “former OpenAI employees founded Anthropic” và “Google invested in Anthropic” thường ở hai chunk. Top-k có thể chỉ lấy một nửa chuỗi. GraphRAG có thể nối `Person-FOUNDED->Anthropic<-INVESTED_IN-Google`, giữ provenance từng cạnh.

GraphRAG khó ở G05 nếu extraction bỏ sót cạnh lịch sử, seed resolver bỏ alias, hoặc temporal cap loại bài cũ. Vector context khi đó có thể đầy đủ hơn. Khắc phục: audit extraction, kiểm tra seed, lọc thời gian, tăng hop có điều kiện và vector fallback.

### 5. Trade-off, agent control và scale 350 MB

Flat RAG ingestion đơn giản, latency thấp, hợp factoid nhưng ngữ cảnh dễ phân mảnh. GraphRAG tốn LLM extraction, entity resolution và Neo4j nhưng biểu diễn rõ chuỗi quan hệ/provenance.

Tôi từ chối so sánh cosine toàn cặp O(N²) vì dễ OOM. Pipeline dùng FAISS sinh candidate rồi lexical guard và Union-Find. Ở 350 MB, bottleneck đầu tiên là LLM extraction, sau đó entity resolution và ghi DB. Giải pháp: cache theo content hash, queue bất đồng bộ có retry/idempotency, batch `UNWIND`, ANN blocking theo type, checkpoint theo chunk và community partitioning.

## Phần 2 — Reflection và action plan

### 1. Mapping bài giảng vào code

| Khái niệm | Module | Hàm/khối code | Quan sát |
|---|---|---|---|
| Conservative Coreference | M1 | `resolve_coref_batch`, `run_coref` | Fallback giữ text và log lỗi |
| Schema allowlist | M2 | `ALLOWED_NODE_TYPES`, `ALLOWED_RELATIONS` | Loại type/relation ngoài schema |
| Bulk Cypher | M2 | `bulk_insert_nodes`, `bulk_insert_edges` | `UNWIND`, batch 1000 |
| Entity Resolution | M3 | `build_resolution_map`, `merge_guard`, `UF` | ANN → guard → union |
| Flat Retrieval | M4 | `build_flat_index`, `retrieve_flat_context` | FAISS IP, top-k |
| Super-node cap | M4 | `retrieve_graph_context`, `recent_edges` | 50/node, 250/global |
| LLM Judge | M5 | `judge_answer`, `run_evaluation` | 3 tiêu chí và rationale |
| Self-correction | Bonus | `self_correcting_context` | hop 2 → hop 3 → vector |

### 2. Debugging và bài học

Khó nhất là phân biệt “embedding giống” với “cùng thực thể”. Chỉ tăng threshold không xử lý được product/company hay người trùng họ. Giải pháp là blocking theo type, chuẩn hóa có kiểm soát, alias map nhỏ, lexical guard và audit. Entity resolution phải giải thích/rollback được; một false merge thường nguy hiểm hơn vài false negative.

### 3. Action plan đồ án

Đồ án: trợ lý tra cứu hồ sơ dự án và nhân sự nội bộ. Hybrid GraphRAG phù hợp vì câu hỏi nối người–dự án–khách hàng–công nghệ qua nhiều tài liệu; Flat RAG vẫn dùng cho mô tả dài.

- Nodes: `Person`, `Team`, `Project`, `Client`, `Technology`, `Document`.
- Relations: `MEMBER_OF`, `WORKED_ON`, `OWNED_BY`, `USES`, `DELIVERED_TO`, `MENTIONED_IN`.
- Resolution: mã nhân viên/project là khóa mạnh; email/mã CRM là alias; embedding chỉ sinh candidate với type/lexical guard.
- Super-node: giới hạn `Technology` phổ biến theo thời gian, relation và ACL; ưu tiên cạnh liên quan seed.
- Governance: mọi cạnh có `source_chunk_id`, `published_date`, `evidence`, `confidence`; ACL lọc trước traversal.

## Tự đánh giá

| Tiêu chí | Điểm | Ghi chú |
|---|---:|---|
| Hiểu GraphRAG | 4/5 | Nắm pipeline và failure modes |
| Kiểm soát AI Coding Agent | 4/5 | Không chấp nhận O(N²) hay số liệu giả |
| Chất lượng đồ thị | 3/5 | Cần chạy dữ liệu thật để xác nhận |
| Phân tích/debug | 4/5 | Có audit, provenance và fallback |

## Checklist chạy cuối

1. Tạo `.env`, điền secrets và nạp biến môi trường.
2. Restart & Run All; xác nhận `invalid_provenance_edges == 0`.
3. Audit đã có 10 dòng, gắn scope rõ; boundary test super-node đã pass.
4. Evaluation 25/25 đã ghi đè CSV và bảng benchmark đã cập nhật bằng số thật.
