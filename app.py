from flask import Flask, render_template, request, jsonify
import requests
import json
import os
import re
from datetime import datetime
import urllib.parse
import time
import random
from bs4 import BeautifulSoup
import logging

app = Flask(__name__)

# Cấu hình logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cấu hình API
API_CONFIG = {
    # SerpAPI - https://serpapi.com (100 tìm kiếm miễn phí mỗi tháng)
    'USE_SERPAPI': False,
    'SERPAPI_KEY': "your_serpapi_key",
    
    # ScraperAPI - https://www.scraperapi.com (1000 tìm kiếm miễn phí)
    'USE_SCRAPERAPI': True, 
    'SCRAPERAPI_KEY': "e44b5a962e5333e7e448537c839afbd4",
    
    # BrightData - https://brightdata.com
    'USE_BRIGHTDATA': False,
    'BRIGHTDATA_USERNAME': "your_username",
    'BRIGHTDATA_PASSWORD': "your_password",
    'BRIGHTDATA_HOST': "brd.superproxy.io",
    'BRIGHTDATA_PORT': "22225",
    
    # OpenAI - https://openai.com
    'USE_OPENAI': False,
    'OPENAI_API_KEY': "your_openai_api_key"
}

# Tạo thư mục data nếu chưa tồn tại
os.makedirs('data', exist_ok=True)

def normalize_url(url):
    """Chuẩn hóa URL để so sánh chính xác hơn"""
    try:
        # Loại bỏ protocol
        url = re.sub(r'^https?://(www\.)?', '', url)
        
        # Xử lý encoding URL
        url = urllib.parse.unquote(url)
        
        # Loại bỏ dấu / ở cuối
        url = url.rstrip('/')
        
        # Loại bỏ www. ở đầu nếu có
        if url.startswith('www.'):
            url = url[4:]
            
        # Loại bỏ tham số query string
        url = url.split('?')[0]
        
        # Loại bỏ tham số fragment
        url = url.split('#')[0]
        
        # Loại bỏ các đường dẫn phổ biến không cần thiết
        common_paths = ['/index.html', '/index.php', '/index.asp', '/index.jsp', '/default.aspx']
        for path in common_paths:
            if url.endswith(path):
                url = url[:-len(path)]
                break
                
        # Xử lý tên miền nhiều cấp
        parts = url.split('/')
        if len(parts) > 0:
            domain = parts[0]
            # Chỉ giữ lại hai cấp cuối cùng của tên miền (ví dụ: example.com)
            domain_parts = domain.split('.')
            if len(domain_parts) > 2:
                domain = '.'.join(domain_parts[-2:])
                parts[0] = domain
                url = '/'.join(parts)
        
        return url.lower().strip()
    except Exception as e:
        logger.error(f"Lỗi khi chuẩn hóa URL: {e}")
        return url.lower().strip()

