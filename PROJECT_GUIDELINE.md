# Data2Form Pro — Project Guideline

Tài liệu này mô tả cấu trúc và tiêu chuẩn phát triển dựa trên mã nguồn hiện có. Khi implementation và tài liệu mâu thuẫn, hãy kiểm tra code/test hiện hành, xác định hành vi mong muốn rồi cập nhật guideline cùng thay đổi liên quan; không xem guideline là bằng chứng rằng một hành vi đã được triển khai.

## 1. Phạm vi sản phẩm

Data2Form Pro là ứng dụng local-first để ánh xạ dữ liệu workbook Excel vào các biểu mẫu web do người dùng cấu hình. Ứng dụng không gắn với nghiệp vụ hay website cụ thể. Người dùng chịu trách nhiệm kiểm tra selector, quyền truy cập, dữ liệu đầu vào và kết quả lưu ở website đích.

Các luồng hiện có gồm:

- Form đơn và chế độ bảng/lặp tương thích với mapping cũ.
- Mapping plan phiên bản hóa cho một parent form cùng nhiều bảng chi tiết, liên kết bằng khóa parent.
- Upload/preview workbook nhiều sheet, preset theo URL, lịch sử run và trạng thái/log trong lúc chạy.
- Browser Playwright hiển thị để người dùng có thể xử lý các bước đăng nhập/CAPTCHA/OTP cần can thiệp thủ công.

Không cam kết hỗ trợ mọi website, custom widget, cơ chế xác thực hoặc xác nhận lưu dữ liệu. Trạng thái automation hoàn tất chỉ phản ánh tương tác đã chạy theo luồng ứng dụng; luôn xác minh kết quả trên website đích.

## 2. Cấu trúc repository

```text
app.py                    FastAPI app, API routes, middleware và điều phối run
main.py                   Compatibility facade, xuất AutomationStatus và các runner
automation_runtime.py     Trạng thái run và quản lý vòng đời browser/session
single_form_runner.py     Runner cho form đơn/table mode
mapping_plan.py           Kiểm tra mapping plan và workbook parent/detail
mapping_plan_runner.py    Runner cho mapping plan
form_fields.py            Chuẩn hóa/validate field type và áp dụng giá trị
selector_picker.py        Tương tác browser để chọn selector
selector_utils.py         Chuẩn hóa và resolve selector, bao gồm token {row}
workbook_service.py       Upload, lưu, đọc sheet, preview và cache workbook
persistence.py            SQLite persistence cho preset và history
request_security.py       Kiểm tra loopback origin và mutation request
scripts/                  Launcher/process manager local đa nền tảng
frontend/src/              React + TypeScript UI
frontend/dist/             Artifact build của frontend; được tạo, không sửa tay
static/                    Tài nguyên tĩnh dùng chung (ví dụ favicon)
stores/                    Workbook được upload, phân nhóm theo ngày
tests/                     Python unittest suite
```

Các module Python ở root có thể được tách hoặc chuyển vị trí khi kiến trúc thay đổi; cập nhật sơ đồ này cùng thay đổi đó. `main.py` hiện là facade tương thích, không phải nơi đặt logic runner mới.

## 3. Kiến trúc và ranh giới trách nhiệm

### Backend

- `app.py` sở hữu HTTP/API boundary, request/response models, middleware, và điều phối các tác vụ automation.
- `workbook_service.py` xử lý upload/đọc workbook, metadata sheet, cache và preview; không đặt logic UI tại đây.
- `mapping_plan.py` kiểm tra cấu trúc plan, sheet/header/khóa/mapping và chuẩn bị dữ liệu trước khi browser chạy.
- `single_form_runner.py` và `mapping_plan_runner.py` chứa các luồng automation riêng; dùng lại `automation_runtime.py`, `form_fields.py` và `selector_utils.py` thay vì nhân bản logic chung.
- `persistence.py` quản lý truy vấn SQLite cho presets và history. Giữ truy vấn parameterized, đóng connection/resource và bảo toàn dữ liệu/contract hiện có.
- Tác vụ automation hiện chạy đồng bộ trong background thread; không chuyển sang mô hình async hoặc thêm process manager/framework nếu chưa có yêu cầu và đánh giá tương thích.

### Frontend

