"""Weather query tool using the free Open-Meteo API (no API key required).

Supports city name geocoding, current weather, and multi-day forecast.
"""

import httpx
from langchain_core.tools import tool

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 15.0
USER_AGENT = (
    "Mozilla/5.0 (compatible; AssistantBird/0.1; +https://github.com/lkk031/bird-assistant)"
)

# WMO Weather Code → Chinese description
WMO_CODES: dict[int, str] = {
    0: "☀️ 晴天",
    1: "🌤️ 大部晴朗",
    2: "⛅ 多云",
    3: "☁️ 阴天",
    45: "🌫️ 有雾",
    48: "🌫️ 雾凇",
    51: "🌧️ 小毛毛雨",
    53: "🌧️ 中毛毛雨",
    55: "🌧️ 大毛毛雨",
    56: "🌧️ 小冻毛毛雨",
    57: "🌧️ 大冻毛毛雨",
    61: "🌧️ 小雨",
    63: "🌧️ 中雨",
    65: "🌧️ 大雨",
    66: "🌧️ 小冻雨",
    67: "🌧️ 大冻雨",
    71: "🌨️ 小雪",
    73: "🌨️ 中雪",
    75: "🌨️ 大雪",
    77: "🌨️ 雪粒",
    80: "🌧️ 小阵雨",
    81: "🌧️ 中阵雨",
    82: "🌧️ 大阵雨",
    85: "🌨️ 小阵雪",
    86: "🌨️ 大阵雪",
    95: "⛈️ 雷暴",
    96: "⛈️ 雷暴伴小冰雹",
    99: "⛈️ 雷暴伴大冰雹",
}

# Wind direction codes → Chinese
WIND_DIRECTIONS: dict[int, str] = {
    0: "北",
    45: "东北",
    90: "东",
    135: "东南",
    180: "南",
    225: "西南",
    270: "西",
    315: "西北",
    360: "北",
}


def _wmo_to_text(code: int) -> str:
    """Convert WMO weather code to Chinese description with emoji."""
    return WMO_CODES.get(code, f"未知天气 (code={code})")


def _wind_degree_to_direction(degree: float) -> str:
    """Convert wind direction in degrees to Chinese compass direction."""
    if degree < 0:
        return "未知"
    # Find the nearest compass direction key
    closest_key = min(WIND_DIRECTIONS.keys(), key=lambda k: abs(k - degree))
    return WIND_DIRECTIONS.get(closest_key, "未知")


