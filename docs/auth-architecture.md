# Thiết kế kiến trúc: Authentication bằng JWT

- **Trạng thái:** thiết kế đề xuất, chưa triển khai và chưa xác minh runtime.
- **Phạm vi tài liệu:** xác thực người dùng cho dashboard/API Data2Form hiện có.
- **Stack quan sát được:** Python, FastAPI, SQLite, frontend HTML/CSS/JavaScript phục vụ cùng origin.
- **Giả định thiết kế mặc định:** một tài khoản quản trị/người vận hành cho mỗi bản cài đặt Data2Form trên máy trạm. Chưa có yêu cầu về đăng ký công khai, tenant hay nhiều vai trò.

> Nếu mục tiêu là nhiều người dùng độc lập hoặc nhiều tenant, không được triển khai theo giả định một tài khoản: cần quyết định quyền sở hữu dữ liệu và migration `user_id` trước khi bảo vệ API.

## 1. Tóm tắt kiến trúc đề xuất

Bảo vệ toàn bộ `/api/*` bằng một ranh giới xác thực dùng chung. Dùng **JWT access token ngắn hạn trong cookie HttpOnly** để phù hợp với dashboard same-origin hiện tại; dùng refresh token opaque ngẫu nhiên, lưu hash và xoay vòng trong SQLite để hỗ trợ phiên đăng nhập dài hạn và thu hồi. Mỗi request API có access JWT hợp lệ phải đồng thời trỏ tới một phiên còn hoạt động trong DB. Cách này giữ lợi ích định dạng/kiểm chữ ký JWT nhưng chủ động đánh đổi tính stateless để logout, thu hồi phiên và vô hiệu hóa tài khoản có hiệu lực ngay.

Tài khoản đầu tiên được tạo ngoài HTTP bằng lệnh quản trị tương tác; không có endpoint đăng ký công khai, mật khẩu mặc định, hoặc bí mật JWT được hard-code. Các API dữ liệu hiện hữu giữ nguyên response thành công trong giai đoạn này; frontend bổ sung màn hình đăng nhập và một wrapper fetch xử lý 401/CSRF.

## 2. Hiện trạng và invariants cần giữ

### 2.1 Hiện trạng đã quan sát

- `app.py` tạo `FastAPI` và mount toàn bộ `static/` dưới `/static`; route `/` trả về `static/index.html`.
- Các API hiện tại không có auth dependency/middleware. Frontend ở `static/script.js` gọi trực tiếp `/api/upload`, `/api/run`, `/api/presets`, `/api/history`, `/api/download`, `/api/status`, picker và các API khác.
- SQLite `automation.db` có `presets` và `history`; `init_db()` chạy khi import ứng dụng. `presets` dùng URL làm khóa chính; history chứa log và đường dẫn file. Chưa thấy schema user/tenant.
- `GET /api/status` trả danh sách screenshot; frontend mở ảnh qua đường dẫn `/static/...`. Các file PNG ngoài favicon trong `static/` bị dọn lúc startup, nhưng khi tồn tại thì hiện có thể được phục vụ công khai qua StaticFiles.
- `/api/desktop/windows` trả thông tin cửa sổ/process máy cục bộ. `/api/pick-selector` mở trình duyệt đến URL do request cung cấp; `/api/run` khởi chạy automation trên website đích.
- Frontend là same-origin theo cách phục vụ hiện tại; chưa thấy CORS middleware trong `app.py`.
- `requirements.txt` hiện chưa khai báo thư viện JWT hoặc password hashing chuyên dụng.
- Working tree có thay đổi chưa commit trong `.gitignore` và các mục untracked khác; chúng không thuộc phạm vi thiết kế/tài liệu này.

### 2.2 Invariants/behavior cần bảo toàn

1. Giao diện vẫn dùng được sau khi đăng nhập; preset, upload, preview, automation, status, history và download tiếp tục hoạt động với shape thành công hiện tại.
2. Không chạy automation, mở picker, đọc/tải dữ liệu hoặc liệt kê cửa sổ hệ thống trước khi request được xác thực.
3. Các luồng đăng nhập website đích trong Playwright (`use_session`, `.browser_session`) tách biệt hoàn toàn với phiên đăng nhập Data2Form; không đọc/ghi/đổi cookie hoặc profile của website đích.
4. Dữ liệu hiện có không bị xóa, đổi owner ngầm, hoặc thay đổi ý nghĩa trong bước thêm auth.
5. JWT/refresh token/password không xuất hiện trong log, URL, localStorage, sessionStorage, response lỗi hoặc tên file.
6. Khi auth chưa cấu hình hợp lệ, ứng dụng không được âm thầm phục vụ API ở chế độ mở.