- Frontend dùng React, TypeScript, Vite, Ant Design và Axios theo `frontend/package.json`.
- Mã ứng dụng nằm trong `frontend/src/`; `frontend/dist/` được FastAPI phục vụ sau khi build.
- Tách API access trong `frontend/src/services/` khỏi component/presentation; dùng type hiện có trong `frontend/src/types/` và pattern của các page/component lân cận.
- Giữ giao diện responsive, truy cập được bằng bàn phím, có trạng thái loading/empty/error rõ ràng và phản hồi phù hợp cho thao tác bất đồng bộ.
- Không đưa cấu hình bí mật, dữ liệu workbook hoặc browser profile vào bundle frontend.

## 4. API, tương thích và persistence

- Trước khi đổi endpoint, request/response field, mapping format hoặc status payload, tìm caller backend/frontend và tests liên quan. Giữ tương thích với preset/mapping cũ nếu có thể; ưu tiên mở rộng có kiểm soát và chuyển đổi từng bước.
- Mapping field hiện hỗ trợ: `text`, `number`, `email`, `textarea`, `select`, `checkbox`, `radio`, `date`, `upload`, `click`; alias legacy `selection` được chuẩn hóa thành `select`. Chỉ cập nhật danh sách này cùng validation, UI, runner và tests.
- Selector lặp hàng dùng token `{row}`. Không suy luận selector theo website hoặc tự đổi selector do người dùng cấu hình ngoài contract đã kiểm thử.
- Mapping plan có version; validate toàn bộ workbook/khóa/mapping trước khi khởi chạy browser. Giữ thứ tự bảng chi tiết theo cấu hình. Parent key phải ổn định, không trống/trùng; khóa chi tiết phải khớp parent.
- SQLite hiện lưu bảng `presets` và `history` trong `automation.db`; mapping/log dạng cấu trúc được serialize JSON. Schema thay đổi phải có kế hoạch nâng cấp dữ liệu và kiểm tra dữ liệu cũ; không âm thầm xóa hoặc đổi nghĩa cột/field legacy.
- `automation.db`, workbook tải lên và browser session là dữ liệu local có thể chứa thông tin nhạy cảm. Không đưa chúng vào Git, log chia sẻ, screenshot công khai hoặc artifact kiểm thử.

## 5. Automation và xử lý lỗi

- Chỉ chạy browser automation trên URL đích do người dùng cấu hình và đã qua kiểm tra phù hợp. Không dùng ứng dụng để vượt CAPTCHA, kiểm soát truy cập hoặc chính sách website; bước cần con người phải được xử lý thủ công.
- Browser mặc định xác thực chứng chỉ TLS; với website dùng chứng chỉ tự ký, hãy cấu hình chứng chỉ tin cậy ở hệ điều hành/browser thay vì tắt xác thực trong ứng dụng.
- Không mặc định coi việc điền field/click/submit là bằng chứng dữ liệu đã được server website lưu. Hiển thị lỗi và trạng thái một cách trung thực; không báo thành công giả khi xác nhận từ website chưa có.
- Khi field hoặc detail row lỗi, dừng theo semantics hiện có và không tiếp tục submit dữ liệu có trạng thái dở dang. Không retry thao tác ghi có thể gây trùng lặp nếu chưa xác định tính idempotent.
- Giữ phân biệt lỗi validate trước browser, lỗi navigation/selector, lỗi field/row và lỗi persist/history; log đủ ngữ cảnh để chẩn đoán nhưng tránh ghi nội dung nhạy cảm từ workbook hoặc trang web.
- Thay đổi selector, field handling, row lifecycle hoặc browser session cần test cho đường đi thành công và lỗi/biên quan trọng.

## 6. Bảo mật và quyền riêng tư

- Ứng dụng hiện hướng tới local development. Middleware giới hạn host/origin loopback và chặn một số mutation cross-site; launcher `scripts/dev.py` cũng chỉ cho phép bind loopback.
- Không expose backend/frontend ra LAN hoặc Internet, không bật remote access, và không xem origin checks là thay thế cho authentication. Remote access cần thiết kế xác thực, authorization, CSRF, network boundary và threat review riêng trước khi triển khai.
- Không ghi secret/password/token, nội dung form đầy đủ, dữ liệu cá nhân hoặc nội dung session vào log. Giới hạn thông tin trả về từ API theo nhu cầu UI.
- Validate file upload, đường dẫn, URL và input tại boundary; dùng API/path handling an toàn và truy vấn SQL parameterized. Khi sửa security boundary, thêm regression tests cho request hợp lệ và request bị từ chối.
- Tôn trọng quyền riêng tư/điều khoản sử dụng của website đích. Không tự động hóa đăng nhập hoặc né biện pháp bảo vệ thay cho người dùng.

