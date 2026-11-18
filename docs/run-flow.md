# Hướng dẫn sử dụng AutoInput

Tài liệu này hướng dẫn theo thứ tự: **cài và mở app → chuẩn bị dữ liệu → cấu hình tự động hóa
→ kiểm tra → chạy thật → xem kết quả và gỡ lỗi**.

AutoInput có thể đọc CSV, Excel, JSON, XML; ánh xạ dữ liệu vào app desktop trên macOS/Windows
hoặc form web; kiểm tra dữ liệu trước khi nhập; theo dõi trạng thái từng dòng; chạy lại dòng lỗi
và xuất báo cáo.

## 1. Bắt đầu chạy app

Mở Terminal (macOS/Linux) hoặc PowerShell (Windows) tại thư mục dự án. Cài phần phụ thuộc phù
hợp với ứng dụng đích:

| Ứng dụng đích | Lệnh cài đặt | Ghi chú |
|---|---|---|
| Web (mọi hệ điều hành) | `uv sync --extra gui --extra web` | Cài thêm Chromium ở bước dưới |
| App desktop macOS | `uv sync --extra gui --extra mac` | Cần cấp quyền Accessibility; Input Monitoring dùng cho phím dừng toàn cục |
| App desktop Windows | `uv sync --extra gui --extra windows` | AutoInput và app đích cần chạy cùng mức quyền |

Trên macOS, vào **System Settings → Privacy & Security** và bật **Accessibility** cho Terminal,
iTerm, VS Code hoặc AutoInput đang chạy. Bật thêm **Input Monitoring** nếu cần phím dừng khẩn
cấp toàn cục. Sau khi cấp quyền, thoát hẳn rồi mở lại app/Terminal. Trên Windows, nếu app đích
chạy quyền Administrator thì AutoInput cũng phải chạy quyền Administrator.

Nếu dùng web, cài trình duyệt Chromium một lần:

```bash
uv run playwright install chromium
```

Mở giao diện:

```bash
uv run autoinput gui
```

### Chạy demo web có sẵn

Demo sử dụng form [demo_form.html](../samples/demo_form.html), profile
[demo_web_form.yaml](../profiles/demo_web_form.yaml), mapping
[demo_web_form.yaml](../mappings/demo_web_form.yaml) và dữ liệu
[customers.csv](../samples/customers.csv).

Từ thư mục dự án, cài phần phụ thuộc web như trên, sau đó chạy thử bằng CLI:

```bash
uv run autoinput validate samples/customers.csv -m mappings/demo_web_form.yaml
uv run autoinput run samples/customers.csv -m mappings/demo_web_form.yaml           # chạy thử
uv run autoinput run samples/customers.csv -m mappings/demo_web_form.yaml --live    # chạy thật
```

Lệnh `run` mặc định chỉ ghi log thao tác, **không điều khiển app đích**. Lệnh có `--live` sẽ mở
Chromium và thực hiện kịch bản trên form demo. Để tự mở giao diện thay vì chạy demo qua CLI,
dùng `uv run autoinput gui`.
Với file mẫu, hai dòng hợp lệ sẽ được nhập; dòng có dữ liệu sai sẽ được đánh dấu lỗi và bỏ qua.

### Dùng giao diện lần đầu

1. Ở **Nguồn dữ liệu**, mở hoặc kéo thả file. Kiểm tra bản xem trước; chọn sheet hoặc dòng tiêu
   đề nếu cần.
   Với Excel, app **tự nhận diện bảng**: dòng tiêu đề (kể cả tiêu đề 2–3 tầng có ô gộp, ghép
   thành tên như `Phụ cấp / Tiền cơm`), dòng bắt đầu dữ liệu, và bỏ qua dòng đánh số cột,
   dòng nhóm/mục, dòng Tổng cộng cùng phần chữ ký bên dưới.
   **Bố cục Excel** hiển thị gần giống file gốc (500 dòng đầu): ô gộp, font, đậm/nghiêng, màu
   nền/chữ, viền, căn lề, độ rộng cột, chiều cao dòng, dòng/cột ẩn và định dạng số/ngày.
   Màu số dòng bên trái: **xanh dương** = tiêu đề, **xanh lá** = dữ liệu sẽ nhập,
   **vàng** = bị bỏ qua (di chuột để xem lý do), **xám** = phần đầu trang.
   **Chuột phải vào một dòng** để sửa nhanh: đặt làm tiêu đề (1 hoặc nhiều tầng), dữ liệu
   bắt đầu/kết thúc tại đây, bỏ qua hoặc lấy lại các dòng đang chọn, xoá chỉnh tay,
   **Tự nhận diện lại**.
   **Giữ định dạng số như Excel** (bật mặc định) nhập đúng giá trị đang hiển thị, ví dụ `01`,
   `1.000.000`, `15,5%`; tắt để lấy giá trị thô (`1`, `1000000`, `0.155`).
   **Lọc thông minh** bật/tắt việc tự bỏ các dòng phụ nói trên.
   Chuyển sang **Dữ liệu nhập** để xem đúng các dòng sẽ dùng cho auto. Số thứ tự dòng của
   Excel là **số dòng thật trong sheet** (dùng cho `--rows`, báo cáo và nhật ký).
   Nếu file có nhiều sheet, nhãn **Sheet (N)** cho biết số lượng; bấm mũi tên bên cạnh
   để chọn sheet khác (sheet mới được tự nhận diện lại). Ô **Dòng tiêu đề** nhập số trực tiếp.
   Định dạng gốc chỉ đọc được với `.xls`, `.xlsx`, `.xlsm`; `.ods`/`.xlsb` chỉ hiện giá trị.