## 3. Mục tiêu, ngoài phạm vi, và giả định

### Mục tiêu

- Xác thực mọi API chức năng bằng một cơ chế thống nhất.
- Có onboarding tài khoản an toàn, login, lấy identity hiện tại, refresh, logout và thu hồi phiên.
- Chống đánh cắp token qua JavaScript bằng HttpOnly cookie, giảm CSRF, giới hạn brute force và bảo vệ nội dung riêng tư.
- Có đường rollout/rollback an toàn cho SQLite và bản cài đặt cục bộ.

### Ngoài phạm vi phiên bản đầu

- Public signup, xác minh email, khôi phục mật khẩu qua email, MFA, OAuth/SSO, RBAC, multi-tenant, phân quyền theo từng bản ghi.
- JWT dành cho third-party/mobile client, access token trong `localStorage`, hoặc API stateless không lưu phiên.
- Thay đổi nội dung/chức năng automation, thay đổi schema `presets`/`history` để gán owner, chuẩn hóa response của mọi API legacy.
- Giải quyết SSRF/egress policy cho URL automation/picker; yêu cầu auth không loại bỏ rủi ro đó.

### Giả định cần xác nhận trước khi triển khai

- Mỗi cài đặt hiện tại chỉ có một người dùng vận hành đáng tin cậy; mọi dữ liệu hiện lưu trong SQLite/thư mục `stores/` được xem là dữ liệu của cài đặt đó.
- Server mặc định chỉ nghe loopback trên máy trạm như hướng dẫn chạy hiện tại. Nếu bind ra LAN/Internet, bắt buộc HTTPS, secure cookies, cấu hình host/proxy rõ ràng và threat review bổ sung.
- Account bootstrap được thực hiện bởi chủ máy qua CLI; không có “first user wins” endpoint trên mạng.
- Token/key secret được cấp qua môi trường triển khai (hoặc secret store của OS ở bước triển khai sau), không lưu trong Git/SQLite.

## 4. So sánh phương án

| Phương án | Ưu điểm | Nhược điểm/rủi ro | Kết luận |
|---|---|---|---|
| JWT bearer trong localStorage | Dễ gắn vào fetch/API clients; không gửi tự động theo cookie | XSS có thể lấy token và tái sử dụng ngoài trình duyệt; cần thay mọi call site và xử lý token persistence | Không chọn cho dashboard same-origin |
| Session ID opaque trong cookie + session DB | Thu hồi/kiểm soát đơn giản, ít lỗi JWT | Không đáp ứng mục tiêu dùng JWT; session cookie vẫn cần CSRF | Phương án tốt nếu JWT không phải yêu cầu bắt buộc |
| **JWT access HttpOnly cookie + refresh opaque xoay vòng** | JWT đáp ứng yêu cầu; token không đọc được từ JS; refresh được thu hồi/rotate; hợp với same-origin UI | Cần CSRF; DB session lookup khiến access không stateless; quản lý cookie/proxy phải đúng | **Đề xuất** |
| Access + refresh đều là JWT stateless | Ít DB access | Logout/thu hồi khó; refresh token reuse khó xử lý chắc chắn; có thể sống tới hạn token | Không chọn |

## 5. Các quyết định thiết kế

### 5.1 Identity và provisioning

- Bảng `users` có một account local admin duy nhất ở phiên bản đầu; `username_normalized` là unique, case-insensitive; `is_active` cho phép vô hiệu hóa account.
- Tạo account bằng script CLI dự kiến `scripts/create_admin.py` hoặc entrypoint tương đương: hỏi username và mật khẩu qua prompt ẩn, tạo password hash; không nhận password qua command-line argument, không ghi credential vào stdout/log.
- Lệnh bootstrap chỉ tạo account khi chưa tồn tại. Nếu đã có account thì dừng, không reset password ngầm. Password reset cần thao tác admin riêng và phải thu hồi mọi phiên.
- Hash password bằng Argon2id qua thư viện chuyên dụng (`pwdlib[argon2]` hoặc thư viện tương đương được chốt khi triển khai). Không tự viết thuật toán hash; kiểm tra hash theo constant-time API của thư viện.