def check_ranking_serpapi(keyword, target_url, country):
    """
    Kiểm tra thứ hạng của URL trên Google theo từ khóa sử dụng SerpAPI
    """
    try:
        logger.info(f"SerpAPI: Kiểm tra thứ hạng cho '{keyword}' - {target_url}")
        
        if not target_url.startswith('http'):
            target_url = 'https://' + target_url
        
        normalized_target = normalize_url(target_url)
        
        # Tạo URL SerpAPI
        params = {
            "api_key": API_CONFIG['SERPAPI_KEY'],
            "q": keyword,
            "num": 100,
            "engine": "google",
        }
        
        if country:
            params["gl"] = country
        
        response = requests.get("https://serpapi.com/search", params=params)
        response.raise_for_status()
        
        # Lưu kết quả JSON để debug
        with open('data/last_search.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps(response.json(), indent=2))
        
        serpapi_results = response.json()
        
        # Lấy kết quả tìm kiếm từ JSON
        organic_results = serpapi_results.get("organic_results", [])
        
        # Tìm URL trong kết quả
        for i, result in enumerate(organic_results, 1):
            link = result.get("link", "")
            if normalized_target in normalize_url(link):
                save_search_history(keyword, target_url, country, i)
                return i
        
        # Không tìm thấy URL trong kết quả
        save_search_history(keyword, target_url, country, -1)
        return -1
        
    except Exception as e:
        logger.error(f"Lỗi SerpAPI: {e}")
        return -1

def check_ranking_scraperapi(keyword, target_url, country):
    """
    Kiểm tra thứ hạng của URL trên Google bằng ScraperAPI
    Kiểm tra qua 3 trang đầu tiên để có kết quả chính xác hơn
    """
    try:
        logger.info(f"ScraperAPI: Kiểm tra thứ hạng cho '{keyword}' - {target_url}")
        
        if not target_url.startswith('http'):
            target_url = 'https://' + target_url
        
        normalized_target = normalize_url(target_url)
        domain_target = urllib.parse.urlparse(target_url).netloc
        if domain_target.startswith('www.'):
            domain_target = domain_target[4:]
            
        # Kiểm tra lần lượt 3 trang đầu tiên
        for page in range(3):
            # Tính giá trị start cho mỗi trang (0, 10, 20)
            start_param = page * 10
            
            # Tạo URL tìm kiếm Google cho trang hiện tại
            google_url = f"https://www.google.com/search?q={urllib.parse.quote(keyword)}&num=10"
            
            # Thêm tham số phân trang nếu không phải trang đầu tiên
            if page > 0:
                google_url += f"&start={start_param}"
            
            # Thêm tham số quốc gia nếu có
            if country:
                google_url += f"&gl={country}&hl={country}"
                # Thêm country restriction
                google_url += f"&cr=country{country.upper()}"
                
            # Thêm các tham số để tắt kết quả cá nhân hóa
            google_url += "&pws=0&filter=0&complete=0"
                
            # Tạo tham số cho ScraperAPI
            params = {
                "api_key": API_CONFIG['SCRAPERAPI_KEY'],
                "url": google_url,
                "render": "true",           # Kích hoạt JavaScript
                "country_code": country if country else "us",
                "premium": "true",          # Sử dụng proxy cao cấp nếu có
                "keep_headers": "true",     # Giữ nguyên headers
                "device_type": "desktop",   # Sử dụng thiết bị desktop
                "autoparse": "true"         # Tự động phân tích kết quả tìm kiếm
            }
            
            logger.info(f"ScraperAPI URL trang {page+1}: {google_url}")
            
            # Thêm độ trễ để tránh bị chặn (tăng độ trễ cho các trang sau)
            time.sleep(random.uniform(1, 2) * (page + 1))
            
            # Thực hiện gọi API với retry tự động nếu gặp lỗi 500
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                try:
                    # Gửi yêu cầu đến ScraperAPI
                    response = requests.get(
                        "https://api.scraperapi.com/", 
                        params=params,
                        timeout=60  # Tăng timeout lên 60 giây
                    )
                    # Kiểm tra kết quả
                    response.raise_for_status()
                    break  # Thoát khỏi vòng lặp retry nếu thành công
                except requests.RequestException as e:
                    retry_count += 1
                    logger.warning(f"Lỗi ScraperAPI lần {retry_count}/{max_retries}: {e}")
                    if retry_count < max_retries:
                        # Tăng thời gian chờ mỗi lần thử lại
                        time.sleep(random.uniform(3, 5))
                    else:
                        # Nếu đã thử lại đủ số lần mà vẫn thất bại, bỏ qua trang này
                        logger.error(f"Không thể truy cập trang {page+1} sau {max_retries} lần thử")
                        continue  # Chuyển sang trang tiếp theo
            
            # Nếu không nhận được phản hồi, chuyển sang trang tiếp theo
            if 'response' not in locals():
                continue
                
            # Lưu HTML để debug
            file_name = f'data/last_search_page{page+1}.html'
            with open(file_name, 'w', encoding='utf-8') as f:
                f.write(response.text)
                
            # Kiểm tra xem có phải JSON tự động phân tích không
            if 'application/json' in response.headers.get('Content-Type', ''):
                try:
                    json_data = response.json()
                    # Lưu JSON để debug
                    with open(f'data/last_search_page{page+1}.json', 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=2)
                        
                    # Nếu có kết quả tự động phân tích
                    if 'organic_results' in json_data:
                        logger.info(f"Nhận được kết quả JSON được phân tích tự động từ ScraperAPI cho trang {page+1}")
                        organic_results = json_data.get('organic_results', [])
                        
                        # Tìm URL trong kết quả
                        for i, result in enumerate(organic_results, 1):
                            link = result.get("link", "")
                            norm_link = normalize_url(link)
                            
                            # Kiểm tra cả URL đầy đủ và domain
                            if normalized_target in norm_link or domain_target in norm_link:
                                actual_rank = start_param + i
                                logger.info(f"Tìm thấy URL trong kết quả JSON trang {page+1}, thứ hạng: {actual_rank}")
                                save_search_history(keyword, target_url, country, actual_rank)
                                return actual_rank
                        
                        logger.info(f"Không tìm thấy URL trong kết quả JSON trang {page+1}, tiếp tục phân tích HTML")
                except Exception as e:
                    logger.warning(f"Lỗi khi phân tích JSON trang {page+1}: {e}")
            
            # Parse HTML để tìm kết quả
            html_content = response.text
            
            # Offset bắt đầu từ start_param
            offset = start_param
            
            # Đánh dấu nội dung HTML cho mỗi trang để dễ phân biệt
            modified_html = html_content.replace('<div class="g', f'<div data-page="{page+1}" class="g')
            
            # Phân tích HTML cho trang hiện tại
            rank = parse_google_html(modified_html, keyword, target_url, country, offset)
            
            # Nếu tìm thấy kết quả trong trang này, trả về ngay
            if rank > 0:
                return rank
        
        # Nếu đã kiểm tra tất cả 3 trang mà không tìm thấy
        logger.info(f"Không tìm thấy URL {target_url} trong 3 trang đầu tiên cho từ khóa '{keyword}'")
        save_search_history(keyword, target_url, country, -1)
        return -1
        
    except Exception as e:
        logger.error(f"Lỗi ScraperAPI: {e}")
        return -1

def check_ranking_brightdata(keyword, target_url, country):
    """
    Kiểm tra thứ hạng của URL trên Google bằng BrightData proxy
    """
    try:
        logger.info(f"BrightData: Kiểm tra thứ hạng cho '{keyword}' - {target_url}")
        
        if not target_url.startswith('http'):
            target_url = 'https://' + target_url
        
        # Thiết lập proxy BrightData
        proxy_url = f"http://{API_CONFIG['BRIGHTDATA_USERNAME']}:{API_CONFIG['BRIGHTDATA_PASSWORD']}@{API_CONFIG['BRIGHTDATA_HOST']}:{API_CONFIG['BRIGHTDATA_PORT']}"
        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }
        
        # Tạo URL tìm kiếm Google
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(keyword)}&num=100"
        if country:
            search_url += f"&gl={country}"
        
        # User agent giống Chrome thật
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        response = requests.get(search_url, headers=headers, proxies=proxies)
        response.raise_for_status()
        
        # Lưu HTML để debug
        with open('data/last_search.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        # Parse HTML để tìm kết quả
        return parse_google_html(response.text, keyword, target_url, country)
        
    except Exception as e:
        logger.error(f"Lỗi BrightData: {e}")
        return -1

def check_ranking_openai(keyword, target_url, country):
    """
    Sử dụng OpenAI để phân tích thứ hạng dựa trên các kết quả tìm kiếm đã lưu
    hoặc thực hiện tìm kiếm thủ công
    """
    try:
        logger.info(f"OpenAI: Phân tích thứ hạng cho '{keyword}' - {target_url}")
        
        if not target_url.startswith('http'):
            target_url = 'https://' + target_url
        
        # Đầu tiên, thử tìm kiếm bằng phương pháp thông thường
        html_content = None
        
        # Nếu có file HTML đã lưu, sử dụng nó
        if os.path.exists('data/last_search.html'):
            try:
                with open('data/last_search.html', 'r', encoding='utf-8') as f:
                    html_content = f.read()
            except:
                pass
        
        # Nếu không có HTML đã lưu, thực hiện tìm kiếm
        if not html_content:
            check_result = check_ranking_direct(keyword, target_url, country)
            # Nếu tìm thấy kết quả, trả về luôn
            if check_result != -1:
                return check_result
            
            # Đọc lại file HTML sau khi tìm kiếm
            try:
                with open('data/last_search.html', 'r', encoding='utf-8') as f:
                    html_content = f.read()
            except:
                return -1
        
        # Sử dụng OpenAI API để phân tích HTML
        openai_api_key = API_CONFIG['OPENAI_API_KEY']
        
        # Tạo prompt cho OpenAI
        prompt = f"""
        Tôi cần bạn phân tích HTML kết quả tìm kiếm Google và tìm thứ hạng của một URL cụ thể.
        
        TỪKHÓA: {keyword}
        URL CẦN TÌM: {target_url}
        
        Nhiệm vụ:
        1. Phân tích các kết quả tìm kiếm trong HTML
        2. Tìm vị trí xuất hiện đầu tiên của URL {target_url} trong kết quả
        3. Trả về số nguyên đại diện cho thứ hạng (vị trí) của URL trong kết quả tìm kiếm
        4. Nếu không tìm thấy URL, trả về -1
        
        Chỉ trả về một số nguyên duy nhất, không cần giải thích.
        """
        
        # Lấy nội dung ngắn gọn từ HTML để tránh quá dài
        html_summary = html_content[:5000] + ("\n... [HTML content truncated] ...\n" if len(html_content) > 5000 else "")
        html_summary += f"\n\n{html_content[-3000:]}" if len(html_content) > 8000 else ""
        
        # Gọi OpenAI API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_api_key}"
        }
        
        payload = {
            "model": "gpt-4o",  # Hoặc model phù hợp khác
            "messages": [
                {"role": "system", "content": "Bạn là trợ lý phân tích HTML chuyên nghiệp."},
                {"role": "user", "content": prompt + "\n\nHTML:\n" + html_summary}
            ],
            "temperature": 0,
            "max_tokens": 20
        }
        
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        
        # Phân tích kết quả từ OpenAI
        result = response.json()
        ai_response = result['choices'][0]['message']['content'].strip()
        
        # Trích xuất số từ response
        try:
            rank = int(re.search(r'-?\d+', ai_response).group())
            if rank > 0:
                save_search_history(keyword, target_url, country, rank)
                return rank
            else:
                save_search_history(keyword, target_url, country, -1)
                return -1
        except:
            # Nếu không thể trích xuất số, trả về không tìm thấy
            save_search_history(keyword, target_url, country, -1)
            return -1
            
    except Exception as e:
        logger.error(f"Lỗi OpenAI: {e}")
        return -1