2. Bấm **Tiếp tục** để sang **Ánh xạ & Kiểm tra**.
3. Chọn profile ứng dụng đích, rà soát cột nguồn ↔ trường đích và các dòng bị báo lỗi.
   App tự gợi ý cột và phép biến đổi (ví dụ ngày → `dd/mm/yyyy`, SĐT → `phone_vn`).
   Danh sách cột hiện kèm giá trị mẫu (`Họ và tên · vd: …`); cột **Ví dụ kết quả** cho thấy
   giá trị dòng đầu sau biến đổi. Trường chưa ghép được tô vàng và đếm ở dòng
   **Đã ghép X/Y trường**. Nút **+** cạnh ô biến đổi thêm nhanh phép biến đổi có sẵn.
   **Tự nhớ:** sau khi kiểm tra thành công, app nhớ cách đọc file Excel (sheet, tiêu đề, lọc)
   và cách ghép cột. Lần sau mở file cùng bố cục, app tự áp dụng lại và tự chọn ứng dụng đích.
   Dữ liệu nhớ nằm trong `templates.json` ở thư mục dữ liệu của app, không sửa YAML của bạn.
4. Sang **Chạy nhập liệu**. Để nguyên **Chạy thử** trong lần đầu; có thể giới hạn dòng hoặc
   chọn chế độ từng dòng.
5. Đặt ứng dụng đích ở trạng thái sẵn sàng nếu dùng desktop, rồi bấm **Bắt đầu**.
6. Xem trạng thái từng dòng và phần tổng kết. Chỉ chuyển sang nhập thật sau khi đã kiểm tra
   mapping và kết quả chạy thử.

Trong khi chạy, AutoInput có thể tạm dừng/tiếp tục, dừng, chạy từng dòng, dừng khi lỗi, chỉ chạy
những dòng được chọn, nghỉ giữa các dòng, chạy lại dòng lỗi và xuất báo cáo.

Giao diện dùng nền sáng, thanh điều hướng xanh đậm và icon theo chức năng. Khi cửa sổ nhỏ,
nội dung có thể cuộn thay vì cắt chữ. Nhật ký mặc định được thu gọn để dành chỗ cho dữ liệu;
bấm **Nhật ký** ở thanh dưới hoặc vào **Xem → Nhật ký hoạt động** để mở.

Đọc file và kiểm tra dữ liệu chạy nền, có thông báo **Đang đọc/Đang kiểm tra**. Bạn vẫn có thể
đổi file hoặc sửa cấu hình; kết quả của tác vụ cũ sẽ bị bỏ. Nút tiếp tục/chạy chỉ hoạt động sau
khi tác vụ hiện tại hoàn tất.

GUI hỗ trợ tối đa **100.000 dòng dữ liệu không rỗng** mỗi file. Nếu vượt giới hạn, app báo lỗi
và không nạp một phần file. Hãy chia nhỏ file hoặc dùng CLI để tránh bỏ sót dữ liệu.

## 2. Ba phần cấu hình cần hiểu

| Phần | Mục đích | Ví dụ |
|---|---|---|
| **Nguồn dữ liệu** | File có các dòng và cột cần nhập | `samples/customers.csv` |
| **Profile** | Cách kết nối app đích, locator các trường/nút và các bước thao tác | `profiles/demo_web_form.yaml` |
| **Mapping** | Nối cột nguồn với trường trong profile; đặt quy tắc kiểm tra/biến đổi | `mappings/demo_web_form.yaml` |