### 5.2 Token, phiên và vòng đời

- **Access JWT:** HS256 trong giai đoạn một service; key tối thiểu 256 bit, tạo bằng CSPRNG, cấu hình ngoài source code. Claims bắt buộc: `iss`, `aud`, `sub` (user ID), `sid` (session ID), `jti`, `iat`, `nbf`, `exp`, `typ="access"`. Thời hạn đề xuất 15 phút.
- Validate allowlist thuật toán cố định (`HS256`), issuer/audience, thời gian, loại token và claim bắt buộc; không tin `alg` do token chọn, không nhận token refresh ở API bình thường.
- **Refresh token:** opaque random ít nhất 256 bit, không phải JWT; chỉ bản hash SHA-256 được lưu. Hạn idle 7 ngày, hạn tuyệt đối 30 ngày (giá trị khởi đầu cần cấu hình/duyệt theo UX). Mỗi lần refresh tiêu thụ token hiện tại và phát token mới trong một transaction.
- Refresh token reuse sau khi đã tiêu thụ là dấu hiệu token bị sao chép: thu hồi session/family liên quan, xóa cookie và trả lỗi xác thực tổng quát. Refresh transaction phải atomic (SQLite `BEGIN IMMEDIATE` hoặc cơ chế tương đương) để chặn hai request đồng thời cùng dùng một token.
- Mỗi request tới API xác thực access JWT, sau đó kiểm tra `sid` còn active và user còn active. Do vậy logout, disable account, và password reset có hiệu lực ngay; DB lookup trên mỗi request là chi phí chấp nhận được cho app local quy mô nhỏ.
- Logout thu hồi session và refresh token descendants trong transaction, xóa cookie. Thay đổi password/vô hiệu hóa account thu hồi mọi session của user.

### 5.3 Cookie, CSRF và browser

- Cookie access: `d2f_access`; refresh: `d2f_refresh` với `Path=/api/auth`; cả hai host-only, không `Domain`, `HttpOnly`, `SameSite=Strict`, `Secure` bật khi chạy HTTPS. Với loopback HTTP chỉ cho phép `Secure=false` theo cấu hình dev/local rõ ràng; không tự suy luận từ `X-Forwarded-Proto` không đáng tin.
- Không trả JWT access/refresh trong JSON. Không lưu token trong Web Storage. `GET /api/auth/me` trả user profile không nhạy cảm.
- CSRF token ngẫu nhiên riêng: endpoint bootstrap trả token ngắn hạn cho login; sau login/refresh trả token gắn với session và lưu hash. Backend đặt cookie CSRF host-only, `HttpOnly`, `SameSite=Strict` (và `Secure` theo cấu hình), đồng thời trả token qua JSON để frontend chỉ giữ trong memory và gửi header `X-CSRF-Token`; backend so khớp cookie/header constant-time, session binding và kiểm tra `Origin` allowlist cho mọi request thay đổi state (POST/PUT/PATCH/DELETE), bao gồm login, refresh, logout. Không bật CORS rộng.
- `SameSite=Strict` là phòng vệ bổ sung, không thay thế CSRF token/Origin check. GET/HEAD không được gây side effect.
- Frontend thêm `apiFetch()` wrapper: cùng-origin credentials, tự gắn CSRF header cho mutation, xử lý 401 để hiển thị login. Không tự replay mutation sau login; người dùng phải chủ động gửi lại để tránh chạy automation/upload hai lần.
- Shell HTML, CSS, JS, favicon có thể công khai; không cache response chứa identity/CSRF. File screenshot, Excel, history/log và mọi endpoint dữ liệu không được nằm trên public static path.

### 5.4 Key và vận hành