def check_ranking_direct(keyword, target_url, country):
    """
    Kiểm tra thứ hạng của URL bằng cách mô phỏng chính xác truy vấn của trình duyệt
    Kiểm tra cả 3 trang đầu tiên của kết quả tìm kiếm Google (tổng 30 kết quả)
    """
    try:
        logger.info(f"Direct: Kiểm tra thứ hạng cho '{keyword}' - {target_url}")
        
        # Chuẩn hóa URL mục tiêu
        if not target_url.startswith('http'):
            target_url = 'https://' + target_url
        
        normalized_target = normalize_url(target_url)
        domain_target = urllib.parse.urlparse(target_url).netloc
        if domain_target.startswith('www.'):
            domain_target = domain_target[4:]
        
        # Tạo URL tìm kiếm Google giống hệt trình duyệt
        params = {
            'q': keyword,
            'num': '10',  # 10 kết quả mỗi trang
            'ie': 'utf-8',
            'oe': 'utf-8',
            'hl': 'vi',
            'pws': '0',       # Tắt kết quả cá nhân hóa
            'filter': '0',    # Hiển thị tất cả kết quả
            'complete': '0'   # Tắt tính năng tự động hoàn thành
        }
        
        if country:
            params['gl'] = country
            params['cr'] = 'country' + country.upper()  # Thêm tham số country restriction 
        
        # Danh sách User-Agent đa dạng và hiện đại
        user_agents = [
            # Chrome trên Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            # Chrome trên MacOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            # Safari trên MacOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
            # Firefox trên Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            # Edge trên Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
            # Firefox trên Linux
            "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
            # Chrome trên Linux
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        # Chọn ngẫu nhiên User-Agent
        selected_ua = random.choice(user_agents)
        is_chrome = "Chrome" in selected_ua
        is_firefox = "Firefox" in selected_ua
        is_safari = "Safari" in selected_ua and "Chrome" not in selected_ua
        is_edge = "Edg/" in selected_ua
        
        # Lưu User-Agent đã chọn để debug
        with open('data/last_ua.txt', 'w', encoding='utf-8') as f:
            f.write(f"User-Agent: {selected_ua}\n")
        
        # Headers tùy chỉnh theo trình duyệt đã chọn
        headers = {
            'User-Agent': selected_ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.google.com/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
        }
        
        # Tùy chỉnh thêm headers theo trình duyệt
        if is_chrome:
            headers.update({
                'sec-ch-ua': '"Google Chrome";v="120", "Chromium";v="120", "Not-A.Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            })
        elif is_firefox:
            headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'DNT': '1',
                'Sec-GPC': '1'
            })
        elif is_safari:
            headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7'
            })
        elif is_edge:
            headers.update({
                'sec-ch-ua': '"Microsoft Edge";v="121", "Not-A.Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            })
        
        # Lưu và sử dụng cookies
        cookies_file = 'data/google_cookies.json'
        cookies = {}
        if os.path.exists(cookies_file):
            try:
                with open(cookies_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
            except:
                cookies = {}
        
        # Tạo session để duy trì cookies và headers qua các request
        session = requests.Session()
        
        # Kiểm tra lần lượt 3 trang đầu tiên
        for page in range(3):
            # Tính giá trị start cho mỗi trang (0, 10, 20)
            start_param = page * 10
            
            # Cập nhật params với tham số phân trang
            page_params = params.copy()
            if page > 0:
                page_params['start'] = str(start_param)
            
            # Tạo URL tìm kiếm cho trang hiện tại
            search_url = "https://www.google.com/search?" + urllib.parse.urlencode(page_params)
            
            # Ghi thông tin URL vào file log
            with open('data/last_ua.txt', 'a', encoding='utf-8') as f:
                f.write(f"URL trang {page+1}: {search_url}\n")
            
            logger.info(f"Truy cập URL trang {page+1}: {search_url}")
            
            # Thêm độ trễ ngẫu nhiên tăng dần theo trang
            time.sleep(random.uniform(1.5, 3) * (page + 1))
            
            # Thử 3 lần nếu gặp lỗi
            max_retries = 3
            retry_count = 0
            response = None
            
            while retry_count < max_retries:
                try:
                    # Cài đặt kết nối giống trình duyệt thật
                    response = session.get(
                        search_url, 
                        headers=headers, 
                        cookies=cookies,
                        allow_redirects=True,
                        timeout=30 + (page * 10)  # Tăng timeout cho các trang sau
                    )
                    response.raise_for_status()
                    break  # Thoát vòng lặp nếu thành công
                except requests.RequestException as e:
                    retry_count += 1
                    logger.warning(f"Lỗi khi truy cập trang {page+1} ({retry_count}/{max_retries}): {e}")
                    # Thay đổi User-Agent mỗi lần thử lại
                    headers['User-Agent'] = random.choice(user_agents)
                    # Tăng thời gian chờ mỗi lần thử lại
                    time.sleep(random.uniform(3, 7))
            
            # Nếu đã thử hết lần mà vẫn thất bại
            if response is None:
                logger.error(f"Không thể truy cập Google trang {page+1} sau nhiều lần thử")
                continue  # Chuyển sang trang tiếp theo
            
            # Lưu cookies mới
            with open(cookies_file, 'w', encoding='utf-8') as f:
                json.dump(dict(response.cookies), f)
            
            # Lưu HTML để debug
            with open(f'data/last_search_page{page+1}.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            html_content = response.text
            
            # Kiểm tra reCAPTCHA hoặc yêu cầu bất thường
            if 'recaptcha' in html_content.lower() or 'unusual traffic' in html_content.lower() or 'robot' in html_content.lower():
                logger.warning(f"Google yêu cầu CAPTCHA ở trang {page+1} - bị chặn tự động truy cập")
                if page == 0:
                    return -2  # Mã đặc biệt cho CAPTCHA nếu ngay trang đầu tiên
                else:
                    # Nếu các trang sau bị chặn, tiếp tục với kết quả đã có (nếu có)
                    break
                
            # Đánh dấu nội dung HTML để phân biệt các trang
            modified_html = html_content.replace('<div class="g', f'<div data-page="{page+1}" class="g')
            
            # Parse HTML để tìm kết quả trong trang hiện tại
            rank = parse_google_html(modified_html, keyword, target_url, country, start_param)
            
            # Nếu tìm thấy trong trang này, trả về kết quả
            if rank > 0:
                return rank
        
        # Không tìm thấy trong cả 3 trang
        logger.warning(f"Không tìm thấy URL {target_url} trong 30 kết quả đầu tiên")
        save_search_history(keyword, target_url, country, -1)
        return -1
        
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra thứ hạng: {e}")
        return -1

def parse_google_html(html_content, keyword, target_url, country, offset=0):
    """
    Phân tích HTML kết quả tìm kiếm Google để tìm thứ hạng URL
    offset: Vị trí bắt đầu của kết quả (0 cho trang 1, 10 cho trang 2, 20 cho trang 3, v.v.)
    """
    try:
        # Chuẩn hóa URL
        normalized_target = normalize_url(target_url)
        domain_target = urllib.parse.urlparse(target_url).netloc
        if domain_target.startswith('www.'):
            domain_target = domain_target[4:]
            
        # Phân tích cả hai tên miền chính và phụ để tăng độ chính xác
        domain_parts = domain_target.split('.')
        root_domain = '.'.join(domain_parts[-2:]) if len(domain_parts) >= 2 else domain_target

        # Phân tích HTML bằng BeautifulSoup với parser html.parser
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Lưu debug chi tiết
        page_num = (offset // 10) + 1
        debug_file = f'data/selectors_debug_page{page_num}.txt'
        
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(f"URL cần tìm: {target_url}\n")
            f.write(f"Normalized URL: {normalized_target}\n")
            f.write(f"Domain cần tìm: {domain_target}\n")
            f.write(f"Root domain: {root_domain}\n")
            f.write(f"Trang: {page_num} (offset: {offset})\n\n")
        
        # 1. Tìm tất cả kết quả tìm kiếm sử dụng nhiều bộ chọn
        search_results = []
        
        # Các selectors phổ biến cho kết quả tìm kiếm trên Google - cập nhật 2023-2024
        selectors = [
            # Selectors cơ bản
            'div.g', 
            'div.Gx5Zad', 
            'div.N54PNb', 
            'div.yuRUbf', 
            'div[data-hveid]',
            'div.srKDX',
            'div.MjjYud',
            'div.kb0PBd',
            'div.hlcw0c',
            
            # Selectors kết hợp
            'div.g.tF2Cxc',
            'div.g.Pg70bf',
            
            # Selectors tiêu đề và container
            '.LC20lb',
            '.kvH3mc',
            '.kCrYT',
            
            # Selectors mới 2024
            'div.v5yQqb',
            'div.lyLwlc',
            'div.sATSHe',
            'div.nfSF8e',
            'a.cz88f8',
            'a.DaLSR',
            
            # Selectors kết quả tự nhiên
            'div.fP1Qef',
            'div.egMi0',
            'div.jtfYYd',
            'div.Z26q7c',
            
            # Selectors cho cite
            'div.VuuXrf',
            'div.byrV5b',
            'cite.iUh30',
            'span.qXLe6d',
            'span.fYyStc'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            search_results.extend(elements)
            logger.info(f"Trang {page_num}: Selector '{selector}': {len(elements)} phần tử")
            
            # Ghi chi tiết debug vào file
            with open(debug_file, 'a', encoding='utf-8') as f:
                f.write(f"Selector '{selector}': {len(elements)} phần tử\n")
                for i, elem in enumerate(elements[:3], 1):  # Lưu 3 phần tử đầu tiên để kiểm tra
                    links = elem.select('a[href]')
                    link_texts = [l.get('href', '') for l in links]
                    f.write(f"  - Phần tử #{i}: {len(links)} links: {', '.join(link_texts[:3])}\n")
        
        # Lọc các phần tử trùng lặp
        unique_results = []
        for result in search_results:
            if result not in unique_results:
                unique_results.append(result)
        
        logger.info(f"Trang {page_num}: Tổng số kết quả duy nhất: {len(unique_results)}")
        
        # 2. Tìm URL trong các kết quả tìm kiếm - kiểm tra nhiều cách khác nhau
        # Danh sách để theo dõi thứ hạng các URLs tìm thấy
        found_ranks = {}
        
        # Kiểm tra trong nội dung HTML của kết quả tìm kiếm
        for i, result in enumerate(unique_results, 1):
            result_html = str(result).lower()
            
            # Tìm domain trong HTML của kết quả (kiểm tra cả domain chính và phụ)
            if domain_target.lower() in result_html or root_domain.lower() in result_html:
                actual_position = offset + i
                logger.info(f"Tìm thấy domain trong kết quả #{actual_position} (trang {page_num})")
                
                # Debug thêm thông tin
                with open(debug_file, 'a', encoding='utf-8') as f:
                    f.write(f"\nTìm thấy domain trong kết quả #{actual_position} (trang {page_num})\n")
                    f.write(f"HTML của phần tử: {result_html[:200]}...\n")
                
                found_ranks[actual_position] = "domain_in_html"
                
            # Tìm URL đầy đủ trong kết quả
            if normalized_target in result_html:
                actual_position = offset + i
                logger.info(f"Tìm thấy URL trong kết quả #{actual_position} (trang {page_num})")
                
                # Debug thêm thông tin
                with open(debug_file, 'a', encoding='utf-8') as f:
                    f.write(f"\nTìm thấy URL trong kết quả #{actual_position} (trang {page_num})\n")
                    f.write(f"HTML của phần tử: {result_html[:200]}...\n")
                
                found_ranks[actual_position] = "url_in_html"
                
            # Tìm kiếm trong nội dung cite
            cite_elements = result.select('cite, .VuuXrf, .iUh30, .byrV5b, .qXLe6d, .fYyStc')
            for cite in cite_elements:
                cite_text = cite.get_text().lower()
                if domain_target.lower() in cite_text or root_domain.lower() in cite_text:
                    actual_position = offset + i
                    logger.info(f"Tìm thấy domain trong cite của kết quả #{actual_position} (trang {page_num})")
                    
                    with open(debug_file, 'a', encoding='utf-8') as f:
                        f.write(f"\nTìm thấy domain trong cite #{actual_position} (trang {page_num})\n")
                        f.write(f"Cite text: {cite_text}\n")
                    
                    found_ranks[actual_position] = "domain_in_cite"
                
            # Tìm kiếm trong thẻ liên kết
            links = result.select('a[href]')
            for link in links:
                href = link.get('href', '').lower()
                
                # Xử lý các URL chuyển hướng của Google
                if href.startswith('/url?') and 'url=' in href:
                    url_param = re.search(r'url=(http[^&]+)', href)
                    if url_param:
                        actual_url = urllib.parse.unquote(url_param.group(1))
                        norm_actual = normalize_url(actual_url)
                        
                        if (normalized_target in norm_actual or 
                            domain_target.lower() in norm_actual or 
                            root_domain.lower() in norm_actual):
                            
                            actual_position = offset + i
                            logger.info(f"Tìm thấy URL trong link redirect của kết quả #{actual_position} (trang {page_num})")
                            
                            # Debug thêm thông tin
                            with open(debug_file, 'a', encoding='utf-8') as f:
                                f.write(f"\nTìm thấy URL trong link redirect của kết quả #{actual_position} (trang {page_num})\n")
                                f.write(f"Link gốc: {href}\n")
                                f.write(f"Link sau khi giải mã: {actual_url}\n")
                            
                            found_ranks[actual_position] = "url_in_redirect"
                
                # Kiểm tra link trực tiếp
                elif href.startswith('http'):
                    norm_href = normalize_url(href)
                    if (normalized_target in norm_href or 
                        domain_target.lower() in norm_href or 
                        root_domain.lower() in norm_href):
                        
                        actual_position = offset + i
                        logger.info(f"Tìm thấy URL trong href trực tiếp của kết quả #{actual_position} (trang {page_num})")
                        
                        # Debug thêm thông tin
                        with open(debug_file, 'a', encoding='utf-8') as f:
                            f.write(f"\nTìm thấy URL trong href trực tiếp của kết quả #{actual_position} (trang {page_num})\n")
                            f.write(f"href: {href}\n")
                            f.write(f"normalized href: {norm_href}\n")
                        
                        found_ranks[actual_position] = "url_in_direct_link"
    
        # 3. Quét tất cả các liên kết (thẻ a) trực tiếp trên trang
        all_links = soup.find_all('a', href=True)
        result_links = []
        
        for link in all_links:
            href = link.get('href', '').lower()
            
            # Xử lý các URL chuyển hướng của Google
            if href.startswith('/url?') and 'url=' in href:
                url_param = re.search(r'url=(http[^&]+)', href)
                if url_param:
                    actual_url = urllib.parse.unquote(url_param.group(1))
                    result_links.append(actual_url)
                    
                    norm_actual = normalize_url(actual_url)
                    if (normalized_target in norm_actual or 
                        domain_target.lower() in norm_actual or 
                        root_domain.lower() in norm_actual):
                        
                        # Ước tính vị trí dựa trên số lượng link đã tìm thấy
                        position = len(result_links)
                        actual_position = offset + position
                        logger.info(f"Tìm thấy URL trong danh sách link redirect #{actual_position} (trang {page_num})")
                        
                        # Debug thêm thông tin
                        with open(debug_file, 'a', encoding='utf-8') as f:
                            f.write(f"\nTìm thấy URL trong danh sách link redirect #{actual_position} (trang {page_num})\n")
                            f.write(f"Link gốc: {href}\n")
                            f.write(f"Link sau khi giải mã: {actual_url}\n")
                        
                        found_ranks[actual_position] = "url_in_all_links_redirect"
            
            # Kiểm tra link trực tiếp
            elif href.startswith('http') and not re.search(r'google\.(com|co)', href):
                result_links.append(href)
                
                norm_href = normalize_url(href)
                if (normalized_target in norm_href or 
                    domain_target.lower() in norm_href or 
                    root_domain.lower() in norm_href):
                    
                    # Ước tính vị trí dựa trên số lượng link đã tìm thấy
                    position = len(result_links)
                    actual_position = offset + position
                    logger.info(f"Tìm thấy URL trong danh sách link #{actual_position} (trang {page_num})")
                    
                    # Debug thêm thông tin
                    with open(debug_file, 'a', encoding='utf-8') as f:
                        f.write(f"\nTìm thấy URL trong danh sách link #{actual_position} (trang {page_num})\n")
                        f.write(f"href: {href}\n")
                        f.write(f"normalized href: {norm_href}\n")
                    
                    found_ranks[actual_position] = "url_in_all_links_direct"

        # Lưu danh sách tất cả URL tìm thấy để debug
        all_urls_file = f'data/all_found_urls_page{page_num}.txt'
        with open(all_urls_file, 'w', encoding='utf-8') as f:
            f.write(f"Danh sách URL tìm thấy cho từ khóa: '{keyword}' (Trang {page_num})\n")
            f.write(f"URL cần tìm: {target_url} (normalized: {normalized_target})\n")
            f.write(f"Domain: {domain_target}, Root domain: {root_domain}\n\n")
            
            for i, url in enumerate(result_links, 1):
                norm_url = normalize_url(url)
                f.write(f"{offset + i}. {url}\n   Normalized: {norm_url}\n\n")
        
        # Nếu tìm thấy URL trong nhiều phương pháp, sử dụng thứ hạng nhỏ nhất (tốt nhất)
        if found_ranks:
            # Ghi lại các thứ hạng tìm thấy bằng các phương pháp khác nhau
            with open(debug_file, 'a', encoding='utf-8') as f:
                f.write("\nThứ hạng tìm thấy bằng các phương pháp khác nhau:\n")
                for rank, method in found_ranks.items():
                    f.write(f"Thứ hạng {rank}: {method}\n")
            
            best_rank = min(found_ranks.keys())
            logger.info(f"Thứ hạng tốt nhất tìm thấy: {best_rank} từ {len(found_ranks)} phương pháp khác nhau")
            
            # Lưu thứ hạng vào lịch sử
            save_search_history(keyword, target_url, country, best_rank)
            return best_rank
                
        # Không tìm thấy trong trang này
        logger.warning(f"Không tìm thấy URL {target_url} trong kết quả tìm kiếm trang {page_num}")
        return -1  # Trả về -1 để tiếp tục tìm kiếm ở trang khác
        
    except Exception as e:
        logger.error(f"Lỗi khi phân tích HTML trang {(offset // 10) + 1}: {e}")
        return -1

def check_ranking(keyword, target_url, country):
    """
    Kiểm tra thứ hạng của URL trên Google theo từ khóa
    Thử lần lượt các API đã cấu hình
    """
    # Nếu đã cấu hình ScraperAPI thì dùng nó ưu tiên
    if API_CONFIG['USE_SCRAPERAPI'] and API_CONFIG['SCRAPERAPI_KEY'] != "your_scraperapi_key":
        logger.info("Sử dụng ScraperAPI để tìm kiếm...")
        return check_ranking_scraperapi(keyword, target_url, country)
    
    # Nếu đã cấu hình SerpAPI thì dùng nó
    if API_CONFIG['USE_SERPAPI'] and API_CONFIG['SERPAPI_KEY'] != "your_serpapi_key":
        logger.info("Sử dụng SerpAPI để tìm kiếm...")
        return check_ranking_serpapi(keyword, target_url, country)
    
    # Nếu đã cấu hình BrightData thì dùng nó
    if API_CONFIG['USE_BRIGHTDATA'] and API_CONFIG['BRIGHTDATA_USERNAME'] != "your_username":
        logger.info("Sử dụng BrightData để tìm kiếm...")
        return check_ranking_brightdata(keyword, target_url, country)
    
    # Nếu đã cấu hình OpenAI thì dùng nó sau khi thử phương pháp trực tiếp
    if API_CONFIG['USE_OPENAI'] and API_CONFIG['OPENAI_API_KEY'] != "your_openai_api_key":
        logger.info("Sử dụng OpenAI để phân tích thứ hạng...")
        return check_ranking_openai(keyword, target_url, country)
    
    # Mặc định dùng phương pháp trực tiếp
    logger.info("Sử dụng phương pháp mô phỏng trình duyệt...")
    return check_ranking_direct(keyword, target_url, country)

def save_search_history(keyword, url, country, rank):
    """
    Lưu lịch sử tìm kiếm vào file JSON
    """
    history_file = 'data/search_history.json'
    history = []
    
    # Đọc lịch sử hiện có nếu có
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            history = []
    
    # Thêm kết quả tìm kiếm mới
    history.append({
        'keyword': keyword,
        'url': url,
        'country': country,
        'rank': rank,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    # Lưu lại lịch sử
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/batch')
def batch_page():
    """
    Trang kiểm tra thứ hạng hàng loạt
    """
    return render_template('batch.html')

@app.route('/settings')
def settings_page():
    """
    Trang cài đặt ứng dụng
    """
    return render_template('settings.html')

@app.route('/debug')
def debug_info():
    """
    Cung cấp thông tin debug về lần tìm kiếm gần nhất
    """
    last_search_html = 'Không có dữ liệu'
    if os.path.exists('data/last_search.html'):
        try:
            with open('data/last_search.html', 'r', encoding='utf-8') as f:
                last_search_content = f.read()
                # Chỉ trả về một phần để tránh quá tải
                last_search_html = last_search_content[:5000] + '...'
        except:
            last_search_html = 'Lỗi khi đọc file HTML'
    
    return render_template('debug.html', last_search_html=last_search_html)

@app.route('/api/check-ranking', methods=['POST'])
def api_check_ranking():
    data = request.json
    keyword = data.get('keyword', '')
    url = data.get('url', '')
    country = data.get('country', '')
    
    if not keyword or not url:
        return jsonify({'error': 'Thiếu từ khóa hoặc URL'}), 400
    
    # Thêm timestamp để ghi log
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"[{timestamp}] Kiểm tra thứ hạng: '{keyword}' - {url} - {country}")
    
    rank = check_ranking(keyword, url, country)
    
    # Xử lý các mã lỗi khác nhau
    if rank == -2:
        return jsonify({
            'keyword': keyword,
            'url': url,
            'country': country,
            'rank': rank,
            'error': 'Google đang yêu cầu CAPTCHA. Vui lòng thử lại sau hoặc truy cập Google trực tiếp.',
            'error_code': 'CAPTCHA_REQUIRED'
        })
    elif rank == -3:
        return jsonify({
            'keyword': keyword,
            'url': url,
            'country': country,
            'rank': rank,
            'error': 'Không thể kết nối đến Google sau nhiều lần thử. Vui lòng kiểm tra kết nối mạng và thử lại sau.',
            'error_code': 'CONNECTION_ERROR'
        })
    elif rank == -1:
        # Không tìm thấy URL trong kết quả
        logger.info(f"[{timestamp}] Không tìm thấy URL {url} trong kết quả tìm kiếm cho '{keyword}'")
        return jsonify({
            'keyword': keyword,
            'url': url,
            'country': country,
            'rank': rank,
            'error_code': 'URL_NOT_FOUND'
        })
    else:
        # Tìm thấy URL ở thứ hạng cụ thể
        logger.info(f"[{timestamp}] URL {url} có thứ hạng {rank} cho từ khóa '{keyword}'")
        return jsonify({
            'keyword': keyword,
            'url': url,
            'country': country,
            'rank': rank
        })

@app.route('/api/history')
def api_history():
    history_file = 'data/search_history.json'
    
    if not os.path.exists(history_file):
        return jsonify([])
    
    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.load(f)
    
    return jsonify(history)

@app.route('/api/batch-check', methods=['POST'])
def api_batch_check():
    """
    API để kiểm tra thứ hạng theo danh sách URL
    Kiểm tra qua 3 trang đầu tiên của kết quả Google
    """
    data = request.json
    keyword = data.get('keyword', '').strip()
    urls = data.get('urls', [])
    country = data.get('country', '')
    base_url = data.get('base_url', '').strip()
    
    if not keyword or not urls:
        return jsonify({'error': 'Thiếu từ khóa hoặc danh sách URL'}), 400
    
    # Giới hạn số lượng URL mỗi lần kiểm tra
    max_urls = 20
    if len(urls) > max_urls:
        return jsonify({'error': f'Số lượng URL vượt quá giới hạn ({max_urls})'}), 400
    
    # Timestamp để ghi log
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"[{timestamp}] Batch Check: '{keyword}' - {len(urls)} URLs - {country} - Kiểm tra 3 trang đầu")
    
    # Thống kê kết quả
    stats = {
        'total': len(urls),
        'found': 0,
        'not_found': 0,
        'errors': 0,
        'page1': 0,  # Số kết quả tìm thấy ở trang 1
        'page2': 0,  # Số kết quả tìm thấy ở trang 2
        'page3': 0,  # Số kết quả tìm thấy ở trang 3
    }
    
    results = []
    
    # Thực hiện kiểm tra cho từng URL
    for i, url_suffix in enumerate(urls):
        # Chuẩn hóa mã sản phẩm (loại bỏ khoảng trắng và ký tự đặc biệt)
        url_suffix = url_suffix.strip()
        
        # Tạo URL đầy đủ nếu có base_url
        if base_url:
            # Đảm bảo base_url không có dấu / ở cuối
            base_url = base_url.rstrip('/')
            # Đảm bảo url_suffix không có dấu / ở đầu
            url_suffix = url_suffix.lstrip('/')
            # Tạo URL đầy đủ với dấu / ở cuối
            full_url = f"{base_url}/{url_suffix}"
            if not full_url.endswith('/'):
                full_url += '/'
        else:
            full_url = url_suffix
            if not full_url.endswith('/'):
                full_url += '/'
        
        # Thêm delay để tránh bị chặn, tăng dần theo số lượng nhiệm vụ
        if i > 0:
            delay_time = random.uniform(1.5, 3) * (1 + (i * 0.15))
            logger.info(f"Chờ {delay_time:.2f} giây trước khi kiểm tra URL tiếp theo")
            time.sleep(delay_time)
        
        try:
            # Kiểm tra thứ hạng
            rank = check_ranking(keyword, full_url, country)
            
            # Thêm kết quả vào danh sách
            result = {
                'keyword': keyword,
                'url': full_url,
                'url_suffix': url_suffix,
                'country': country,
                'rank': rank,
                'checked_pages': 3  # Luôn kiểm tra 3 trang đầu tiên
            }
            
            # Thêm thông tin trang và vị trí trên trang nếu tìm thấy URL
            if rank > 0:
                stats['found'] += 1
                page_num = (rank - 1) // 10 + 1
                position_on_page = ((rank - 1) % 10) + 1
                result['page'] = page_num
                result['position_on_page'] = position_on_page
                result['status'] = 'found'
                result['message'] = f"Tìm thấy ở vị trí {rank} (trang {page_num}, vị trí {position_on_page})"
                
                # Cập nhật thống kê theo trang
                if page_num == 1:
                    stats['page1'] += 1
                elif page_num == 2:
                    stats['page2'] += 1
                elif page_num == 3:
                    stats['page3'] += 1
            
            # Thêm mã lỗi nếu có
            elif rank == -2:
                stats['errors'] += 1
                result['error_code'] = 'CAPTCHA_REQUIRED'
                result['error_reason'] = 'Google yêu cầu xác thực CAPTCHA'
                result['status'] = 'error'
            elif rank == -3:
                stats['errors'] += 1
                result['error_code'] = 'CONNECTION_ERROR'
                result['error_reason'] = 'Không thể kết nối đến Google sau nhiều lần thử'
                result['status'] = 'error'
            elif rank == -1:
                stats['not_found'] += 1
                result['error_code'] = 'URL_NOT_FOUND'
                result['error_reason'] = 'URL không xuất hiện trong 30 kết quả đầu tiên (3 trang)'
                result['status'] = 'not_found'
                
            results.append(result)
            
            # Ghi log kết quả
            logger.info(f"[{timestamp}] URL {full_url} có thứ hạng {rank} cho từ khóa '{keyword}'")
            
        except Exception as e:
            stats['errors'] += 1
            logger.error(f"Lỗi khi kiểm tra {full_url}: {str(e)}")
            results.append({
                'keyword': keyword,
                'url': full_url,
                'url_suffix': url_suffix,
                'country': country,
                'rank': -4,  # Mã lỗi đặc biệt cho lỗi xử lý
                'error_code': 'PROCESSING_ERROR',
                'error_reason': str(e),
                'status': 'error'
            })
    
    return jsonify({
        'keyword': keyword,
        'country': country,
        'results': results,
        'timestamp': timestamp,
        'stats': stats,
        'checked_pages': 3  # Luôn kiểm tra 3 trang đầu tiên
    })

@app.route('/api/multi-check', methods=['POST'])
def api_multi_check():
    """
    API để kiểm tra thứ hạng cho nhiều từ khóa khác nhau với cùng một URL
    Kiểm tra qua 3 trang đầu tiên của kết quả Google cho mỗi từ khóa
    """
    data = request.json
    tasks = data.get('tasks', [])
    
    if not tasks:
        return jsonify({'error': 'Thiếu danh sách công việc kiểm tra'}), 400
    
    # Giới hạn số lượng công việc kiểm tra
    max_tasks = 20
    if len(tasks) > max_tasks:
        return jsonify({'error': f'Số lượng công việc kiểm tra vượt quá giới hạn ({max_tasks})'}), 400
    
    # Timestamp để ghi log
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"[{timestamp}] Multi Check: {len(tasks)} từ khóa - Kiểm tra qua 3 trang đầu tiên")
    
    # Số nhiệm vụ thành công và thất bại
    success_count = 0
    failed_count = 0
    
    results = []
    
    # Thực hiện từng công việc kiểm tra
    for i, task in enumerate(tasks):
        keyword = task.get('keyword', '').strip()
        url = task.get('url', '').strip()
        country = task.get('country', 'vn')
        
        if not keyword or not url:
            failed_count += 1
            continue
        
        # Thêm delay để tránh bị chặn, tăng dần giữa các lần kiểm tra
        if i > 0:
            delay_time = random.uniform(1.5, 3) * (1 + (i * 0.2))  # Tăng dần thời gian chờ theo số lượng nhiệm vụ
            logger.info(f"Chờ {delay_time:.2f} giây trước khi kiểm tra nhiệm vụ tiếp theo")
            time.sleep(delay_time)
        
        try:
            # Kiểm tra thứ hạng
            rank = check_ranking(keyword, url, country)
            success_count += 1
            
            # Thêm kết quả vào danh sách
            result = {
                'keyword': keyword,
                'url': url,
                'country': country,
                'rank': rank,
                'checked_pages': 3  # Luôn kiểm tra 3 trang đầu tiên
            }
            
            # Thêm thông tin chi tiết về kết quả tìm kiếm
            if rank > 0:
                page_num = (rank - 1) // 10 + 1
                position_on_page = ((rank - 1) % 10) + 1
                result['page'] = page_num
                result['position_on_page'] = position_on_page
                result['status'] = 'found'
                result['message'] = f"Tìm thấy URL ở vị trí {rank} (trang {page_num}, vị trí {position_on_page})"
            
            # Thêm mã lỗi nếu có
            elif rank == -2:
                result['error_code'] = 'CAPTCHA_REQUIRED'
                result['error_reason'] = 'Google yêu cầu xác thực CAPTCHA'
                result['status'] = 'error'
                failed_count += 1
            elif rank == -3:
                result['error_code'] = 'CONNECTION_ERROR'
                result['error_reason'] = 'Không thể kết nối đến Google sau nhiều lần thử'
                result['status'] = 'error'
                failed_count += 1
            elif rank == -1:
                result['error_code'] = 'URL_NOT_FOUND'
                result['error_reason'] = 'URL không xuất hiện trong 30 kết quả đầu tiên (3 trang)'
                result['status'] = 'not_found'
                
            results.append(result)
            
            # Ghi log kết quả
            logger.info(f"[{timestamp}] Từ khóa '{keyword}': URL {url} có thứ hạng {rank}")
            
        except Exception as e:
            failed_count += 1
            logger.error(f"Lỗi khi kiểm tra từ khóa '{keyword}': {str(e)}")
            results.append({
                'keyword': keyword,
                'url': url,
                'country': country,
                'rank': -4,  # Mã lỗi đặc biệt cho lỗi xử lý
                'error_code': 'PROCESSING_ERROR',
                'error_reason': str(e),
                'status': 'error'
            })
    
    return jsonify({
        'results': results,
        'timestamp': timestamp,
        'total': len(tasks),
        'success': success_count,
        'failed': failed_count,
        'checked_pages': 3  # Luôn kiểm tra 3 trang đầu tiên
    })

@app.route('/data/<path:filename>')
def serve_data_file(filename):
    """
    Cung cấp các file dữ liệu và debug thông qua HTTP
    """
    # Kiểm tra đường dẫn an toàn
    safe_path = os.path.normpath(filename)
    if '..' in safe_path or safe_path.startswith('/'):
        return "Access denied", 403
        
    # Chỉ cho phép một số loại file an toàn
    allowed_extensions = ['.html', '.txt', '.json', '.log']
    file_ext = os.path.splitext(safe_path)[1].lower()
    
    if file_ext not in allowed_extensions:
        return "File không được hỗ trợ", 403
    
    file_path = os.path.join('data', safe_path)
    
    # Kiểm tra file tồn tại
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return "File không tồn tại", 404
        
    # Xác định content type
    content_type = 'text/plain'
    if file_ext == '.html':
        content_type = 'text/html'
    elif file_ext == '.json':
        content_type = 'application/json'
    
    # Đọc và trả về nội dung file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': f'{content_type}; charset=utf-8'}
    except Exception as e:
        logger.error(f"Lỗi khi đọc file {file_path}: {e}")
        return f"Lỗi khi đọc file: {str(e)}", 500

@app.route('/config', methods=['GET', 'POST'])
def api_config():
    """
    Lấy hoặc cập nhật cấu hình
    """
    if request.method == 'GET':
        # Trả về cấu hình hiện tại (xóa các API key)
        safe_config = {k: (v if not k.endswith('KEY') and not k.endswith('PASSWORD') else '') for k, v in API_CONFIG.items()}
        return jsonify(safe_config)
    
    elif request.method == 'POST':
        # Cập nhật cấu hình
        config_data = request.json
        
        for key, value in config_data.items():
            if key in API_CONFIG:
                API_CONFIG[key] = value
        
        # Lưu cấu hình vào file
        with open('data/config.json', 'w', encoding='utf-8') as f:
            # Lưu cấu hình an toàn (không bao gồm API key)
            safe_config = {k: (v if not k.endswith('KEY') and not k.endswith('PASSWORD') else '') for k, v in API_CONFIG.items()}
            json.dump(safe_config, f, ensure_ascii=False, indent=2)
        
        return jsonify({'status': 'success', 'message': 'Cấu hình đã được cập nhật'})

if __name__ == '__main__':
    # Tải cấu hình từ file nếu có
    config_file = 'data/config.json'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                # Cập nhật cấu hình từ file
                for key, value in saved_config.items():
                    if key in API_CONFIG and value:  # Chỉ cập nhật giá trị không rỗng
                        API_CONFIG[key] = value
        except Exception as e:
            logger.error(f"Lỗi khi tải cấu hình: {e}")
    
    app.run(debug=True) 