Một profile có thể dùng lại với nhiều file; mapping xác định cách đưa từng file vào profile đó.
Giai đoạn chọn file và mapping chỉ đọc/kiểm tra dữ liệu, chưa thao tác lên app đích.

## 3. Thiết lập các bước chạy tự động

### 3.1 Xác định locator của form

Locator là cách tìm ô nhập, nút hoặc thông báo trên app đích.

| Nền tảng | Công cụ thường dùng | Ví dụ |
|---|---|---|
| Web | DevTools (F12) | `{ label: "Họ và tên" }`, `{ css: "#save" }` |
| macOS | `uv run autoinput ax-tree --app "Tên App"` hoặc Xcode Accessibility Inspector | `{ role: AXTextField, identifier: fullName }` |
| Windows | Accessibility Insights / `inspect.exe` | `{ auto_id: txtFullName }` |

### 3.2 Khai báo profile

Trong profile, khai báo thông tin kết nối, trường cần điền, control cần bấm/chờ và thứ tự thao tác.
Ví dụ rút gọn:

```yaml
id: customer_form
name: "Form khách hàng"
driver: web
connect:
  url: "https://example.test/customers"

fields:
  full_name: { label: "Họ và tên", locator: { label: "Họ và tên" } }
  phone: { label: "Điện thoại", locator: { label: "Điện thoại" } }

controls:
  save_button: { css: "#save" }
  saved_message: { css: "#toast" }
  new_button: { css: "#new" }

record_steps:
  - { action: fill_all }
  - { action: click, target: save_button }
  - { action: wait, target: saved_message, timeout: 10 }
  - { action: click, target: new_button }

on_error_steps:
  - { action: press, keys: "Escape" }
```

Kịch bản trên thực hiện tuần tự cho mỗi dòng: **điền trường → lưu → chờ xác nhận lưu thành công
→ mở form mới**. `wait` giúp tránh nhập dòng tiếp theo khi app chưa xử lý xong. Chỉ dùng `sleep`
khi app không có locator/trạng thái nào để chờ; ưu tiên `wait`.

Các mẫu thứ tự khác:

| Tình huống | Thứ tự gợi ý |
|---|---|
| Form tự làm trống sau khi lưu | `fill_all` → `click save` → `wait form_empty_marker` |
| Phải bấm **Thêm mới** trước | `click new` → `fill_all` → `click save` → `wait saved` |
| Có hộp thoại xác nhận | `click save` → `wait confirm_dialog` → `press Enter` → chờ hộp thoại đóng |
| Lưu bằng phím tắt | `fill_all` → `press ControlOrMeta+S` → `wait saved` |

Thứ tự các trường trong `fields` nên khớp thứ tự Tab của form. Nếu app macOS không nhận cách
điền trực tiếp (thường gặp ở app Electron/Java), đặt `input_mode: keyboard` trong `connect`.

### 3.3 Khai báo mapping

Mapping nối tên cột trong file với tên trường của profile, đồng thời có thể bắt buộc dữ liệu và
áp dụng transform:

```yaml
name: "CSV khách hàng → form"
profile: customer_form
fields:
  - { field: full_name, source: "Họ và Tên", required: true, transforms: [strip, collapse_spaces, title] }
  - { field: phone, source: "Điện Thoại", transforms: [strip, phone_vn] }
```

`field` phải trùng tên trường trong profile; `source` phải trùng tên cột trong file. Đánh dấu
`sensitive: true` trên trường trong profile cho dữ liệu nhạy cảm để che giá trị trong log.
Kịch bản có `fill`/`fill_all` phải có ít nhất một trường được ánh xạ; app không cho chạy/lưu
mapping rỗng. GUI giữ lại `const`, `default` và các tuỳ chọn đọc file khi mở, chỉnh và lưu YAML.
Giá trị cố định/mặc định xuất hiện dưới dạng mục riêng trong danh sách cột nguồn; sửa giá trị
này trực tiếp trong YAML. Khi mở mapping, app đọc lại file với `source_options` của mapping.

## 4. Kiểm duyệt trước khi nhập thật

Thực hiện lần lượt các bước sau trước lần chạy thật đầu tiên:

1. **Kiểm tra file nguồn:** xem tiêu đề, dữ liệu mẫu, sheet và định dạng.
2. **Kiểm tra mapping:** xác nhận cột nguồn nối đúng trường đích; rà soát transform và trường
   bắt buộc.
