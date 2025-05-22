# Ứng dụng Kiểm tra Thứ hạng URL trên Google

Ứng dụng web đơn giản để kiểm tra thứ hạng của một URL trên Google Search theo từ khóa.

## Cài đặt

1. Clone mã nguồn về máy của bạn.

2. Cài đặt các thư viện cần thiết:

```bash
pip install -r requirements.txt
```

3. Chạy ứng dụng:

```bash

```python app.py

4. Mở trình duyệt và truy cập: http://localhost:5000

## Tính năng

- Kiểm tra thứ hạng URL trên Google Search theo từ khóa
- Hỗ trợ tìm kiếm theo quốc gia
- Hiển thị vị trí trong top 100 hoặc thông báo không tìm thấy
- Lưu lịch sử kiểm tra và hiển thị 10 kết quả gần nhất

## Cách sử dụng

1. Nhập từ khóa cần kiểm tra
2. Nhập URL cần kiểm tra thứ hạng
3. Chọn quốc gia để tìm kiếm
4. Nhấn nút "Kiểm tra"
5. Xem kết quả thứ hạng và lịch sử kiểm tra

## Lưu ý

- Ứng dụng sử dụng cách thức scraping đơn giản để tìm kiếm trên Google
- Google có thể chặn các yêu cầu tự động nếu có quá nhiều truy vấn trong thời gian ngắn
- Dữ liệu lịch sử được lưu trong file JSON ở thư mục `data`

## Công nghệ sử dụng

- Frontend: HTML, CSS, JavaScript, Bootstrap 5
- Backend: Python, Flask
- Scraping: BeautifulSoup4, Requests
