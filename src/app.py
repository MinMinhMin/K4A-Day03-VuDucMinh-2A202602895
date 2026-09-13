"""
🚀 CORE AGENT APPLICATION (DAY 03: CHATBOT VS REACT AGENT)
Thực thi so sánh giữa Chatbot Baseline (Cấp 2) và ReAct Agent kết nối MCP Server (Cấp 3).
"""

import json
import os
import sys
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from mcp_server import MCPChargingServer
from prompts import MAX_ITERATIONS
from providers import get_llm_provider
from tools import reset_mock_database

load_dotenv()

CHATBOT_BASELINE_PROMPT = """
Bạn là Trợ lý Trạm sạc xe điện VinFast.
Bạn có thể trả lời các câu hỏi kiến thức chung về việc sử dụng trạm sạc.
Bạn không có quyền truy cập dữ liệu trạm sạc theo thời gian thực nếu không gọi Tool.
"""

CHARGING_REACT_AGENT_SYSTEM_PROMPT = """
Bạn là Trợ lý Tác tử Trạm sạc xe điện VinFast.
Bạn được trang bị hai công cụ:
1. charging_station_query: tra cứu trạm đang mở và cổng sạc còn trống.
2. reserve_charging_slot: đặt trước một cổng sạc cụ thể.

QUY TẮC REACT (Thought -> Action -> Observation):
1. Xác định dữ liệu cần thiết trước mỗi hành động.
2. Với câu hỏi kiến thức chung, trả lời trực tiếp không cần gọi Tool.
3. Với yêu cầu tra cứu trạm, gọi charging_station_query.
4. Với yêu cầu đặt chỗ, gọi reserve_charging_slot khi đã có đủ station_id,
   connector_id, datetime_str và vehicle_id.
5. Nếu người dùng yêu cầu tìm rồi đặt, trước tiên tra cứu trạm; sau khi nhận
   Observation, chọn cổng phù hợp và thực hiện đặt chỗ.
6. Không bịa đặt trạng thái trạm, cổng sạc hoặc mã đặt chỗ ngoài Observation.
"""

