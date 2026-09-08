import time
import threading
from typing import Dict, List

class MockEurekaServer:
    def __init__(self, lease_duration: float = 3.0, eviction_interval: float = 1.0):
        self.registry: Dict[str, Dict[str, float]] = {}
        self.lease_duration = lease_duration
        self.eviction_interval = eviction_interval
        self.running = True
        self.lock = threading.Lock()

    def register(self, app_name: str, instance_id: str) -> bool:
        app_name = app_name.upper()
        with self.lock:
            if app_name not in self.registry:
                self.registry[app_name] = {}
            self.registry[app_name][instance_id] = time.time()
            print(f"[Eureka Server] Registered {instance_id} under APP: '{app_name}'")
            return True

    def heartbeat(self, app_name: str, instance_id: str):
        app_name = app_name.upper()
        with self.lock:
            if app_name in self.registry and instance_id in self.registry[app_name]:
                self.registry[app_name][instance_id] = time.time()
                print(f"[Eureka Server] Heartbeat received from {instance_id}")

    def get_instances(self, app_name: str) -> List[str]:
        app_name = app_name.upper()
        with self.lock:
            instances = self.registry.get(app_name, {})
            return list(instances.keys())

    def run_eviction_task(self):
        while self.running:
            time.sleep(self.eviction_interval)
            now = time.time()
            with self.lock:
                for app_name, instances in list(self.registry.items()):
                    expired = [inst_id for inst_id, last_hb in instances.items() if now - last_hb > self.lease_duration]
                    for inst_id in expired:
                        del instances[inst_id]
                        print(f"[Eureka Server] EVICTED crashed instance: {inst_id} (No heartbeat for {self.lease_duration}s)")

class MockServiceInstance:
    def __init__(self, app_name: str, instance_id: str, eureka: MockEurekaServer, url_valid: bool = True):
        self.app_name = app_name
        self.instance_id = instance_id
        self.eureka = eureka
        self.url_valid = url_valid
        self.is_alive = True

    def start(self):
        if not self.url_valid:
            print(f"[{self.instance_id}] ERROR: Eureka URL invalid (missing trailing slash). Registration failed!")
            return
        self.eureka.register(self.app_name, self.instance_id)
        threading.Thread(target=self._send_heartbeats, daemon=True).start()

    def _send_heartbeats(self):
        while self.is_alive:
            time.sleep(1.0)
            if self.is_alive:
                self.eureka.heartbeat(self.app_name, self.instance_id)

    def crash(self):
        print(f"\n💥 CRASH! Instance {self.instance_id} unexpected shutdown (No graceful unregister)!")
        self.is_alive = False

class MockOrderService:
    def __init__(self, eureka: MockEurekaServer):
        self.eureka = eureka

    def call_restaurant_service(self, target_app_name: str):
        instances = self.eureka.get_instances(target_app_name)
        print(f"[Order Service] Querying '{target_app_name}' -> Found instances: {instances}")
        if not instances:
            print(f"[Order Service] ❌ FAIL: No available instances for '{target_app_name}'!")
        else:
            print(f"[Order Service] ✅ SUCCESS: Routing request to {instances[0]}")

def main():
    print("========================================================")
    print("   MÔ PHỎNG PHÂN TÍCH VÀ SỬA LỖI EUREKA SERVICE DISCOVERY")
    print("========================================================\n")

    eureka_server = MockEurekaServer(lease_duration=3.0, eviction_interval=1.0)
    eviction_thread = threading.Thread(target=eureka_server.run_eviction_task, daemon=True)
    eviction_thread.start()

    print("--- 1. MINH HỌA LỖI 1: Cấu hình sai defaultZone (Thiếu '/') ---")
    bad_inst = MockServiceInstance("restaurant-service", "restaurant-service-bad", eureka_server, url_valid=False)
    bad_inst.start()
    time.sleep(1)

    print("\n--- 2. MINH HỌA LỖI 2: Đặt tên 'RestaurantService' (Sai convention) ---")
    wrong_name_inst = MockServiceInstance("RestaurantService", "restaurant-service-1", eureka_server, url_valid=True)
    wrong_name_inst.start()
    time.sleep(1.5)

    order_service = MockOrderService(eureka_server)
    print("\nOrder-service thử gọi qua tên 'restaurant-service':")
    order_service.call_restaurant_service("restaurant-service")
    print("Order-service phải gọi chính xác 'RestaurantService' (Nhưng gây rối rắm quy chuẩn hệ thống):")
    order_service.call_restaurant_service("RestaurantService")

    print("\n--- 3. KHẮC PHỤC CẤU HÌNH ĐÚNG & SCALE 4 INSTANCES ---")
    instances = []
    for i in range(1, 5):
        inst = MockServiceInstance("restaurant-service", f"restaurant-service-{i}", eureka_server, url_valid=True)
        inst.start()
        instances.append(inst)
    
    time.sleep(2.0)
    order_service.call_restaurant_service("restaurant-service")

    print("\n--- 4. MINH HỌA CO SỰ CỐ: restaurant-service-2 CRASH ĐỘT NGỘT ---")
    instances[1].crash()

    print("\n[Ngay khi vừa crash] Eureka Server vẫn chưa loại bỏ instance chết vì chờ heartbeat timeout:")
    order_service.call_restaurant_service("restaurant-service")

    print("\nChờ 3.5 giây để Eureka Eviction Task làm việc...")
    time.sleep(3.5)

    print("\n[Sau timeout] Danh sách instance cập nhật mới nhất:")
    order_service.call_restaurant_service("restaurant-service")

    eureka_server.running = False
    print("\n================ Mô phỏng hoàn tất! ================")

if __name__ == "__main__":
    main()