3. **Kiểm tra toàn bộ dữ liệu:** sửa dòng lỗi được báo trước khi chạy. Dòng không hợp lệ sẽ bị
   bỏ qua, không thao tác lên app đích.
4. **Chạy thử:** giữ chế độ **Chạy thử** mặc định để kiểm tra pipeline; dùng `-v` trong CLI để
   xem log thao tác. Chế độ này không điều khiển app đích nên chưa xác nhận locator/nút có hoạt động.
5. **Chạy thật từng dòng:** bật chế độ từng dòng hoặc dùng `--live --step` để kiểm tra thao tác
   thực tế một dòng mỗi lần.
6. **Chạy thật toàn bộ:** chỉ bỏ chọn Chạy thử/chọn `--live` sau khi đã kiểm duyệt dữ liệu,
   locator và thao tác.

Mọi chỉnh sửa phải được chốt và kiểm tra trước khi bắt đầu. Mỗi lần chạy dùng bản sao riêng của
profile, mapping và tuỳ chọn, không nhận thay đổi cấu hình giữa chừng.

Với app desktop `mac`/`uia`, chế độ nhập thật có đếm ngược 3 giây trước khi kết nối. Trong lúc
chạy, tránh dùng chuột/bàn phím vì AutoInput cần focus app đích. Driver `web` không chiếm
chuột/bàn phím.

## 5. Các lệnh thường dùng

Các lệnh sau chạy từ thư mục dự án. Khai báo file và mapping một lần.

Terminal macOS/Linux:

```bash
FILE=samples/customers.csv
MAP=mappings/demo_web_form.yaml
```

PowerShell:

```powershell
$FILE = "samples/customers.csv"
$MAP = "mappings/demo_web_form.yaml"
```

Sau đó dùng:

```bash
uv run autoinput gui                                      # mở giao diện
uv run autoinput inspect "$FILE"                         # xem file và các dòng đầu
uv run autoinput validate "$FILE" -m "$MAP"              # ánh xạ và kiểm tra mọi dòng
uv run autoinput profiles                                 # liệt kê profile có sẵn
uv run autoinput run "$FILE" -m "$MAP"                   # chạy thử (mặc định)
uv run autoinput run "$FILE" -m "$MAP" --live            # nhập thật
uv run autoinput -v run "$FILE" -m "$MAP" --rows 1-3     # chạy thử dòng 1–3, log chi tiết
uv run autoinput run "$FILE" -m "$MAP" --live --step     # nhập thật, xác nhận từng dòng
uv run autoinput ax-tree --app "TextEdit"                 # macOS: xem cây control
```

Các tuỳ chọn quan trọng:

| Tuỳ chọn | Tác dụng |
|---|---|
| `--live` | Tắt chạy thử và thao tác thật lên app đích |
| `--rows 1-5,9` | Chỉ chạy các dòng được chỉ định |
| `--step` | Chạy từng dòng, xác nhận để tiếp tục |
| `--stop-on-error` | Dừng lần chạy khi gặp lỗi |
| `-v` | Bật log chi tiết |

Trong GUI, các tuỳ chọn tương ứng có ở màn hình **Chạy nhập liệu**.

## 6. Theo dõi, điều khiển và xử lý kết quả

### Trạng thái của từng dòng

| Trạng thái | Ý nghĩa |
|---|---|
| **Đang nhập…** | Đang thực hiện kịch bản trên dòng |
| **Xong** | Kịch bản hoàn tất |
| **Dữ liệu lỗi** | Dữ liệu/mapping không hợp lệ; dòng bị bỏ qua |
| **Thất bại** | Một thao tác trong kịch bản lỗi, ví dụ không tìm thấy control hoặc hết thời gian chờ |
| **Cần đối soát** | Nhập thật đã bắt đầu thao tác nhưng bị lỗi/hủy; chưa biết dữ liệu đã được lưu hay chưa |

Nếu thao tác bị lỗi, AutoInput dừng kịch bản của dòng, chụp ảnh màn hình vào
`<data_dir>/screenshots/` nếu có thể, chạy `on_error_steps` nếu có, rồi ghi trạng thái và lý do.
Với lỗi thông thường, tuỳ chọn **Dừng khi lỗi** quyết định có tiếp tục với dòng kế tiếp hay không.

