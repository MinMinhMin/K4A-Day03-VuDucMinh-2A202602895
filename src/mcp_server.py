"""
🔌 MODEL CONTEXT PROTOCOL (MCP) SERVER MODULE
Mô phỏng kiến trúc MCP Server (Client-Server Architecture) cung cấp công cụ chuẩn hóa.
"""

import json
import sys
from typing import Dict, Any, List

try:
    from tools import TOOLS_SCHEMA, dispatch_tool_call
except ModuleNotFoundError:
    from .tools import TOOLS_SCHEMA, dispatch_tool_call

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

class MCPChargingServer:
    """
    Giả lập MCP Server tuân thủ chuẩn giao thức Model Context Protocol
    """
    def __init__(self, server_name: str = "vinfast-charging-mcp-server"):
        self.server_name = server_name
        self.version = "2026.1.0"
        
    def list_tools(self) -> List[Dict[str, Any]]:
        """Trả về danh sách các Tools chuẩn giao thức MCP"""
        return TOOLS_SCHEMA
        
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Thực thi request gọi Tool theo chuẩn MCP JSON-RPC
        """
        raw_result = dispatch_tool_call(tool_name, arguments)

        try:
            content = json.loads(raw_result)
        except (TypeError, json.JSONDecodeError) as exc:
            content = {
                "status": "EXECUTION_ERROR",
                "error": f"Không thể phân tích kết quả Tool: {str(exc)}",
                "raw_result": raw_result
            }

        return {
            "jsonrpc": "2.0",
            "server": self.server_name,
            "tool": tool_name,
            "result": content
        }


# Giữ tương thích với src/app.py hiện tại trong khi các file khác được cập nhật.
MCPAcademicServer = MCPChargingServer


if __name__ == "__main__":
    print("==========================================================")
    print("🔌 KIỂM THỬ ĐỘC LẬP MCP SERVER (vinfast-charging-mcp-server)")
    print("==========================================================")

    server = MCPChargingServer()
    tools = server.list_tools()
    print(f"✅ Khởi tạo thành công MCP Server: {server.server_name} (Version: {server.version})")
    print(f"📦 Số lượng Tools công bố: {len(tools)}")

    # Kiểm tra schema của tool đặt trước cổng sạc.
    reserve_tool = next((t for t in tools if t.get("name") == "reserve_charging_slot"), None)
    if reserve_tool and reserve_tool.get("parameters", {}).get("properties"):
        print("✅ Tool 'reserve_charging_slot' đã có schema đầy đủ.")
    else:
        print("⏳ Tool 'reserve_charging_slot' chưa có schema đầy đủ.")

    # Kiểm tra gọi tool tra cứu trạm sạc qua MCP.
    test_result = server.call_tool(
        "charging_station_query",
        {"location": "Bình Thạnh", "connector_type": "DC Fast"}
    )
    if test_result.get("result", {}).get("status") != "SUCCESS":
        print("⏳ Kiểm tra gọi tool charging_station_query chưa thành công.")
    else:
        print("✅ Test dispatch tool 'charging_station_query' thành công:")
        print(f"   Phản hồi JSON-RPC: {json.dumps(test_result, ensure_ascii=False)}")