## 7. Quy ước code

- Dùng Python theo style và typing đang có; giữ module tập trung một trách nhiệm, tránh thêm abstraction/dependency nếu không có use case cần thiết.
- Frontend viết TypeScript/React theo cấu trúc và lint rules hiện tại; tránh `any` không cần thiết, giữ API type đồng bộ với backend.
- Đặt tên rõ ràng, xử lý exception tại boundary phù hợp, không nuốt lỗi bằng fallback im lặng. Không để debug print, dead code hoặc dữ liệu nhạy cảm trong diff.
- Giữ diff nhỏ theo mục tiêu; không drive-by refactor, thay framework, cập nhật dependency hàng loạt hay thay đổi build/CI/config production ngoài phạm vi yêu cầu.
- Không sửa `frontend/dist/` thủ công. Tạo artifact bằng build command chính thức.

## 8. Kiểm thử và xác minh

### Backend

```bash
python -m unittest discover -s tests -v
```

Test hiện dùng `unittest`; dùng temporary directory/database trong tests cần ghi dữ liệu để tránh tác động `automation.db` hoặc `stores/` thật. Khi sửa logic, chạy test liên quan trước rồi chạy toàn bộ suite nếu môi trường cho phép.

### Frontend

```bash
cd frontend
npm run build
npm run lint
```

Chạy các kiểm tra phù hợp với thay đổi. Nếu dependency/frontend packages chưa được cài, ghi rõ blocker; không tuyên bố kiểm tra thành công khi chưa chạy.

### Runtime và artifact

- Chạy backend trực tiếp: `python -m uvicorn app:app --reload` (sau khi frontend đã build để phục vụ UI tại `/`).
- Phát triển frontend riêng: `npm run dev` trong `frontend/`; Vite proxy API theo cấu hình hiện có.
- Launcher local: `python scripts/dev.py status`, `python scripts/dev.py start`, `python scripts/dev.py stop`; các wrapper theo hệ điều hành nằm trong `scripts/`.
- Trước smoke test, kiểm tra side effects: import `app` hiện gọi `init_db()` và có thể tạo/cập nhật `automation.db`. Dùng DB/workspace cô lập khi test runtime cần bảo toàn dữ liệu người dùng.
- Phân biệt rõ test/build evidence với kiểm tra runtime trên browser và với xác nhận dữ liệu đã được website bên ngoài lưu.

## 9. Hướng dẫn thay đổi

1. Khảo sát pattern hiện có, caller, API contract, test và trạng thái Git trước khi chỉnh sửa.
2. Nêu rõ scope, tiêu chí chấp nhận, rủi ro/side effect và cách xác minh; giữ nguyên thay đổi người dùng đang có.
3. Với behavior change/bug fix, bổ sung test hồi quy trước hoặc cùng thay đổi implementation; không sửa test chỉ để làm xanh.
4. Chạy focused tests rồi các gate liên quan; xem lại diff và trạng thái Git để đảm bảo không có thay đổi ngoài ý muốn.
5. Cập nhật tài liệu khi cấu trúc, contract, lệnh phát triển hoặc giới hạn bảo mật thay đổi.
6. Không commit, push, merge, publish hay sửa dữ liệu thật nếu không được yêu cầu rõ ràng.

## 10. Các giới hạn cần nhớ

- Đây là công cụ automation local, chưa phải dịch vụ multi-user hoặc production-ready cho remote access.
- Browser interaction không đảm bảo thành công với custom control hoặc website thay đổi DOM; người dùng phải kiểm tra trước khi chạy batch.
- Dữ liệu upload/database/browser session nằm trên máy chạy ứng dụng; cần tự quản lý retention, backup và xóa dữ liệu theo nhu cầu.
- Không có bằng chứng chỉ từ log hoặc trạng thái nội bộ rằng website đích đã commit dữ liệu; xác nhận riêng trên trang đích.
