"""
🔌 MULTI-PROVIDER LLM ADAPTER (Google Gemini, OpenAI & Offline Mock)
Hỗ trợ Native Tool Calling và chuyển đổi linh hoạt qua biến môi trường LLM_PROVIDER.
"""

import os
import re
import sys
import json
import time
from typing import Dict, Any, List
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

class BaseLLMProvider:
    """Interface cơ sở cho các LLM Provider hỗ trợ Native Tool Calling"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        raise NotImplementedError


class MockOfflineProvider(BaseLLMProvider):
    """Offline Mock Provider dùng để chạy thử mà không tốn API Key"""
    def __init__(self):
        self.model_name = "Offline-Mock-Model-2026"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return (
            f"[Mock Chatbot Response]: Xin chào! Tôi đã nhận được câu hỏi '{prompt}'. "
            "Bạn có thể yêu cầu tôi tra cứu trạm sạc hoặc đặt trước một cổng sạc."
        )

    @staticmethod
    def _extract_location(prompt: str) -> str:
        """Trích xuất khu vực sau các từ khóa 'tại' hoặc 'ở'."""
        match = re.search(r"(?:tại|ở)\s+([^,.!?\n]+)", prompt, flags=re.IGNORECASE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_datetime(prompt: str) -> str:
        """Chuẩn hóa thời gian tiếng Việt về dạng HH:MM DD/MM/YYYY."""
        match = re.search(
            r"(\d{1,2}:\d{2})\s*(?:ngày\s*)?(\d{1,2}/\d{1,2}/\d{4})",
            prompt,
            flags=re.IGNORECASE
        )
        return f"{match.group(1)} {match.group(2)}" if match else ""

    @staticmethod
    def _extract_token(prompt: str, pattern: str) -> str:
        match = re.search(pattern, prompt, flags=re.IGNORECASE)
        return match.group(0).upper() if match else ""

    @staticmethod
    def _extract_observation_value(prompt: str, key: str) -> str:
        match = re.search(
            rf"[\"']{re.escape(key)}[\"']\s*:\s*[\"']([^\"']+)",
            prompt,
            flags=re.IGNORECASE
        )
        return match.group(1) if match else ""

    def _charging_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        thought: str,
        tools_schema: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        available_tools = {tool.get("name") for tool in tools_schema}
        if tool_name not in available_tools:
            return {
                "type": "text",
                "content": f"Không tìm thấy Tool '{tool_name}' trong MCP Server.",
                "thought": "Không có Tool phù hợp để thực hiện yêu cầu."
            }

        return {
            "type": "tool_call",
            "tool_name": tool_name,
            "arguments": arguments,
            "thought": thought
        }

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        prompt_lower = prompt.lower()

        query_tool = "charging_station_query"
        reserve_tool = "reserve_charging_slot"
        reservation_intent = any(
            phrase in prompt_lower
            for phrase in ["đặt trước", "đặt chỗ", "đặt cổng"]
        )
        query_intent = any(
            phrase in prompt_lower
            for phrase in ["tìm", "tra cứu", "còn cổng"]
        )

        # Khi app.py đã đưa Observation của bước đặt chỗ vào context,
        # Mock Provider kết thúc phiên bằng câu trả lời văn bản.
        if "tool vừa gọi: reserve_charging_slot" in prompt_lower or "reservation_id" in prompt_lower:
            return {
                "type": "text",
                "content": "Đã hoàn tất yêu cầu đặt trước cổng sạc.",
                "thought": "Đã nhận được kết quả đặt chỗ và có thể trả lời người dùng."
            }

        # Với yêu cầu tìm rồi đặt, sau Observation tra cứu sẽ gọi Tool đặt chỗ.
        if "tool vừa gọi: charging_station_query" in prompt_lower:
            station_id = self._extract_observation_value(prompt, "station_id")
            connector_id = self._extract_observation_value(prompt, "connector_id")
            vehicle_id = self._extract_token(prompt, r"\bVF[\w-]+\b")

            if reservation_intent and station_id and connector_id:
                return self._charging_tool_call(
                    reserve_tool,
                    {
                        "station_id": station_id,
                        "connector_id": connector_id,
                        "datetime_str": self._extract_datetime(prompt),
                        "vehicle_id": vehicle_id
                    },
                    "Đã nhận Observation của trạm sạc và sẽ đặt cổng phù hợp.",
                    tools_schema
                )

            return {
                "type": "text",
                "content": "Đã hoàn tất tra cứu trạm sạc.",
                "thought": "Observation đã đủ để trả lời kết quả tra cứu."
            }

        station_id = self._extract_token(prompt, r"\bST\d+\b")
        connector_id = self._extract_token(prompt, r"\bC\d+\b")
        vehicle_id = self._extract_token(prompt, r"\bVF[\w-]+\b")
        connector_match = re.search(r"\b(DC\s+Fast|AC)\b", prompt, flags=re.IGNORECASE)
        connector_type = connector_match.group(1) if connector_match else ""

        if reservation_intent and station_id and connector_id:
            return self._charging_tool_call(
                reserve_tool,
                {
                    "station_id": station_id,
                    "connector_id": connector_id,
                    "datetime_str": self._extract_datetime(prompt),
                    "vehicle_id": vehicle_id
                },
                "Người dùng yêu cầu đặt trước một cổng sạc cụ thể.",
                tools_schema
            )

        if query_intent:
            return self._charging_tool_call(
                query_tool,
                {
                    "location": self._extract_location(prompt),
                    "datetime_str": self._extract_datetime(prompt),
                    "connector_type": connector_type
                },
                "Người dùng yêu cầu tra cứu trạm sạc và cổng còn trống.",
                tools_schema
            )

        return {
            "type": "text",
            "content": (
                "Bạn có thể hỏi về vị trí trạm sạc, tình trạng cổng sạc "
                "hoặc yêu cầu đặt trước một cổng cụ thể."
            ),
            "thought": "Câu hỏi không yêu cầu dữ liệu trạm sạc thời gian thực."
        }


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider (Native Tool Calling với Google GenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-3.6-flash"
        self.min_request_interval = float(
            os.getenv("GEMINI_MIN_REQUEST_INTERVAL_SECONDS", "13")
        )
        self._last_request_at = 0.0

    def _wait_for_rate_limit(self) -> None:
        """Giãn cách request để không vượt quota Free Tier theo phút."""
        if self.min_request_interval <= 0:
            self._last_request_at = time.monotonic()
            return

        elapsed = time.monotonic() - self._last_request_at
        remaining = self.min_request_interval - elapsed
        if remaining > 0:
            print(
                f"ℹ️ [Gemini Rate Limit]: Chờ {remaining:.1f}s trước request tiếp theo."
            )
            time.sleep(remaining)
        self._last_request_at = time.monotonic()
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from google import genai
            self._wait_for_rate_limit()
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(model=self.model_name, contents=contents)
            return response.text
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            print("ℹ️ [Gemini Provider]: Chưa tìm thấy GEMINI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)
        
        try:
            from google import genai
            from google.genai import types

            self._wait_for_rate_limit()
            client = genai.Client(api_key=self.api_key)
            
            # Chuẩn hóa function declarations cho Gemini SDK
            function_declarations = []
            for tool in tools_schema:
                # Bỏ qua các tool schema chưa được định nghĩa hoàn chỉnh
                if not tool.get("name") or not tool.get("parameters"):
                    continue
                function_declarations.append({
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                })

            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                tools=[{"function_declarations": function_declarations}] if function_declarations else None,
                temperature=0.2
            )

            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )

            # Kiểm tra xem Gemini có trả về Tool Call không
            if response.function_calls:
                call = response.function_calls[0]
                args = dict(call.args) if hasattr(call, 'args') and call.args else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.name,
                    "arguments": args,
                    "thought": f"Gemini quyết định gọi công cụ '{call.name}' với tham số: {json.dumps(args, ensure_ascii=False)}"
                }
            else:
                return {
                    "type": "text",
                    "content": response.text or "",
                    "thought": "Gemini phản hồi trực tiếp bằng văn bản (không cần gọi công cụ)."
                }

        except Exception as e:
            print(f"⚠️ [Gemini API Warning]: Không thể kết nối live API ({str(e)}). Tự động fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (Native Tool Calling với OpenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(model=self.model_name, messages=messages)
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[OpenAI Exception]: {str(e)}"

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            print("ℹ️ [OpenAI Provider]: Chưa tìm thấy OPENAI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)

            tools = []
            for tool in tools_schema:
                if not tool.get("name"):
                    continue
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {})
                    }
                })

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None
            )

            msg = response.choices[0].message
            if msg.tool_calls:
                call = msg.tool_calls[0]
                args = json.loads(call.function.arguments) if call.function.arguments else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.function.name,
                    "arguments": args,
                    "thought": f"OpenAI quyết định gọi công cụ '{call.function.name}' với tham số: {json.dumps(args, ensure_ascii=False)}"
                }
            else:
                return {
                    "type": "text",
                    "content": msg.content or "",
                    "thought": "OpenAI phản hồi trực tiếp bằng văn bản (không cần gọi công cụ)."
                }
        except Exception as e:
            print(f"⚠️ [OpenAI API Warning]: Không thể kết nối live API ({str(e)}). Tự động fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)


def get_llm_provider() -> BaseLLMProvider:
    """Factory function khởi tạo Provider theo LLM_PROVIDER env variable"""
    provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    if provider_type == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if key and key != "your_gemini_api_key_here":
            return GeminiProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if key and key != "your_openai_api_key_here":
            return OpenAIProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "mock":
        return MockOfflineProvider()
    else:
        return MockOfflineProvider()
