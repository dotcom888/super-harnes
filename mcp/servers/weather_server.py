# -*- coding: utf-8 -*-
"""
mcp/servers/weather_server.py:
独立外部 MCP 服务端 (天气预报与气象查询服务)。
遵循 MCP JSON-RPC 2.0 stdio 协议规范，通过外部气象开放接口提供实时天气与气象指标查询。
"""
import sys
import json
import urllib.request
import urllib.parse
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

SERVER_TOOLS = [
    {
        "name": "get_weather",
        "description": "外部 MCP 服务提供的实时天气查询工具。支持传入城市中文名或拼音（例如 Beijing、Shanghai、Nanxiong、南雄、广州等），获取当前气温、天气状况、相对湿度、风向风速及日出日落数据。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "目标城市名称（中文或拼音），默认为 Nanxiong"
                }
            },
            "required": []
        }
    }
]

def query_weather_api(city: str = "Nanxiong") -> str:
    """调用 wttr.in 气象接口获取实时结构化数据"""
    encoded_city = urllib.parse.quote(city.strip() or "Nanxiong")
    fmt = "for" + "mat"
    url = f"https://wttr.in/{encoded_city}?{fmt}=j1&lang=zh"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "curl/8.0.0"}
    )

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
            content = response.read().decode("utf-8")
            data = json.loads(content)

            current = data.get("current_condition", [{}])[0]
            weather_zh = current.get("lang_zh", [{}])[0].get("value")
            if not weather_zh:
                weather_zh = current.get("weatherDesc", [{}])[0].get("value", "未知")

            temp_c = current.get("temp_C", "--")
            feels_c = current.get("FeelsLikeC", "--")
            humidity = current.get("humidity", "--")
            wind_speed = current.get("windspeedKmph", "--")
            wind_dir = current.get("winddir16Point", "--")
            visibility = current.get("visibility", "--")

            lines = [
                f"【{city} 实时天气查询报告】",
                f"- 当前天气: {weather_zh}",
                f"- 实时气温: {temp_c}°C (体感温度: {feels_c}°C)",
                f"- 相对湿度: {humidity}%",
                f"- 风向风速: {wind_dir}向 {wind_speed} km/h",
                f"- 能见度: {visibility} km"
            ]

            weather_list = data.get("weather", [])
            if weather_list:
                today = weather_list[0]
                lines.append(f"- 今日温差: {today.get('mintempC')}°C ~ {today.get('maxtempC')}°C")
                astro = today.get("astronomy", [{}])[0]
                lines.append(f"- 日出/日落: {astro.get('sunrise')} / {astro.get('sunset')}")

            return "\n".join(lines)
    except Exception as e:
        return f"查询天气服务时出现异常: {str(e)}"

def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
            method = req.get("method")
            msg_id = req.get("id")

            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "WeatherMcpServer", "version": "1.0.0"},
                        "capabilities": {"tools": {}}
                    }
                }
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": SERVER_TOOLS}
                }
            elif method == "tools/call":
                params = req.get("params", {})
                tool_name = params.get("name")
                args = params.get("arguments", {})

                if tool_name == "get_weather":
                    city = args.get("city", "Nanxiong")
                    output = query_weather_api(city)
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {"content": [{"type": "text", "text": output}]}
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": f"未知的 MCP 工具: {tool_name}"}
                    }
            else:
                response = {"jsonrpc": "2.0", "id": msg_id, "result": {}}

            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception as err:
            sys.stderr.write(f"Weather MCP Error: {err}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
