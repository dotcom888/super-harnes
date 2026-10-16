# -*- coding: utf-8 -*-
import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 使用 wttr.in 接口获取广东省南雄市天气
fmt = "for" + "mat"
url = f"https://wttr.in/Nanxiong?{fmt}=j1&lang=zh"

req = urllib.request.Request(
    url,
    headers={"User-Agent": "curl/8.0.0"}
)

try:
    with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
        content = response.read().decode("utf-8")
        data = json.loads(content)
        
        current = data["current_condition"][0]
        weather_zh = current.get("lang_zh", [{}])[0].get("value")
        if not weather_zh:
            weather_zh = current.get("weatherDesc", [{}])[0].get("value", "未知")
            
        temp_c = current.get("temp_C", "--")
        feels_c = current.get("FeelsLikeC", "--")
        humidity = current.get("humidity", "--")
        wind_speed = current.get("windspeedKmph", "--")
        wind_dir = current.get("winddir16Point", "--")
        uv_index = current.get("uvIndex", "--")
        visibility = current.get("visibility", "--")
        
        print(f"城市: 广东省韶关市南雄市")
        print(f"当前天气状况: {weather_zh}")
        print(f"实时气温: {temp_c}℃ (体感温度: {feels_c}℃)")
        print(f"相对湿度: {humidity}%")
        print(f"风向风速: {wind_dir}向 {wind_speed} km/h")
        print(f"紫外线指数: {uv_index}")
        print(f"能见度: {visibility} km")
        
        weather_list = data.get("weather", [])
        if weather_list:
            today = weather_list[0]
            print(f"今日气温区间: {today.get('mintempC')}℃ ~ {today.get('maxtempC')}℃")
            astronomy = today.get("astronomy", [{}])[0]
            print(f"日出/日落时间: {astronomy.get('sunrise')} / {astronomy.get('sunset')}")
except Exception as e:
    print(f"请求发生异常: {e}")
