from DrissionPage import ChromiumPage, ChromiumOptions
import json
import time

# ==========================================
# 1. HÀM LÕI: VƯỢT CLOUDFLARE & GỌI API
# ==========================================
def fetch_api_with_cf_bypass(page, url, max_retries=10):
    """Hàm dùng chung để truy cập URL và lấy dữ liệu JSON chuẩn."""
    try:
        page.get(url)
        
        for i in range(max_retries):
            # Dùng JS gọi lại API để lách tính năng tự format JSON của Chrome
            js_code = f'''
                return fetch("{url}")
                    .then(res => res.text())
                    .then(text => {{
                        try {{ return JSON.parse(text); }} catch (e) {{ return null; }}
                    }});
            '''
            data = page.run_js(js_code)
            
            if data:
                return data
            time.sleep(1) # Chờ 1s cho lần thử tiếp theo
            
        print(f"[-] Lỗi: Quá 10s không vượt được Cloudflare cho URL: {url}")
        return None
    except Exception as e:
        print(f"[-] Có lỗi xảy ra khi truy cập {url}: {e}")
        return None

# ==========================================
# 2. HÀM NGHIỆP VỤ (BUSINESS LOGIC)
# ==========================================
def get_metadata_by_route(page, route_id):
    url = f"https://apicms.ebms.vn/businfo/getvarsbyroute/{route_id}"
    return fetch_api_with_cf_bypass(page, url)

def get_stops_by_var(page, route_id, var_id):
    url = f"https://apicms.ebms.vn/businfo/getstopsbyvar/{route_id}/{var_id}"
    return fetch_api_with_cf_bypass(page, url)

def save_to_json(data, filepath="./data/1_bronze/bus_station.json"):
    if not data:
        print("Không có dữ liệu để lưu.")
        return
        
    # 'w' tự động ghi đè file cũ, không cần os.remove()
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"\n[V] Đã lưu thành công {len(data)} tuyến vào {filename}")

# ==========================================
# 3. LUỒNG ĐIỀU PHỐI (ETL)
# ==========================================
def run_crawl_scripts():
    ls_route_id = [347, 349, 368, 369, 393, 394, 1, 395, 396, 77, 350, 353, 37, 48, 32, 75, 36, 51, 20, 3, 112, 66, 128, 53, 131, 133, 45, 70, 130]
    result_data = []

    # Khởi tạo Trình duyệt MỘT LẦN DUY NHẤT
    print("Đang khởi động Trình duyệt...")
    co = ChromiumOptions()
    # co.headless(True) # Mở comment này nếu muốn chạy ngầm
    page = ChromiumPage(co)

    try:
        for route_id in ls_route_id:
            print(f"\n--- Đang xử lý Route ID: {route_id} ---")
            
            # BƯỚC 1: Lấy Metadata
            metadata = get_metadata_by_route(page, route_id)

            # Kiểm tra metadata hợp lệ (phải là list và có ít nhất 1 phần tử)
            if not metadata or not isinstance(metadata, list) or len(metadata) == 0:
                print(f"[-] Bỏ qua route {route_id}: Không có dữ liệu metadata.")
                time.sleep(1)
                continue

            # Rút trích thông tin an toàn (dùng .get để tránh KeyError)
            route_info = metadata[0]
            var_id = route_info.get("RouteVarId")
            route_no = route_info.get("RouteNo")

            if not var_id:
                print(f"[-] Bỏ qua route {route_id}: Không tìm thấy RouteVarId.")
                continue

            # BƯỚC 2: Lấy danh sách trạm (Stops)
            ls_stops = get_stops_by_var(page, route_id, var_id)

            if ls_stops:
                result_data.append({
                    "RouteID": route_no,
                    "Stations": ls_stops
                })
                print(f"[+] Lấy thành công dữ liệu trạm cho tuyến số: {route_no}")
            
            # Thời gian nghỉ giữa các vòng lặp
            time.sleep(0.5)

    finally:
        # LUÔN LUÔN đóng trình duyệt dù có lỗi hay không để giải phóng RAM
        page.quit()
        print("\nĐã dọn dẹp và đóng trình duyệt.")

    # BƯỚC 3: Lưu dữ liệu
    save_to_json(result_data)

if __name__ == "__main__":
    run_crawl_scripts()