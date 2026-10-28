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

Tep `render.yaml` cau hinh web service Python mien phi tren Render va SQLite tam tai `/tmp/greentray.db`. Ban mien phi khong co persistent disk: Render co the cho dich vu ngu sau 15 phut khong co truy cap, va moi du lieu SQLite se mat khi dich vu ngu, khoi dong lai hoac deploy lai. Chi dung ban nay de thu nghiem, khong dung de luu giao dich/du lieu that.

1. Dam bao khong dua file `greentray.db` len repository; `.gitignore` da loai tru file nay.
2. Trong Render, tao Blueprint tu repository. Cau hinh mien phi khong can disk va co the mat toan bo du lieu SQLite khi dich vu ngu, khoi dong lai hoac deploy lai.
3. Khi duoc yeu cau, nhap `ADMIN_INITIAL_PASSWORD` dai it nhat 12 ky tu; day la mat khau rieng, khong luu trong ma nguon. Email admin mac dinh la `admin@greentray.local` va co the doi bang env var `ADMIN_EMAIL`.
4. Sau khi deploy thanh cong, dung URL `https://...onrender.com`. Dang nhap `/admin`; nut **QR trang khach** se tao QR theo URL HTTPS cong khai. QR admin la URL do them `/admin`.

Lan deploy cloud dau tien tao co so du lieu moi voi 60 mon kho; file `greentray.db` tren may tinh khong tu dong duoc tai len cloud. Tren goi mien phi, co so du lieu nay va moi tai khoan/giao dich phat sinh co the mat khi dich vu ngu, khoi dong lai hoac deploy lai. Khong dung cho nghiep vu that va khong chuyen du lieu cu len hosting.

## Dashboard quan tri

Trang `/admin` hien thi tong so hop, luot muon, luot tra, ty le tra, bieu do 7 ngay, va phan bo theo loai hop. Cac so lieu duoc tong hop tu giao dich SQLite. Uoc tinh nhua giam dung gia dinh 150 g cho moi luot tra, khong phai can do thuc te.

## Nhan va tra hop

- Khach hang chon **Xac nhan nhan hop** o hop san sang hoac **Xac nhan tra hop** o luot dang muon. He thong hien thi hop, loai hop, tien coc va thao tac de xac nhan truoc khi ghi giao dich.
- Kho chia thanh hai day rieng: **30 hop** ma `HP001`-`HP030` va **30 coc** ma `COC001`-`COC030`. Du lieu cu duoc giu lai, chuan hoa va bo sung khi server khoi dong.
- Trang quan tri hien thi ma hop, loai hop va trang thai; khong tao QR rieng cho tung hop.
- QR **trang khach** van kha dung trong muc quan tri; khi chay tren Render, QR dung URL HTTPS cong khai.
- Tien coc va hoan coc chi duoc ghi nhan trong SQLite, khong thuc hien thanh toan tien that.
- Voi ban chay cuc bo, server lang nghe tren giao dien mang de dien thoai cung Wi-Fi ket noi; Windows Firewall can cho phep TCP cong 8000 tren mang Private. Khong mo cong nay tren Public/Internet.

## Cau truc tep

- `server.py`: HTTP server, API, phan quyen, SQLite va QR.
- `database.sql`: schema SQLite, rang buoc du lieu va index.
- `index.html`: giao dien quan tri.
- `customer.html`: giao dien khach hang va xac nhan nhan/tra hop.
- `run.bat`, `requirements.txt`: cai thu vien tao QR va chay server.
- `supabase.html`, `schema.sql`, `README.supabase.md`, `vercel.json`: ban Supabase goc duoc giu lai tu starter.

Ban chay cuc bo lang nghe cong 8000 tren cac giao dien mang. Khong chuyen tiep cong router hoac mo truy cap tren mang Public/Internet; tien coc chi duoc ghi nhan noi bo va khong thuc hien thanh toan.
