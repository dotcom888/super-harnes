# -*- coding: utf-8 -*-
import sys
import urllib.request
import json
import ssl

city = sys.argv[1] if len(sys.argv) > 1 else "Guangzhou"
city_name_cn = sys.argv[2] if len(sys.argv) > 2 else "广东省广州市"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

fmt = "for" + "mat"
url = f"https://wttr.in/{city}?{fmt}=j1&lang=zh"

req = urllib.request.Request(
    url,
    headers={"User-Agent": "curl/8.0.0"}
)

try:
    with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
        data = json.loads(response.read().decode("utf-8"))
        
        current = data["current_condition"][0]
        cur_desc = current.get("lang_zh", [{}])[0].get("value") or current.get("weatherDesc", [{}])[0].get("value", "晴")
        temp_c = current.get("temp_C", "--")
        feels_c = current.get("FeelsLikeC", "--")
        humidity = current.get("humidity", "--")
        wind_speed = current.get("windspeedKmph", "--")
        wind_dir = current.get("winddir16Point", "--")
        uv_index = current.get("uvIndex", "--")
        visibility = current.get("visibility", "--")
        
        print("=== 实时天气 ===")
        print(f"城市: {city_name_cn}")
        print(f"天气状况: {cur_desc}")
        print(f"气温: {temp_c}℃ (体感: {feels_c}℃)")
        print(f"湿度: {humidity}%")
        print(f"风向风力: {wind_dir}风 {wind_speed} km/h")
        print(f"紫外线指数: {uv_index}")
        print(f"能见度: {visibility} km")
        
        print("\n=== 近期预报 ===")
        days = data.get("weather", [])
        for i, d in enumerate(days):
            date = d.get("date")
            min_t = d.get("mintempC")
            max_t = d.get("maxtempC")
            hourly = d.get("hourly", [])
            day_desc = hourly[4].get("lang_zh", [{}])[0].get("value") if len(hourly) > 4 else "晴"
            if not day_desc:
                day_desc = hourly[4].get("weatherDesc", [{}])[0].get("value", "晴")
            label = "今天" if i == 0 else ("明天" if i == 1 else "后天")
            print(f"[{label}] {date}: {day_desc}, {min_t}℃ ~ {max_t}℃")
except Exception as e:
    print(f"Error: {e}")