@tool
async def get_weather(city: str, forecast_days: int = 1) -> str:
    """查询指定城市的天气信息，包括当前天气和未来预报。

    通过城市名称查询实时天气数据，包括温度、体感温度、湿度、
    风速风向和天气状况。

    Args:
        city: 城市名称，支持中文（如'北京'）或英文（如'Beijing'、'Tokyo'）。
              也支持省份/国家组合（如'上海,中国'）。
        forecast_days: 预报天数（1-7，默认1天）。设为1时只返回当前天气。

    Returns:
        格式化后的天气信息文本，包含天气图标和详细数据。
    """
    forecast_days = min(max(forecast_days, 1), 7)

    logger.info("get_weather: starting", city=city, forecast_days=forecast_days)

    # Step 1: Geocoding — city name → coordinates
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            geo_resp = client.get(
                GEOCODING_URL,
                params={
                    "name": city,
                    "count": 3,
                    "language": "zh",
                    "format": "json",
                },
                headers={"User-Agent": USER_AGENT},
            )
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()
    except httpx.TimeoutException:
        return "❌ 天气查询超时，请稍后重试。"
    except httpx.HTTPStatusError as e:
        logger.error("get_weather: geocoding HTTP error", status=e.response.status_code)
        return f"❌ 地理编码服务返回错误 (HTTP {e.response.status_code})，请稍后重试。"
    except Exception as e:
        logger.error("get_weather: geocoding failed", error=str(e))
        return f"❌ 地理编码失败: {str(e)}"

    results = geo_data.get("results", [])
    if not results:
        return (
            f"❌ 未找到城市「{city}」的匹配结果。"
            "请检查名称是否正确，或尝试更具体的写法（如「上海,中国」）。"
        )

    # Pick the best match (first result is most relevant by default)
    best = results[0]
    lat = best["latitude"]
    lon = best["longitude"]
    location_name = best.get("name", city)
    country = best.get("country", "")
    admin = best.get("admin1", "")  # Province/state
    location_label = location_name
    if admin and admin != location_name:
        location_label = f"{admin} {location_name}"
    if country:
        location_label += f", {country}"

    logger.info("get_weather: geocoded", location=location_label, lat=lat, lon=lon)

    # Step 2: Weather query
    daily_params = (
        "temperature_2m_max,temperature_2m_min,"
        "weather_code,precipitation_probability_max"
    )
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            weather_resp = client.get(
                WEATHER_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": (
                        "temperature_2m,relative_humidity_2m,apparent_temperature,"
                        "weather_code,wind_speed_10m,wind_direction_10m"
                    ),
                    "daily": daily_params,
                    "timezone": "auto",
                    "forecast_days": forecast_days,
                },
                headers={"User-Agent": USER_AGENT},
            )
            weather_resp.raise_for_status()
            weather_data = weather_resp.json()
    except httpx.TimeoutException:
        return "❌ 天气数据请求超时，请稍后重试。"
    except httpx.HTTPStatusError as e:
        logger.error("get_weather: weather API HTTP error", status=e.response.status_code)
        return f"❌ 天气服务返回错误 (HTTP {e.response.status_code})，请稍后重试。"
    except Exception as e:
        logger.error("get_weather: weather API failed", error=str(e))
        return f"❌ 天气数据获取失败: {str(e)}"

    # Step 3: Format output
    current = weather_data.get("current", {})
    daily = weather_data.get("daily", {})

    lines = [f"## 🌍 {location_label} 天气\n"]

    # --- Current weather ---
    if current:
        temp = current.get("temperature_2m", "N/A")
        apparent = current.get("apparent_temperature", "N/A")
        humidity = current.get("relative_humidity_2m", "N/A")
        weather_code = current.get("weather_code", 0)
        wind_speed = current.get("wind_speed_10m", "N/A")
        wind_dir_deg = current.get("wind_direction_10m", 0)

        weather_desc = (
            _wmo_to_text(int(weather_code))
            if weather_code is not None
            else "未知"
        )
        wind_dir = (
            _wind_degree_to_direction(float(wind_dir_deg))
            if wind_dir_deg is not None
            else "未知"
        )

        lines.append("### 📍 当前天气")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 🌡️ 温度 | **{temp}°C** |")
        lines.append(f"| 🥵 体感温度 | {apparent}°C |")
        lines.append(f"| 💧 湿度 | {humidity}% |")
        lines.append(f"| 🌤️ 天气 | {weather_desc} |")
        lines.append(f"| 🌬️ 风速 | {wind_speed} km/h ({wind_dir}风) |")
        lines.append("")

    # --- Daily forecast ---
    if daily:
        dates = daily.get("time", [])
        t_max = daily.get("temperature_2m_max", [])
        t_min = daily.get("temperature_2m_min", [])
        w_codes = daily.get("weather_code", [])
        precip = daily.get("precipitation_probability_max", [])

        if dates:
            lines.append("### 📅 天气预报")
            lines.append("")
            lines.append("| 日期 | 天气 | 最高温 | 最低温 | 降水概率 |")
            lines.append("|------|------|--------|--------|----------|")
            for i, date in enumerate(dates):
                code = int(w_codes[i]) if i < len(w_codes) else 0
                desc = _wmo_to_text(code)
                hi = f"{t_max[i]}°C" if i < len(t_max) else "N/A"
                lo = f"{t_min[i]}°C" if i < len(t_min) else "N/A"
                rain = f"{precip[i]}%" if i < len(precip) and precip[i] is not None else "-"
                lines.append(f"| {date} | {desc} | {hi} | {lo} | {rain} |")

    lines.append("")
    lines.append("---")
    lines.append(f"📊 数据来源: [Open-Meteo](https://open-meteo.com/) · {location_label}")

    logger.info("get_weather: success", city=city, location=location_label)

    return "\n".join(lines)