- Cấu hình tối thiểu: `AUTH_JWT_SECRET`, `AUTH_JWT_ISSUER`, `AUTH_JWT_AUDIENCE`, `AUTH_COOKIE_SECURE`, `AUTH_ALLOWED_ORIGINS`, access/refresh lifetimes. Secret thiếu/không đủ mạnh phải làm startup fail khi auth bật; không có fallback key mặc định.
- Trong dev loopback, có thể tạo secret local ngoài repo với cảnh báo rõ; restart làm mất hiệu lực token cũ. Không dùng ephemeral secret cho deployment cần giữ phiên.
- Hỗ trợ key rotation có kế hoạch: sign bằng key hiện hành, verify bằng key hiện hành và key trước đó chỉ trong thời gian access token tối đa; dùng `kid` với allowlist key ID nếu cần overlap. Khi nghi lộ key, revoke toàn bộ session, thay key và buộc login lại.
- Login throttle đề xuất 5 lần thất bại / 15 phút theo account và nguồn request; dùng backoff, trả `429` kèm `Retry-After`, không khóa vĩnh viễn để tránh DoS. Không log password/token/cookie. Với một worker local, SQLite throttle table phù hợp hơn bộ đếm chỉ trong RAM nếu cần giữ hiệu lực sau restart.

## 6. Ranh giới tin cậy và phạm vi bảo vệ

| Surface | Caller | Chính sách |
|---|---|---|
| `GET /`, `/static/style.css`, `/static/script.js`, favicon | Browser chưa đăng nhập | Public shell/assets tối thiểu; không chứa dữ liệu người dùng. Static mount không được làm lộ file runtime/private |
| `GET /api/auth/csrf`, `POST /api/auth/login` | Browser chưa xác thực | Public nhưng có Origin/CSRF/bootstrap checks; login rate-limit; không tiết lộ account tồn tại |
| `POST /api/auth/refresh`, `/api/auth/logout`, `GET /api/auth/me` | Browser có cookie | Validate token/session; CSRF cho mutation; logout idempotent |
| `/api/upload`, `/api/preview`, `/api/clear-cache` | Account đã xác thực | User/session guard; kiểm tra CSRF cho mutation; mọi file thuộc installation local |
| `/api/presets` GET/POST | Account đã xác thực | Guard; giữ behavior hiện tại. Preset vẫn installation-scoped trong mô hình một account |
| `/api/history`, `/api/history/{id}/logs`, `/api/download/{id}`, `/api/status` | Account đã xác thực | Guard; log, ảnh và file chỉ qua route private; không để URL tĩnh công khai |
| `/api/run`, `/api/desktop/run`, picker, `/api/desktop/windows` | Account đã xác thực | Guard bắt buộc trước side effect; CSRF; không nhầm xác thực Data2Form với website session của Playwright |
| Health/liveness (nếu được thêm) | Monitoring | Chỉ metadata tối thiểu; không trả cấu hình, user, DB path hay trạng thái máy nhạy cảm |

Triển khai guard theo nguyên tắc **fail closed**: mặc định mọi `/api/*` đều cần auth, chỉ allowlist chính xác các endpoint auth và health công khai. Không dựa vào prefix `/api/auth` wildcard rộng cho mọi verb nếu endpoint chưa được khai báo.

### Dữ liệu tĩnh riêng tư

Không thể giữ screenshot riêng tư dưới `/static/` công khai. Chuyển screenshot lỗi sang vùng lưu private, ví dụ `stores/screenshots/`, rồi phục vụ qua route có auth như `GET /api/screenshots/{name}` với basename/path validation. Thay đổi response `screenshots` của `/api/status` thành URL API cùng-origin. `/static` chỉ phục vụ assets cố định đã biết. Kiểm tra trực tiếp path traversal và không nhận đường dẫn file tùy ý từ client.

## 7. API contract đề xuất

Các request/response dưới đây là hợp đồng mới cho auth. API legacy giữ response thành công hiện tại để hạn chế phạm vi tương thích; lỗi 401/403/429 có envelope ổn định dùng chung.

### Auth endpoints

| Method/path | Public? | Request | Success | Ghi chú |
|---|---|---|---|---|
| `GET /api/auth/csrf` | Có | Không | `200 {"csrf_token":"..."}` + cookie CSRF | Bootstrap cho login; no-store |
| `POST /api/auth/login` | Có | `{ "username": "...", "password": "..." }` + CSRF | `200 {"user":{"id":"...","username":"..."},"csrf_token":"..."}` + access/refresh cookies | Sai username/password cùng một lỗi; throttle |
| `GET /api/auth/me` | Không | Cookie access | `200 {"user":{"id":"...","username":"..."}}` + CSRF hiện tại nếu cần đồng bộ tab | 401 khi chưa có phiên |
| `POST /api/auth/refresh` | Không; cần cookie refresh | CSRF | `200 {"user":{"id":"...","username":"..."},"csrf_token":"..."}` + cookie access/refresh mới | Rotate atomic; reuse revokes family |
| `POST /api/auth/logout` | Không; cần access hoặc refresh cookie | CSRF | `204` và xóa cookie | Logout lặp lại vẫn an toàn/idempotent |