**Chống nhập trùng:** nếu nhập thật bị lỗi/hủy sau khi bắt đầu điền, bấm nút hoặc gửi phím,
dòng được đánh dấu **Cần đối soát** và lần chạy dừng lại. App không tự suy đoán thao tác lưu có
thành công hay không, kể cả khi lỗi nằm ở bước mở form mới sau khi lưu.
CLI trả mã thoát `1` nếu có dòng cần đối soát để script gọi bên ngoài không hiểu nhầm là thành công.

Khi kết thúc, xem số dòng xong/thất bại/lỗi dữ liệu và thời gian chạy. Có thể:

- **Chạy lại dòng lỗi** chỉ chọn dòng thất bại có thể thử lại và dòng dữ liệu lỗi; không chọn
  dòng đã xong hoặc **Cần đối soát**. Đối soát trên app đích trước; chỉ nhập lại thủ công bằng
  **Chỉ các dòng**/`--rows` sau khi chắc chắn dữ liệu chưa được lưu.
- **Xuất báo cáo** dạng CSV gồm dòng, trạng thái, lý do và ảnh chụp.
- Mở log để xem chi tiết theo luồng `source`, `mapping`, `driver` hoặc `engine`.

Nhật ký SQLite tái sử dụng một kết nối trong mỗi lần chạy và vẫn commit từng dòng trước khi
báo hoàn tất dòng đó. Cập nhật trạng thái giao diện được gom theo lô để giảm giật khi chạy nhanh.

### Phím điều khiển

| Hành động | macOS | Windows | Ghi chú |
|---|---|---|---|
| Bắt đầu | `⌘R` | `F5` / `Ctrl+R` | |
| Tạm dừng / tiếp tục | `⌘P` | `F6` / `Ctrl+P` | Dừng sau thao tác hiện tại |
| Dòng tiếp (chế độ từng dòng) | `⌘↩` | `F10` / `Ctrl+Enter` | |
| Dừng | `Esc` / `⌘.` | `Esc` / `Ctrl+.` | Khi cửa sổ AutoInput đang focus |
| **Dừng khẩn cấp toàn cục** | `⌃⌥Q` | `Ctrl+Alt+Q` | Dùng được khi app đích đang focus với driver desktop |

Có thể đổi phím dừng khẩn cấp bằng biến môi trường
`AUTOINPUT_KILL_SWITCH="<ctrl>+<alt>+x"`.

App kiểm tra lệnh dừng giữa từng trường của `fill_all` và giữa các bước. Một số lời gọi thư viện
hoặc hệ điều hành đang thực thi vẫn cần trả về/hết timeout trước khi dừng được. Khi đóng cửa sổ,
app yêu cầu hủy tác vụ và đợi luồng nền kết thúc rồi mới thoát; không cưỡng bức hủy luồng.

## 7. Truy vết và gỡ lỗi theo từng bước

Khi có lỗi, đi theo thứ tự dưới đây để khoanh vùng:

1. **File không đọc được hoặc cột sai:** chạy `inspect` để xem định dạng, tiêu đề và dữ liệu
   đầu vào.
2. **Mapping/trường bắt buộc sai:** chạy `validate`; xử lý các lỗi trước khi chạy.
3. **Chưa biết profile nào được cài:** chạy `profiles`.
4. **Không tìm thấy control:** dùng `ax-tree` trên macOS, Accessibility Inspector trên macOS,
   Accessibility Insights/`inspect.exe` trên Windows, hoặc DevTools trên web để kiểm tra locator.
5. **Kịch bản lỗi khi thao tác:** chạy thử một vài dòng với `-v`; kiểm tra log, ảnh chụp và
   `on_error_steps`.
6. **Chỉ lỗi trên app desktop:** xác nhận quyền hệ điều hành, trạng thái cửa sổ và focus.

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Thiếu quyền Accessibility | macOS chặn điều khiển app khác | Cấp quyền ở **System Settings → Privacy & Security**, rồi mở lại Terminal/AutoInput |
| `Control not found` | Locator sai hoặc màn hình chưa sẵn sàng | Kiểm tra locator; thêm `wait` trước thao tác |
| App không nhận giá trị trên macOS | Một số app Electron/Java không nhận điền trực tiếp | Đặt `input_mode: keyboard` trong `connect` |
| Dòng mới bị nhập đè lên dòng trước | Chưa chờ app lưu xong | Thêm `wait` sau bước submit |
| Lỗi tiếng Việt trên Windows | Bộ gõ Unikey/Telex ảnh hưởng việc gõ phím | Tắt bộ gõ khi chạy; ưu tiên cách điền trực tiếp |
| Một dòng thất bại giữa kịch bản | Locator, timeout hoặc trạng thái app không đúng | Xem lý do, ảnh chụp và log; sửa profile rồi chạy lại dòng lỗi |

