# 🏛️ Data2Form Pro
**Công cụ ánh xạ dữ liệu Excel vào các biểu mẫu web phổ thông.**

Data2Form Pro giúp ánh xạ từng cột Excel vào các control trên nhiều loại website, xem trước dữ liệu, lưu preset theo URL và theo dõi lỗi đến từng dòng. Việc tương tác được cấu hình bằng selector và loại control thay vì phụ thuộc vào một hệ thống nghiệp vụ cụ thể.

---

## ✨ Tính năng nổi bật

- 📊 **Xử lý Excel thông minh**: Tự động đọc và ánh xạ các cột từ Excel vào các trường trên website.
- 🤖 **Lõi Playwright tổng quát**: Hỗ trợ input text/number/email, textarea, native/custom select, checkbox, radio, date và upload file; có thể tự nhận diện nhiều HTML control phổ biến khi mapping dùng loại Text.
- 🎨 **Giao diện Contemporary**: Thiết kế theo phong cách Glassmorphism hiện đại, trực quan và dễ sử dụng.
- 💾 **Hệ thống Preset**: Tự động ghi nhớ cấu hình selector cho từng trang web, không cần cấu hình lại nhiều lần.
- 📜 **Lịch sử & Logs**: Theo dõi tiến trình chạy thời gian thực, lưu lại lịch sử thực thi kèm log chi tiết.
- ✅ **Kiểm tra trước khi chạy**: Phát hiện mapping thiếu selector, cột Excel không tồn tại và cấu hình chưa hoàn chỉnh.
- 📋 **Kết quả từng dòng**: Hiển thị trạng thái và field lỗi riêng cho từng dòng; không chạy nút Submit/Lưu của dòng khi đã phát hiện lỗi field.
- 🧩 **Ánh xạ tổng quát**: Selector do người dùng cấu hình; chế độ lặp hàng hỗ trợ token `{row}` để trỏ tới dòng hiện tại.


---

## 🛠️ Công nghệ sử dụng

- **Backend**: Python 3.10+, FastAPI.
- **Automation Core**: Playwright (Synchronous engine).
- **Data Processing**: Pandas (Excel handling).
- **Database**: SQLite (Persistence for presets & history).
- **Frontend**: React 19, TypeScript, Vite.
- **UI Component Library**: Ant Design v6 (`antd`), `@ant-design/icons`.
- **Layout Architecture**: Split-View Workspace, realtime execution monitor, and run history.

---

## 🚀 Hướng dẫn cài đặt & Khởi chạy

### 1. Clone dự án
```bash
git clone https://github.com/HuyTinh/data2form.git
cd data2form
```

### 2. Thiết lập môi trường ảo Backend
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 3. Cài đặt thư viện Backend
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Build giao diện React
`frontend/dist` không được lưu trong source control, vì vậy cần build giao diện sau khi clone. Cài Node.js/npm trước, sau đó chạy:
```bash
cd frontend
npm install
npm run build
cd ..
```

### 5. Chạy ứng dụng
```bash
python -m uvicorn app:app --reload
```
Sau đó mở trình duyệt truy cập: `http://127.0.0.1:8000`

### 6. Phát triển Frontend (Development Mode - Tùy chọn)
Nếu bạn muốn chỉnh sửa thêm code giao diện React:
```bash
cd frontend
npm install
npm run dev
```
Trình duyệt sẽ mở tại `http://localhost:5173` (tự động proxy API sang backend port 8000). Sau khi sửa xong, chạy `npm run build` để cập nhật bản phân phối cho FastAPI.

### 7. Quản lý cặp dịch vụ local

Các script trong `scripts/` dùng chung một process manager Python, khởi chạy/kiểm tra cả FastAPI và Vite:

```bash
# Windows
scripts\start-local.cmd
scripts\stop-local.cmd
# start-local.bat / stop-local.bat cũng là alias tương thích

# Git Bash / macOS / Linux
bash scripts/start-local.sh
bash scripts/stop-local.sh

# Xem trạng thái tiến trình do Data2Form quản lý
python scripts/dev.py status
```

Mặc định dịch vụ chỉ bind vào `127.0.0.1`; `DATA2FORM_HOST` chỉ chấp nhận địa chỉ loopback. Có thể đổi port bằng `DATA2FORM_BACKEND_PORT` và `DATA2FORM_FRONTEND_PORT`. PID/state và log được lưu ngoài repository trong thư mục state của người dùng; lệnh stop chỉ dừng tiến trình đã xác minh thuộc Data2Form.


---

## 📖 Hướng dẫn sử dụng

1. **Tải dữ liệu**: Nhấn nút "Upload Excel" để tải file chứa dữ liệu cần nhập.
2. **Cấu hình URL**: Nhập địa chỉ website chứa form cần nhập liệu.
3. **Ánh xạ (Mapping)**: 
   - Sử dụng công cụ "Pick" để chọn các phần tử trên web.
   - Gán cột Excel tương ứng cho từng Selector.