Không cung cấp signup, danh sách user, admin web, hoặc token trong URL/body response. Bootstrap admin là lệnh cục bộ ngoài API.

### Error contract

```json
{
  "detail": {
    "code": "AUTH_REQUIRED",
    "message": "Yêu cầu đăng nhập"
  }
}
```

| Tình huống | Status/code | Retry |
|---|---|---|
| Không có/expired/sai JWT hoặc session bị revoke | `401 AUTH_REQUIRED` | Login hoặc refresh một lần; không retry mutation tự động |
| Sai thông tin login | `401 INVALID_CREDENTIALS` | Không tự động; thông báo chung |
| CSRF hoặc Origin không hợp lệ | `403 CSRF_VALIDATION_FAILED` | Không retry; reload/khởi tạo CSRF lại |
| Login throttle | `429 LOGIN_RATE_LIMITED` + `Retry-After` | Chờ theo header |
| Refresh token cũ/reuse hoặc phiên không tồn tại | `401 SESSION_INVALID` | Xóa client state và login lại |
| Input auth sai định dạng | `422 VALIDATION_ERROR` | Sửa request |
| DB/key/service lỗi | `500/503 INTERNAL_ERROR` | Chỉ retry request an toàn theo chính sách |

Auth middleware không được trả stack trace, phân biệt user không tồn tại, hoặc lộ thông tin bản ghi. Giữ tương thích với client cũ: success body các API hiện hành chưa bị bọc lại; frontend auth-aware phải xử lý response FastAPI legacy.

## 8. Data model và migration

### Bảng đề xuất

- `users`: `id` (UUID/text PK), `username_normalized` (UNIQUE NOT NULL), `username_display`, `password_hash`, `is_active` (NOT NULL), `created_at`, `updated_at`, `password_changed_at`.
- `auth_sessions`: `id`/`sid` (UUID/text PK), `user_id` FK, `created_at`, `last_seen_at`, `idle_expires_at`, `absolute_expires_at`, `revoked_at`, `revocation_reason` nullable. Index `(user_id, revoked_at)`.
- `auth_refresh_tokens`: `id`/`jti` (UUID/text PK), `session_id` FK, `token_hash` UNIQUE NOT NULL, `issued_at`, `expires_at`, `consumed_at`, `revoked_at`, `replaced_by_id` nullable self-reference. Index `(session_id, expires_at)`.
- `auth_login_attempts` (nếu throttle được lưu lâu dài): account key đã normalize và nguồn đã giảm/ẩn danh hóa, cửa sổ thời gian, số lần thất bại, `blocked_until`; không lưu secret/password.

Bật `PRAGMA foreign_keys=ON` trên mọi connection auth. Quy định cleanup token/session hết hạn theo batch và không xóa audit cần thiết ngoài retention đã quyết định. Password hash không bao giờ được trả ra API.

### Migration/rollout

1. **Preflight/backup:** ghi rõ DB hiện tại và thư mục `stores/`; backup nhất quán; xác nhận process đang chạy và port chỉ loopback. Không đọc/đưa nội dung dữ liệu nhạy cảm vào log.
2. **Expand:** thêm các bảng auth/index mới bằng migration versioned hoặc runner idempotent; không sửa/xóa `presets`/`history`. Kiểm tra migration từ DB trống và DB đã có dữ liệu. Lỗi migration làm startup dừng.
3. **Provision:** cấp `AUTH_JWT_SECRET` ngoài repo; chạy CLI tạo admin trước khi server mở API. Không bật chế độ mở nếu provisioning thiếu.
4. **Switch atomically per local install:** dừng server cũ; backup; migrate; provision; chạy bản mới với guard fail-closed; kiểm tra đăng nhập và gọi read-only API bằng account. Vì caller hiện là dashboard same-origin duy nhất đã tìm thấy trong repo, cập nhật UI cùng release; bên ngoài repo chưa thể enumerate.
5. **Stabilize:** theo dõi 401/403/429, lỗi refresh, lỗi SQLite và user support trong thời gian vận hành đã thống nhất. Không có sunset compatibility cho public consumer được xác nhận; phạm vi consumer ngoài repo chưa biết.
6. **Contract:** chưa có bước drop schema legacy trong feature này. Giữ additive auth tables; dọn session/refresh hết hạn theo retention.

