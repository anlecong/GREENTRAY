# GreenTray - ban chay cuc bo

## Mo ung dung

1. Mo thu muc nay trong VS Code.
2. Chay `run.bat` (hoac mo terminal tai thu muc nay va chay `python server.py`).
3. Mo trang khach tai http://127.0.0.1:8000/; trang quan tri tai http://127.0.0.1:8000/admin.

Lan dau chay, ung dung tao `greentray.db` va 60 mon mau (30 hop, 30 coc). Ma nguon SQLite nam trong `database.sql`; server va giao dien nam trong `server.py`, `index.html`, `customer.html`.

## Tai khoan dang nhap

- Quan tri: `admin@greentray.local` / `Admin123!`
- Khach hang: `minhanh@greentray.local` / `Khach123!`

Khach hang co the chon **Dang ky**, nhap ho ten, email va mat khau tu 8 den 128 ky tu; dang ky thanh cong se tu dang nhap. Tai khoan quan tri duoc cap rieng va khong the tao tu bieu mau dang ky. Phien dang nhap duoc luu bang cookie HttpOnly va mat khau duoc bam PBKDF2.

Hai tai khoan tren chi danh cho ban chay cuc bo. Khong dung mat khau demo khi dua ung dung len Internet.

## Chuan bi trien khai Internet tren Render

Tep `render.yaml` cau hinh web service Python, HTTPS cua Render va SQLite tren persistent disk tai `/var/data/greentray.db`. Persistent disk va goi web service `starter` la tinh nang co phi; hay xem gia hien tai trong Render truoc khi tao dich vu. Cau hinh chi dung mot instance vi SQLite khong phu hop de chia se giua nhieu instance.

1. Dua ma nguon len mot GitHub repository rieng tu cua ban.
2. Dam bao khong dua file `greentray.db` len repository; `.gitignore` da loai tru file nay. Trong Render, tao Blueprint tu repository va xem ky goi dich vu/disk truoc khi xac nhan.
3. Khi duoc yeu cau, nhap `ADMIN_INITIAL_PASSWORD` dai it nhat 12 ky tu; day la mat khau rieng, khong luu trong ma nguon. Email admin mac dinh la `admin@greentray.local` va co the doi bang env var `ADMIN_EMAIL`.
4. Sau khi deploy thanh cong, dung URL `https://...onrender.com`. Dang nhap `/admin`; nut **QR trang khach** se tao QR theo URL HTTPS cong khai. QR admin la URL do them `/admin`.

Lan deploy cloud dau tien tao co so du lieu moi voi 60 mon kho; file `greentray.db` tren may tinh khong tu dong duoc tai len cloud. Khong chuyen du lieu cu len hosting neu chua chu dong sao luu va xac nhan can chuyen.

## Dashboard quan tri

Trang `/admin` hien thi tong so hop, luot muon, luot tra, ty le tra, bieu do 7 ngay, va phan bo theo loai hop. Cac so lieu duoc tong hop tu giao dich SQLite. Uoc tinh nhua giam dung gia dinh 150 g cho moi luot tra, khong phai can do thuc te.

## Nhận và trả hộp

- Khách hàng chọn **Xác nhận nhận hộp** ở hộp sẵn sàng hoặc **Xác nhận trả hộp** ở lượt đang mượn. Hệ thống hiển thị hộp, loại hộp, tiền cọc và thao tác để xác nhận trước khi ghi giao dịch.
- Kho chia thành hai dãy riêng: **30 hộp** mã `HP001`–`HP030` và **30 cốc** mã `COC001`–`COC030`. Dữ liệu cũ được giữ lại, chuẩn hóa và bổ sung khi server khởi động.
- Trang quản trị hiển thị mã hộp, loại hộp và trạng thái; không tạo QR riêng cho từng hộp.
- QR **trang khách** vẫn khả dụng trong mục quản trị; khi chạy trên Render, QR dùng URL HTTPS công khai.
- Tiền cọc và hoàn cọc chỉ được ghi nhận trong SQLite, không thực hiện thanh toán tiền thật.
- Với bản chạy cục bộ, server lắng nghe trên giao diện mạng để điện thoại cùng Wi‑Fi kết nối; Windows Firewall cần cho phép TCP cổng 8000 trên mạng Private. Không mở cổng này trên Public/Internet.

## Cau truc tep

- `server.py`: HTTP server, API, phan quyen, SQLite va QR.
- `database.sql`: schema SQLite, rang buoc du lieu va index.
- `index.html`: giao dien quan tri.
- `customer.html`: giao dien khach hang va xac nhan nhan/tra hop.
- `run.bat`, `requirements.txt`: cai thu vien tao QR va chay server.
- `supabase.html`, `schema.sql`, `README.supabase.md`, `vercel.json`: ban Supabase goc duoc giu lai tu starter.

Ban chay cuc bo lang nghe cong 8000 tren cac giao dien mang. Khong chuyen tiep cong router hoac mo truy cap tren mang Public/Internet; tien coc chi duoc ghi nhan noi bo va khong thuc hien thanh toan.