def load_test_cases():
    """Tải danh sách 5 test cases từ config/test_cases.json hoặc config/test_cases.example.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    if not os.path.exists(config_path):
        example_path = os.path.join(base_dir, "config", "test_cases.example.json")
        if os.path.exists(example_path):
            print("⚠️ [CONFIG NOTICE]: Chưa thấy file 'config/test_cases.json'. Đang dùng mẫu 'config/test_cases.example.json'.")
            print("👉 Hãy chạy: copy config/test_cases.example.json config/test_cases.json và viết test cases theo đề tài của bạn!\n")
            config_path = example_path
        else:
            config_path = "test_cases.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_waterfall_trace(trace_data: list):
    """Ghi vết log Waterfall Trace Log ra file docs/trace_waterfall.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    trace_path = os.path.join(docs_dir, "trace_waterfall.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)
    print(f"📊 [OBSERVABILITY]: Đã lưu {len(trace_data)} sự kiện Waterfall Trace tại '{trace_path}'!")


def format_charging_observation(tool_name: str, obs_data: dict) -> str:
    """Chuyển Observation của các tool trạm sạc thành câu trả lời dễ đọc."""
    if not isinstance(obs_data, dict):
        return "Tool trả về dữ liệu không hợp lệ."

    status = obs_data.get("status")

    if status == "SUCCESS" and tool_name == "charging_station_query":
        stations = obs_data.get("stations", [])
        if not stations:
            return "Đã tra cứu nhưng chưa tìm thấy trạm sạc phù hợp."

        station_lines = []
        for station in stations:
            connectors = station.get("available_connectors", [])
            connector_text = ", ".join(
                f"{connector.get('connector_id', '')} ({connector.get('type', '')})"
                for connector in connectors
            )
            station_lines.append(
                f"{station.get('name', station.get('station_id', ''))} "
                f"({station.get('location', '')}) - Cổng trống: {connector_text}"
            )

        return "Các trạm sạc phù hợp:\n- " + "\n- ".join(station_lines)

    if status == "SUCCESS" and tool_name == "reserve_charging_slot":
        return (
            f"Đặt trước cổng {obs_data.get('connector_id', '')} tại trạm "
            f"{obs_data.get('station_id', '')} thành công vào lúc "
            f"{obs_data.get('datetime', '')}. "
            f"Mã đặt chỗ: {obs_data.get('reservation_id', '')}."
        )

    if status in {"NOT_FOUND", "UNAVAILABLE"}:
        return obs_data.get("message", "Không tìm thấy tài nguyên phù hợp.")

    if status == "EXECUTION_ERROR":
        return f"Tool gặp lỗi khi thực thi: {obs_data.get('error', 'Lỗi không xác định.')}"

    return json.dumps(obs_data, ensure_ascii=False)


def request_requires_reservation(user_query: str) -> bool:
    """Kiểm tra yêu cầu có bao gồm hành động đặt trước cổng sạc không."""
    query_lower = user_query.lower()
    return any(
        phrase in query_lower
        for phrase in ["đặt trước", "đặt chỗ", "đặt cổng"]
    )


def run_baseline_chatbot(user_query: str, provider):
    """Chạy Chatbot gốc (Cấp 2) không có công cụ gọi Tool"""
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print(f"🤖 Chatbot phản hồi:\n{response}")


def run_react_agent(user_query: str, provider, mcp_server: MCPChargingServer) -> list:
    """
    [REACT AGENT LOOP] Thực thi vòng lặp Thought -> Action -> Observation với MCP Server
    Trả về danh sách trace log của phiên thực thi.
    """
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")
    
    step = 0
    trace_logs = []
    tools_list = mcp_server.list_tools()
    conversation_context = user_query
    final_answer = None
    
    while step < MAX_ITERATIONS:
        step += 1
        step_start_time = time.time()
        print(f"\n--- 🔄 Vòng lặp ReAct Loop (Step {step}/{MAX_ITERATIONS}) ---")
        
        # Gọi LLM với Native Tool Calling Specs
        llm_response = provider.generate_with_tools(
            conversation_context,
            tools_list,
            system_prompt=CHARGING_REACT_AGENT_SYSTEM_PROMPT
        )
        latency_ms = round((time.time() - step_start_time) * 1000, 2)
        
        thought = llm_response.get("thought", "Đang suy luận...")
        print(f"🧠 [Thought]: {thought}")
        
        # Trường hợp 1: LLM quyết định trả lời bằng văn bản trực tiếp
        if llm_response.get("type") == "text":
            final_answer = llm_response.get("content", "")
            print(f"🏁 [Final Answer]: {final_answer}")
            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "FINAL_ANSWER",
                "thought": thought,
                "output": final_answer,
                "latency_ms": latency_ms
            })
            break
            
        # Trường hợp 2: LLM đề xuất gọi Tool (Action)
        elif llm_response.get("type") == "tool_call":
            tool_name = llm_response.get("tool_name")
            arguments = llm_response.get("arguments", {})
            
            print(f"🛠️ [Action Proposed]: {tool_name}({arguments})")
            
            # Thực thi Tool qua MCP Server
            mcp_result = mcp_server.call_tool(tool_name, arguments)
            obs_data = mcp_result.get("result", {})

            obs_str = json.dumps(obs_data, ensure_ascii=False)
            print(f"👁️ [Observation từ MCP Server]: {obs_str}")
            
            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "TOOL_EXECUTION",
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": obs_data,
                "latency_ms": latency_ms
            })

            # Đưa Observation vào context để LLM có thể quyết định bước tiếp theo.
            observation_summary = format_charging_observation(tool_name, obs_data)

            # Không cần gọi thêm Gemini chỉ để diễn đạt lại kết quả Tool.
            # Với yêu cầu đa bước, chỉ tiếp tục khi bước tra cứu thành công.
            if tool_name == "reserve_charging_slot" or (
                tool_name == "charging_station_query"
                and (
                    not request_requires_reservation(user_query)
                    or obs_data.get("status") != "SUCCESS"
                )
            ):
                final_answer = observation_summary
                print(f"🏁 [Final Answer]: {final_answer}")
                trace_logs.append({
                    "step": step + 1,
                    "query": user_query,
                    "action_type": "FINAL_ANSWER",
                    "thought": "Đã có đủ kết quả từ Tool để trả lời người dùng.",
                    "output": final_answer,
                    "latency_ms": 0.0
                })
                break

            conversation_context = (
                f"Yêu cầu ban đầu của người dùng:\n{user_query}\n\n"
                f"Tool vừa gọi: {tool_name}\n"
                f"Observation: {obs_str}\n\n"
                f"Tóm tắt Observation: {observation_summary}\n"
                "Hãy quyết định bước tiếp theo hoặc trả lời người dùng nếu đã hoàn tất."
            )
            continue

        final_answer = "Agent không trả về phản hồi hợp lệ."
        print(f"⚠️ [Agent Error]: {final_answer}")
        break

    if final_answer is None:
        final_answer = "Agent chưa hoàn tất xử lý trong số vòng lặp cho phép."
        print(f"⚠️ [Agent Timeout]: {final_answer}")
        trace_logs.append({
            "step": step + 1,
            "query": user_query,
            "action_type": "FINAL_ANSWER",
            "thought": "Đã đạt giới hạn số vòng lặp.",
            "output": final_answer,
            "latency_ms": 0.0
        })

    return trace_logs