### Rollback

- Nếu release lỗi: dừng bản mới và quay lại bản cũ; bản cũ bỏ qua bảng auth mới, vì migration chỉ additive. Không xóa user/session tables trong rollback.
- Nếu đã lộ secret hoặc nghi token bị đánh cắp: revoke sessions, rotate secret, bắt buộc đăng nhập lại; nếu DB hỏng thì phục hồi DB từ backup theo quy trình vận hành, không rollback bằng cách mở API không auth.
- Không rollback UI riêng khiến client hiển thị dashboard nhưng backend còn public. Bản cũ chỉ được khởi động trong môi trường loopback tin cậy, có thời hạn và có quyết định chấp thuận rủi ro cụ thể; ưu tiên sửa/forward-fix.

## 9. Điểm triển khai dự kiến

Đây là file/symbol dự kiến cần thay đổi khi được duyệt triển khai; chưa tạo/sửa chúng trong yêu cầu này.

| File/boundary | Trách nhiệm dự kiến |
|---|---|
| `app.py` | Wire auth config/lifespan, auth endpoints, fail-closed guard/dependencies, route ảnh private; chuyển mọi nhóm `/api/*` vào policy được bao phủ |
| `auth_service.py` (mới) | Hash/verify password, token issue/verify, refresh rotation, logout/revoke, CSRF/session policy; không chứa HTTP/UI |
| `auth_store.py` (mới) | SQLite connection/migrations cho auth, transaction atomics và truy vấn user/session/token |
| `scripts/create_admin.py` (mới hoặc CLI tương đương) | Provision account tương tác, fail nếu đã tồn tại, không log secret |
| `requirements.txt` | Thêm dependency đã chọn cho JWT và Argon2; pin/version compatible với Python dự án |
| `static/index.html`, `static/style.css` | Màn hình đăng nhập và trạng thái đăng xuất phù hợp dashboard hiện có |
| `static/script.js` | `apiFetch`, bootstrap/login/me/refresh/logout, CSRF header, 401 routing; không lưu token |
| `main.py`/screenshot producer | Chỉ nếu cần đổi nơi lưu screenshot từ public static sang private store; giữ nguyên automation behavior |
| `tests/` | Unit, API contract, middleware/CSRF, migration/rollback, UI client behavior |

**Consumer inventory:** trong checkout tìm thấy dashboard `static/script.js` gọi API same-origin; chưa tìm thấy SDK/client khác được tracked. `tests/` hiện chỉ có artifacts `__pycache__` trong listing và `git ls-files tests` không liệt kê test source; do đó test contract mới cần được tạo. Caller bên ngoài checkout, bản cài đặt cũ và user-data thật `automation.db` không thể enumerate từ code search.

## 10. Kế hoạch implementation và TDD

1. **Contract/test skeleton:** chốt account model, cookie/domain/origin, token TTL, local vs network deployment; tạo tests cho contract auth/error và danh sách endpoint phải được bảo vệ.
2. **Storage:** migration additive, FK/auth connection, password hash, users/sessions/refresh tables; tests DB trống/DB có preset-history và atomic refresh race/reuse.
3. **Core auth:** login, access JWT verify, refresh rotate, logout, session revoke; unit test claim validation, alg/issuer/audience/expiry, password verify, generic login errors, secret absence from logs.
4. **Request boundary:** default-deny `/api/*`, exact public allowlist; kiểm tra auth xảy ra trước mọi side effect. Test toàn bộ route map gồm `/api/desktop/windows`, upload/download/history/screenshots và unknown `/api/*`.
5. **CSRF/cookies:** Origin allowlist, cookie flags, CSRF bootstrap/binding, secure config cho HTTPS và loopback; negative tests cross-origin/missing/mismatch token, SameSite/Secure/HttpOnly.
6. **Sensitive static migration:** screenshot URL/private route và path traversal tests; đảm bảo `/static` chỉ cung cấp assets tĩnh cố định.
7. **UI:** login, bootstrap current user, expiry/refresh, logout, fetch wrapper; test rằng không token nằm trong localStorage/sessionStorage/URL và không auto-replay mutation.
8. **Compatibility/integration:** xác thực trước/sau login cho mọi API legacy; kiểm tra preset/upload/preview/status/run/history/download giữ success shape và không chạy side effect trước login.
9. **Security/release gate:** secret/key config, brute-force throttle, concurrency refresh, logs redaction, startup fail-closed, backup/rollback rehearsal; review độc lập trước rollout.