4. **Cấu hình bổ sung**: 
   - `Submit Selector`: Nút để gửi form sau khi điền xong mỗi dòng.
   - `Trigger Open Form`: Selector để mở modal/form (nếu cần).
5. **Thực thi**: Nhấn "Run Automation" và theo dõi tiến trình qua log và thanh progress.

### Form có thông tin chung và nhiều bảng chi tiết

1. Chuẩn bị một workbook có một sheet thông tin chung (mỗi dòng là một form/parent, có khóa duy nhất như `OrderID`) và một sheet riêng cho từng bảng chi tiết.
2. Mỗi sheet chi tiết phải có cột khóa parent tương ứng; các dòng được nhóm theo khóa này, không theo thứ tự dòng trong file.
3. Bật **“Thông tin chung + nhiều bảng chi tiết”**, chọn sheet/khóa parent, rồi cấu hình mapping cho thông tin chung.
4. Thêm từng bảng chi tiết theo thứ tự muốn xử lý; chọn sheet, khóa liên kết và mapping riêng. Điền `Nút thêm dòng` hoặc `Nút lưu dòng` chỉ khi website yêu cầu.
5. Chọn selector Submit của form chính. Data2Form điền thông tin chung một lần, chạy từng bảng theo thứ tự cấu hình, rồi submit form chính.

Với bảng lặp, selector có thể dùng token `{row}` để trỏ tới dòng hiện tại (đánh số từ 1). Công cụ Pick tự thêm token này khi nhận diện phần tử `<tr>` trong `<tbody>`; các selector còn lại được dùng nguyên trạng, không tự suy đoán theo tên field hoặc website. Nếu preset cũ chứa ID được đánh số cố định theo từng dòng, hãy cập nhật selector đó sang dạng có `{row}`.

Sheet chi tiết rỗng được bỏ qua. Khóa parent trống/trùng, khóa chi tiết không khớp hoặc mapping không hợp lệ sẽ bị chặn trước khi mở trình duyệt. Nếu có lỗi khi điền một dòng, Data2Form không lưu dòng đó, không submit form chính và dừng run để tránh ghi tiếp trên trạng thái chưa chắc chắn.

### Phạm vi và giới hạn

- Luồng form đơn và chế độ lặp một bảng cũ vẫn được giữ. Chế độ hybrid yêu cầu workbook nhiều sheet, khóa parent ổn định và selector/lifecycle được cấu hình riêng cho từng bảng.
- Custom control cần selector trỏ đúng phần tử tương tác và có thể cần cấu hình loại field thủ công. Website khác nhau có thể dùng widget riêng, vì vậy cần xác minh trên form đích trước khi chạy batch.
- Ngày được nhận ở dạng `YYYY-MM-DD` hoặc `DD/MM/YYYY`; định dạng mơ hồ không tự đoán.
- Upload cần cột Excel chứa đường dẫn tới file có trên máy chạy Data2Form.
- Login có thể dùng browser session; CAPTCHA/OTP hoặc bước cần người dùng vẫn phải xử lý thủ công. Data2Form không đảm bảo hoạt động với mọi website hoặc mọi kiểm soát truy cập.
- Browser giữ xác thực chứng chỉ HTTPS; website dùng chứng chỉ tự ký cần được cấu hình tin cậy trên máy chạy Data2Form.
- Trạng thái “Thao tác xong” xác nhận các tương tác browser hoàn tất, không tự chứng minh website đã lưu dữ liệu thành công. Hãy kiểm tra thông báo/xác nhận ở trang đích.
- API được giới hạn cho loopback/local development; không bind hoặc expose dịch vụ ra LAN/Internet nếu chưa bổ sung cơ chế xác thực phù hợp.

---

## 📂 Cấu trúc thư mục

- `app.py`: FastAPI server và API endpoints.
- `main.py`: Lõi tự động hóa Playwright.
- `frontend/src/`: Mã nguồn frontend React/TypeScript.
- `frontend/dist/`: Frontend build phục vụ bởi FastAPI; được tạo bằng `npm run build`.
- `static/`: Tài nguyên tĩnh dùng chung như favicon.
- `stores/`: File Excel đã tải lên, được tổ chức theo ngày.
- `automation.db`: Cơ sở dữ liệu SQLite được tạo khi chạy ứng dụng.

Chạy backend tests bằng `python -m unittest discover -s tests -v` từ thư mục gốc.

---

## 📝 Quy tắc đóng góp

Mọi thay đổi nên giữ API tương thích ngược, cập nhật tests/tài liệu liên quan và được xác minh bằng các lệnh kiểm tra của dự án trước khi gửi.

---
**Phát triển bởi Huy Tinh** 🚀
