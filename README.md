# BÁO CÁO PHÂN TÍCH VÀ GIẢI PHÁP SỰ CỐ SERVICE DISCOVERY (EUREKA)

## 1. Phân tích Nguyên nhân Gốc rễ & Các Yêu cầu

### Yêu cầu 1: Phân tích `spring.application.name` không nhất quán hoa/thường
- **Nguyên nhân:** Mặc định Eureka Server chuyển tất cả tên ứng dụng đăng ký thành chữ IN HOA (UPPERCASE). Ví dụ: `RestaurantService` -> `RESTAURANTSERVICE`.
- **Vấn đề gây ra:** Trong mô hình Microservices, các dịch vụ khác (như `order-service`) sử dụng Spring Cloud OpenFeign hoặc Spring Cloud LoadBalancer thường gọi tên dịch vụ bằng dạng kebab-case chuẩn (`http://restaurant-service/...`).
- Nếu đặt tên là `RestaurantService`, tên đăng ký sẽ thành `RESTAURANTSERVICE`. Khi `order-service` thực hiện query `restaurant-service`, LoadBalancer sẽ tìm tên `RESTAURANT-SERVICE` nhưng không tìm thấy instance nào, dẫn đến lỗi `No instances available for restaurant-service` hoặc 503 Service Unavailable.
- **Quy chuẩn đề xuất:** Thống nhất đặt tên tất cả dịch vụ ở dạng **kebab-case** chữ thường: `restaurant-service`, `order-service`, `payment-service`.

---

### Yêu cầu 2: Lỗi thiếu dấu `/` ở cuối `defaultZone`
- **Cấu hình sai:** `http://eureka-server:8761/eureka`
- **Cấu hình đúng:** `http://eureka-server:8761/eureka/`
- **Nguyên nhân:** Eureka Client SDK sử dụng HTTP client để ghép URL REST API endpoint. Nếu thiếu dấu `/` ở cuối `/eureka`, Client sẽ tạo ra URL sai dạng `http://eureka-server:8761/eurekaapps/restaurant-service` (thiếu dấu `/` phân cách giữa `/eureka` và `/apps`), làm hỏng các request đăng ký (HTTP 404 / 400).

---

### Yêu cầu 3: Cơ chế Heartbeat của Eureka & Xử lý khi Instance Crash
1. **Cơ chế Heartbeat chuẩn (Default):**
   - **Heartbeat Interval (`lease-renewal-interval-in-seconds`):** Mặc định **30 giây**, Eureka Client gửi 1 ping về Eureka Server để duy trì lease.
   - **Lease Expiration (`lease-expiration-duration-in-seconds`):** Mặc định **90 giây**. Nếu Eureka Server không nhận được heartbeat trong 90s, instance bị đánh dấu hết hạn.
   - **Eviction Task Timer (`eureka.server.eviction-interval-timer-in-ms`):** Mặc định chạy mỗi **60 giây** để quét và loại bỏ các instance quá hạn.
2. **Kịch bản restaurant-service-2 bị crash đột ngột:**
   - Vì crash không qua quy trình Graceful Shutdown (không gửi HTTP DELETE `/eureka/apps/{app}/{id}`), Eureka Server không biết ngay lập tức.
   - Eureka Server sẽ đợi hết 90s (Lease Expiration) + chu kỳ quét Eviction Task (tối đa 60s).
   - **Tổng thời gian loại bỏ:** Tối đa từ **90 đến 150 giây** (khoảng 1.5 - 2.5 phút).
3. **Lưu ý Self-Preservation Mode:** Nếu >15% heartbeat của toàn hệ thống bị mất trong khoảng thời gian ngắn (ví dụ do nghẽn mạng), Eureka Server kích hoạt chế độ tự bảo vệ (**Self-Preservation**) và **sẽ KHÔNG xóa** các instance hết hạn để tránh xóa nhầm service còn sống. Trong thời gian này, `order-service` vẫn nhận được IP của instance đã die nếu không có cấu hình Retry/Circuit Breaker.

---

### Yêu cầu 4: Đề xuất cấu hình phía Order-Service
- Không hardcode IP/URL.
- Bật **Dynamic Service Discovery** & **Client-side Load Balancing** (sử dụng `@LoadBalanced` với `RestTemplate`/`WebClient` hoặc `@FeignClient`).
- Tăng tốc độ cập nhật danh sách Registry Cache ở `order-service` bằng cách giảm `registry-fetch-interval-seconds` (ví dụ xuống 5s-10s trong môi trường cần phản ứng nhanh).
- Kết hợp **Resilience4j** (Retry + Circuit Breaker) để tự động chuyển sang instance sống khác nếu gặp instance chết trong lúc Eureka Server chưa kịp evict.

---

## 2. Cấu hình mẫu
Chi tiết xem trong các file:
- `restaurant-service-application.yml`
- `order-service-application.yml`

## 3. Hướng dẫn chạy file Mô phỏng Python (`main.py`)
File `main.py` mô phỏng toàn bộ chu trình Eureka Discovery, bao gồm:
- Đăng ký service với name chuẩn/không chuẩn.
- Gửi Heartbeat định kỳ.
- Mô phỏng crash của 1 instance và cơ chế Timeout/Eviction.
- Mô phỏng Order Service gọi Ribbon/LoadBalancer tra cứu instance.

### Lệnh chạy:
```bash
python main.py
```