Lệnh gỡ lỗi hay dùng:

```bash
uv run autoinput inspect samples/customers.csv
uv run autoinput validate samples/customers.csv -m mappings/demo_web_form.yaml
uv run autoinput -v run samples/customers.csv -m mappings/demo_web_form.yaml --rows 1-3
uv run autoinput run samples/customers.csv -m mappings/demo_web_form.yaml --live --step
uv run autoinput ax-tree --app "TextEdit"
```

Log nằm tại `<data_dir>/logs/autoinput.log`; ảnh lỗi ở `<data_dir>/screenshots/`.
`<data_dir>` mặc định là `~/Library/Application Support/AutoInput` trên macOS và
`%LOCALAPPDATA%\AutoInput` trên Windows. Không đưa dữ liệu nhạy cảm vào log; các trường có
`sensitive: true` được che.

## 8. Bản cài đặt cho macOS và Windows

### Cài đặt

| Hệ điều hành | File | Cách cài |
|---|---|---|
| macOS (Apple Silicon) | `AutoInput-<phiên bản>-macos-arm64.dmg` | Mở file `.dmg`, kéo **AutoInput** vào **Applications**. Lần đầu: chuột phải → **Open** (bản chưa ký Apple Developer ID). |
| Windows 10/11 (x64) | `AutoInput-<phiên bản>-windows-setup.exe` | Chạy file cài đặt; mặc định cài cho người dùng hiện tại, không cần quyền Admin. Có thêm bản `.zip` chạy trực tiếp. |

Bản cài đặt có sẵn driver web. Trình duyệt dùng Chromium của Playwright nếu đã cài, nếu không
sẽ dùng **Google Chrome** hoặc **Microsoft Edge** có trên máy. Cấu hình (profile, mapping),
nhật ký và ảnh lỗi nằm trong thư mục dữ liệu người dùng; mở nhanh bằng
**Xem → Mở thư mục cấu hình & nhật ký**. Cài lại/cập nhật không ghi đè file bạn đã sửa.

App chỉ chạy một cửa sổ: mở lần thứ hai sẽ đưa cửa sổ đang chạy lên trước.

### Tự build bộ cài

Bộ cài phải build trên chính hệ điều hành đích (macOS build `.dmg`, Windows build `.exe`):

Mở Terminal tại thư mục dự án. Dùng môi trường riêng `.venv-build` với Python 3.12,
không thay đổi môi trường chạy app `.venv`. Lệnh bên dưới tự cài đủ thư viện trước khi build;
nếu cài thất bại thì không chạy bước build.

**macOS (Terminal / zsh):**

```bash
UV_PROJECT_ENVIRONMENT=.venv-build uv run --python 3.12 --extra gui --extra web --extra mac --group build python packaging/build.py
```

**Windows (PowerShell):**

```powershell
$env:UV_PROJECT_ENVIRONMENT = ".venv-build"
uv run --python 3.12 --extra gui --extra web --extra windows --group build python packaging/build.py
Remove-Item Env:UV_PROJECT_ENVIRONMENT
```

Không thêm chú thích `# ...` ở cuối lệnh khi dán vào Terminal.
Không dùng riêng `uv run python packaging/build.py`: lệnh đó không chọn nhóm `build`,
nên có thể thiếu Pillow (`PIL`) hoặc PyInstaller. Nếu gặp lỗi thiếu thư viện,
chạy lại đúng lệnh của hệ điều hành ở trên.

Kết quả nằm trong `dist/`. Trên Windows cần cài [Inno Setup 6](https://jrsoftware.org/isinfo.php)
để tạo `setup.exe`; nếu không có, script vẫn tạo bản `.zip`. Workflow
`.github/workflows/build.yml` build cả hai hệ điều hành khi đẩy tag `v*` hoặc chạy thủ công.

Trước khi tạo bộ cài, `build.py` luôn chạy `packaging/smoke_test.py`: khởi động app ở chế độ ẩn
(không hiện cửa sổ), giới hạn số tiến trình và dừng ngay nếu app tự mở thêm bản sao. Build sẽ
**không** tạo bộ cài nếu kiểm tra này thất bại.

Đặt biến `CODESIGN_IDENTITY="Developer ID Application: …"` để ký app macOS; mặc định là ký
ad-hoc, nên máy khác sẽ cần chuột phải → **Open** ở lần mở đầu.
