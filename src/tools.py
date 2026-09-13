"""
🛠️ TOOL DEFINITIONS & EXECUTION BACKEND
Mã nguồn chứa danh sách Tool Schemas (JSON Schema) và Execution Layer phục vụ cho MCP Server.
"""

import json
from copy import deepcopy
from typing import Dict, Any

# ==============================================================================
# 1. KHAI BÁO TOOL SCHEMAS CHUẨN NATIVE JSON SCHEMA (TASK 1.2)
# ==============================================================================

TOOLS_SCHEMA = [
    # Tool 1: Tra cứu trạm sạc
    {
        "name": "charging_station_query",
        "description": "Tra cứu các trạm sạc xe điện VinFast theo vị trí, thời gian và loại cổng sạc.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Địa điểm hoặc khu vực cần tìm trạm sạc"
                },
                "datetime_str": {
                    "type": "string",
                    "description": "Thời gian dự kiến sạc, ví dụ: '14:00 15/09/2026'"
                },
                "connector_type": {
                    "type": "string",
                    "description": "Loại cổng sạc mong muốn, ví dụ: 'DC Fast' hoặc 'AC'"
                }
            },
            "required": ["location"]
        }
    },

    # --------------------------------------------------------------------------
    # Tool 2: Đặt trước cổng sạc
    # --------------------------------------------------------------------------
    {
        "name": "reserve_charging_slot",
        "description": "Đặt trước một cổng sạc tại trạm sạc xe điện VinFast.",
        "parameters": {
            "type": "object",
            "properties": {
                "station_id": {
                    "type": "string",
                    "description": "Mã trạm sạc, ví dụ: 'ST001'"
                },
                "connector_id": {
                    "type": "string",
                    "description": "Mã cổng sạc, ví dụ: 'C01'"
                },
                "datetime_str": {
                    "type": "string",
                    "description": "Thời gian đặt sạc, ví dụ: '14:00 15/09/2026'"
                },
                "vehicle_id": {
                    "type": "string",
                    "description": "Mã xe hoặc biển số xe"
                }
            },
            "required": [
                "station_id",
                "connector_id",
                "datetime_str",
                "vehicle_id"
            ]
        }
    }
]

# ==============================================================================
# 2. MÔ PHỎNG DỮ LIỆU & HÀM THỰC THI TOOL (EXECUTION LAYER)
# ==============================================================================

_MOCK_DATABASE_TEMPLATE = {
    "ST001": {
        "name": "VinFast Landmark 81",
        "location": "Bình Thạnh, TP.HCM",
        "status": "OPEN",
        "connectors": [
            {
                "connector_id": "C01",
                "type": "DC Fast",
                "status": "AVAILABLE"
            },
            {
                "connector_id": "C02",
                "type": "AC",
                "status": "OCCUPIED"
            }
        ]
    },
    "ST002": {
        "name": "VinFast Thảo Điền",
        "location": "Thảo Điền, TP.HCM",
        "status": "OPEN",
        "connectors": [
            {
                "connector_id": "C01",
                "type": "DC Fast",
                "status": "AVAILABLE"
            }
        ]
    }
}

MOCK_DATABASE = deepcopy(_MOCK_DATABASE_TEMPLATE)


def reset_mock_database() -> None:
    """Khôi phục dữ liệu giả lập để các test case không dùng chung trạng thái."""
    global MOCK_DATABASE
    MOCK_DATABASE = deepcopy(_MOCK_DATABASE_TEMPLATE)


def execute_charging_station_query(
    location: str,
    datetime_str: str = "",
    connector_type: str = ""
) -> str:
    """Tra cứu các trạm sạc đang mở và còn cổng phù hợp."""
    requested_location = location.strip().lower()
    requested_connector = connector_type.strip().lower()
    matches = []

    for station_id, station in MOCK_DATABASE.items():
        available_connectors = [
            connector for connector in station["connectors"]
            if connector["status"] == "AVAILABLE"
            and (
                not requested_connector
                or connector["type"].lower() == requested_connector
            )
        ]

        if (
            station["status"] == "OPEN"
            and requested_location in station["location"].lower()
            and available_connectors
        ):
            matches.append({
                "station_id": station_id,
                "name": station["name"],
                "location": station["location"],
                "available_connectors": available_connectors
            })

    if matches:
        return json.dumps({
            "status": "SUCCESS",
            "location": location,
            "datetime": datetime_str,
            "stations": matches
        }, ensure_ascii=False)

    return json.dumps({
        "status": "NOT_FOUND",
        "message": f"Không tìm thấy trạm sạc còn cổng phù hợp tại {location}."
    }, ensure_ascii=False)


def execute_reserve_charging_slot(
    station_id: str,
    connector_id: str,
    datetime_str: str,
    vehicle_id: str
) -> str:
    """Đặt trước một cổng sạc nếu cổng đó đang còn trống."""
    station = MOCK_DATABASE.get(station_id.strip().upper())

    if not station:
        return json.dumps({
            "status": "NOT_FOUND",
            "message": f"Không tìm thấy trạm sạc '{station_id}'."
        }, ensure_ascii=False)

    connector = next(
        (
            item for item in station["connectors"]
            if item["connector_id"].upper() == connector_id.strip().upper()
        ),
        None
    )

    if not connector:
        return json.dumps({
            "status": "NOT_FOUND",
            "message": f"Không tìm thấy cổng sạc '{connector_id}' tại trạm '{station_id}'."
        }, ensure_ascii=False)

    if connector["status"] != "AVAILABLE":
        return json.dumps({
            "status": "UNAVAILABLE",
            "message": f"Cổng sạc '{connector_id}' hiện không còn trống."
        }, ensure_ascii=False)

    connector["status"] = "RESERVED"

    return json.dumps({
        "status": "SUCCESS",
        "reservation_id": f"RS-{station_id}-{connector_id}-001",
        "station_id": station_id,
        "connector_id": connector_id,
        "datetime": datetime_str,
        "vehicle_id": vehicle_id,
        "message": "Đặt trước cổng sạc thành công."
    }, ensure_ascii=False)


# Router gọi tool thực tế
TOOL_ROUTER = {
    "charging_station_query": execute_charging_station_query,
    "reserve_charging_slot": execute_reserve_charging_slot
}

def dispatch_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Hàm trung chuyển thực thi tool"""
    if tool_name in TOOL_ROUTER:
        try:
            return TOOL_ROUTER[tool_name](**arguments)
        except Exception as e:
            return json.dumps({"status": "EXECUTION_ERROR", "error": str(e)}, ensure_ascii=False)
    return json.dumps({"status": "UNKNOWN_TOOL", "error": f"Tool '{tool_name}' không tồn tại!"}, ensure_ascii=False)