if __name__ == "__main__":
    print("==========================================================")
    print("🏫 VINUNI AI COURSE - DAY 03 LAB: CHATBOT VS REACT AGENT")
    print("==========================================================")
    
    provider = get_llm_provider()
    mcp_server = MCPChargingServer()
    
    print(f"🔌 LLM Provider: {provider.__class__.__name__}")
    print(f"🌐 MCP Server: {mcp_server.server_name}\n")
    
    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases thử nghiệm.\n")
    
    if "--interactive" in sys.argv:
        print("🎮 [INTERACTIVE MODE] Trò chuyện trực tiếp với ReAct Agent:")
        print("💡 Gợi ý câu hỏi thử nghiệm:")
        print("   - Câu hỏi chung: 'Tôi cần lưu ý gì khi sạc xe điện tại trạm công cộng?'")
        print("   - Tra cứu trạm: 'Tìm trạm sạc DC Fast còn trống tại Bình Thạnh'")
        print("   - Đặt chỗ: 'Đặt cổng C01 tại ST001 lúc 14:00 ngày 15/09/2026 cho xe VF8-12345'")
        print("   - Gõ 'exit' hoặc 'quit' để kết thúc phiên trò chuyện.\n")
        while True:
            try:
                user_input = input("👤 Sinh viên hỏi: ").strip()
                if not user_input or user_input.lower() in ["exit", "quit"]:
                    print("👋 Tạm biệt! Kết thúc phiên trò chuyện.")
                    break
                logs = run_react_agent(user_input, provider, mcp_server)
                save_waterfall_trace(logs)
            except (KeyboardInterrupt, EOFError):
                print("\n👋 Đã thoát phiên tương tác.")
                break
    elif "--all" in sys.argv:
        print("🚀 [TEST SUITE MODE] Kiểm tra 5 Test Cases:")
        completed_count = 0
        todo_count = 0
        all_traces = []
        
        for tc in tests:
            print(f"\n==================================================")
            print(f"🧪 [{tc['id']}] Loại test: {tc['type']} (Độ phức tạp: {tc['complexity']})")
            print(f"📌 Kỳ vọng: {tc['expected_behavior']}")
            
            if tc["question"].strip().startswith("TODO"):
                print(f"⏸️ [CHƯA KÍCH HOẠT - ĐANG LÀ TODO]:")
                print(f"   {tc['question']}")
                print(f"   👉 Hãy mở file 'config/test_cases.json' để viết câu hỏi thực tế cho Test Case này!")
                todo_count += 1
            else:
                reset_mock_database()
                logs = run_react_agent(tc["question"], provider, mcp_server)
                all_traces.extend(logs)
                completed_count += 1
                
        print(f"\n==================================================")
        print(f"📊 [KẾT QUẢ TEST SUITE]: Đã thực thi {completed_count}/{len(tests)} Test Cases | {todo_count} Test Cases đang chờ điền câu hỏi (TODO)")
        if all_traces:
            save_waterfall_trace(all_traces)
        print(f"💡 Để trò chuyện trực tiếp từng câu: Chạy 'python src/app.py --interactive'")
    else:
        # Chế độ mặc định khi chỉ gõ 'python src/app.py'
        print("ℹ️ HƯỚNG DẪN SỬ DỤNG CHƯƠNG TRÌNH:")
        print("  1. Chat trực tiếp liên tục:   python src/app.py --interactive")
        print("  2. Chạy toàn bộ Test Cases:    python src/app.py --all\n")
        
        sample_query = tests[1]["question"]
        print(f"--- 🏁 DEMO CHẠY THỬ 1 TEST CASE MẪU (TC02: Tra cứu trạm sạc) ---")
        logs = run_react_agent(sample_query, provider, mcp_server)
        save_waterfall_trace(logs)
        print("\n💡 Hãy thử ngay lệnh: python src/app.py --interactive để chat trực tiếp!")