Không coi test unit là bằng chứng deploy/migration/runtime. Những bước apply migration, smoke test trên bản cài đặt thực, backup/restore, TLS/proxy và rollout vẫn là việc cần quan sát riêng khi triển khai.

## 11. Acceptance criteria

- Request không có/không hợp lệ access token nhận 401 cho tất cả API dữ liệu và side-effect; không một route chức năng nào bị bỏ sót.
- Chỉ endpoints auth đã liệt kê và health tối thiểu được truy cập trước login.
- API protected không đọc file, thay đổi SQLite/cache, mở browser, khởi chạy automation hoặc trả dữ liệu trước khi guard thành công.
- Login thành công không trả JWT ra body và cookie có thuộc tính đã quy định; sai credential không tiết lộ account tồn tại.
- Refresh token chỉ dùng một lần; refresh cũ bị reuse revoke session/family; logout/disable account vô hiệu access ngay qua `sid` check.
- CSRF/Origin sai bị chặn ở mọi mutation, kể cả auth; GET không gây side effect.
- Không thể tải screenshot hoặc dữ liệu riêng tư qua đường `/static/` công khai; asset công khai vẫn tải bình thường.
- DB cũ vẫn giữ nguyên toàn bộ preset/history/file; migration additive và rollback bản ứng dụng không phá dữ liệu cũ.
- Frontend sau login giữ nguyên flows hiện tại; 401 không làm tự chạy lại automation/upload.
- Secret/password/token không xuất hiện trong response lỗi, logs, URLs, browser storage, source code hoặc repository.
- Nếu secret, provisioning, origin policy hoặc migration thiếu/lỗi, startup/auth fail closed chứ không tắt auth.

## 12. Rủi ro và câu hỏi còn mở

| Câu hỏi/rủi ro | Mặc định trong thiết kế | Khi nào phải thay đổi |
|---|---|---|
| Một account hay nhiều account? | Một local admin/installation | Nếu nhiều operator cần dữ liệu cách ly: định nghĩa ownership cho DB/file/cache/status, migration/backfill rồi mới bật account thứ hai |
| Chỉ loopback hay có LAN/Internet? | Loopback local; không tin header proxy tùy ý | Nếu expose network: TLS bắt buộc, trusted proxy/host policy, firewall, threat review và vận hành key/backup |
| Thời hạn session? | Access 15m; refresh idle 7d, absolute 30d | Duyệt lại theo nhu cầu persistent login, rủi ro máy dùng chung và UX |
| Secret lưu ở đâu? | Env injection, không lưu Git | Deployment desktop cần secret store OS/DPAPI hoặc installer-managed protected config |
| Caller ngoài repo? | Chưa enumerable | Nếu có client/automation tích hợp khác, inventory và kiểm thử trước khi enforce auth |
| Throttle theo client IP? | Kết hợp account + nguồn đã giảm/ẩn danh hóa; không khóa vĩnh viễn | Nếu reverse proxy/multi-worker, cần shared rate limiter và trusted client address |
| Tách schema migration? | Bảng auth additive; chưa đổi schema legacy | Nếu migration tooling chính thức được thêm, tích hợp migration versioned thay vì tạo cơ chế song song |

## 13. Bằng chứng khảo sát và giới hạn

Đã đọc `README.md`, `requirements.txt`, các vùng liên quan của `app.py`, `static/index.html`, `static/script.js`, `main.py`, schema SQLite hiện có, danh sách file `static/`/`scripts/`/`tests/`, Git status và diff `.gitignore`. Schema SQLite được đọc chỉ ở mức metadata (`PRAGMA table_info`); không đọc row dữ liệu. Working tree ban đầu có thay đổi `.gitignore` và untracked `.hermes/`, `.serena/`, `frontend/`; không chỉnh sửa chúng.

Thiết kế này là artifact kiến trúc dựa trên source hiện thấy. Chưa thay đổi mã nguồn, cài dependency, chạy migration, thực hiện test/integration, kiểm tra deployment/TLS, hoặc xác nhận yêu cầu multi-user với chủ sản phẩm.