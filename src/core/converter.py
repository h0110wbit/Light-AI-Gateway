"""
Format Converter for AI Gateway
Provides bidirectional conversion between OpenAI, Anthropic, and Gemini formats
for both request bodies and response bodies.
"""
from __future__ import annotations

from typing import Optional, Dict, Any, Tuple
from enum import Enum


class ProviderType(Enum):
    """Supported AI provider types"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class FormatConverter:
    """
    Unified format converter for AI provider APIs.
    Supports bidirectional conversion between OpenAI, Anthropic, and Gemini formats.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Request Transformations
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def transform_request(
        body: Dict[str, Any],
        source: ProviderType,
        target: ProviderType,
    ) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
        """
        Transform request body from source format to target format.
        
        Args:
            body: Original request body
            source: Source provider format
            target: Target provider format
            
        Returns:
            Tuple of (transformed_body, model_name, extra_info)
        """
        if source == target:
            model = body.get("model", "")
            return body, model, {}

        transform_key = f"{source.value}_to_{target.value}"
        transform_map = {
            "openai_to_anthropic":
            FormatConverter._request_openai_to_anthropic,
            "openai_to_gemini": FormatConverter._request_openai_to_gemini,
            "anthropic_to_openai":
            FormatConverter._request_anthropic_to_openai,
            "anthropic_to_gemini":
            FormatConverter._request_anthropic_to_gemini,
            "gemini_to_openai": FormatConverter._request_gemini_to_openai,
            "gemini_to_anthropic":
            FormatConverter._request_gemini_to_anthropic,
        }

        if transform_key not in transform_map:
            raise ValueError(f"Unsupported transformation: {transform_key}")

        return transform_map[transform_key](body)

    # ─── OpenAI → Anthropic ───────────────────────────────────────────────────

    @staticmethod
    def _request_openai_to_anthropic(
            body: Dict[str,
                       Any]) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
        """
        Transform OpenAI chat request to Anthropic messages format.
        
        Args:
            body: OpenAI request body
            
        Returns:
            Tuple of (anthropic_body, model_name, extra_info)
        """
        messages = body.get("messages", [])
        system_prompt = None
        anthropic_messages = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = content
            elif role in ("user", "assistant"):
                anthropic_messages.append({
                    "role":
                    role,
                    "content":
                    content if isinstance(content, str) else content
                })

        result = {
            "model": body.get("model", "claude-3-5-sonnet-20241022"),
            "messages": anthropic_messages,
            "max_tokens": body.get("max_tokens", 4096),
        }

        if system_prompt:
            result["system"] = system_prompt

        if "temperature" in body:
            result["temperature"] = body["temperature"]
        if "top_p" in body:
            result["top_p"] = body["top_p"]
        if "stream" in body:
            result["stream"] = body["stream"]
        if "stop" in body:
            stop = body["stop"]
            if isinstance(stop, list):
                result["stop_sequences"] = stop
            else:
                result["stop_sequences"] = [stop]

        return result, result["model"], {}

    # ─── OpenAI → Gemini ──────────────────────────────────────────────────────

    @staticmethod
    def _request_openai_to_gemini(
            body: Dict[str,
                       Any]) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
        """
        Transform OpenAI chat request to Gemini format.
        
        Args:
            body: OpenAI request body
            
        Returns:
            Tuple of (gemini_body, model_name, extra_info)
        """
        messages = body.get("messages", [])
        model = body.get("model", "gemini-pro")

        system_instruction = None
        gemini_contents = []

        def extract_text_from_content(content) -> str:
            """Extract text from content which can be string or list of parts."""
            if content is None:
                return ""
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                return " ".join(text_parts)
            return str(content)

        # Handle top-level system field (Anthropic-style)
        if "system" in body:
            system_instruction = extract_text_from_content(body["system"])

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                system_instruction = extract_text_from_content(content)
            elif role == "user":
                text_content = extract_text_from_content(content)
                gemini_contents.append({
                    "role": "user",
                    "parts": [{
                        "text": text_content
                    }]
                })
            elif role == "assistant":
                text_content = extract_text_from_content(content)
                gemini_contents.append({
                    "role": "model",
                    "parts": [{
                        "text": text_content
                    }]
                })

        result = {"contents": gemini_contents, "generationConfig": {}}

        if system_instruction:
            result["systemInstruction"] = {
                "parts": [{
                    "text": system_instruction
                }]
            }

        if "temperature" in body:
            result["generationConfig"]["temperature"] = body["temperature"]
        if "top_p" in body:
            result["generationConfig"]["topP"] = body["top_p"]
        if "max_tokens" in body:
            result["generationConfig"]["maxOutputTokens"] = body["max_tokens"]
        if "stop" in body:
            stop = body["stop"]
            if isinstance(stop, list):
                result["generationConfig"]["stopSequences"] = stop
            elif isinstance(stop, str):
                result["generationConfig"]["stopSequences"] = [stop]

        is_stream = body.get("stream", False)
        return result, model, {"is_stream": is_stream}

    # ─── Anthropic → OpenAI ───────────────────────────────────────────────────

    @staticmethod
    def _request_anthropic_to_openai(
            body: Dict[str,
                       Any]) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
        """
        Transform Anthropic messages request to OpenAI chat format.
        
        Args:
            body: Anthropic request body
            
        Returns:
            Tuple of (openai_body, model_name, extra_info)
        """
        messages = body.get("messages", [])
        system_prompt = body.get("system")
        openai_messages = []

        if system_prompt:
            openai_messages.append({
                "role":
                "system",
                "content":
                system_prompt
                if isinstance(system_prompt, str) else system_prompt
            })

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content")

            if role in ("user", "assistant"):
                openai_content = FormatConverter._convert_anthropic_content_to_openai(
                    content)
                openai_messages.append({
                    "role": role,
                    "content": openai_content
                })

        result = {
            "model": body.get("model", "gpt-4"),
            "messages": openai_messages,
        }

        if "max_tokens" in body:
            result["max_tokens"] = body["max_tokens"]
        if "temperature" in body:
            result["temperature"] = body["temperature"]
        if "top_p" in body:
            result["top_p"] = body["top_p"]
        if "stream" in body:
            result["stream"] = body["stream"]
        if "stop_sequences" in body:
            stop = body["stop_sequences"]
            if len(stop) == 1:
                result["stop"] = stop[0]
            else:
                result["stop"] = stop

        return result, result["model"], {}

    @staticmethod
    def _convert_anthropic_content_to_openai(content: Any) -> Any:
        """
        Convert Anthropic content format to OpenAI content format.
        
        Anthropic content can be:
        - A string: "Hello"
        - A list of content blocks: [{"type": "text", "text": "Hello"}]
        - A list with mixed types: [{"type": "text", "text": "Hello"}, {"type": "image", ...}]
        
        OpenAI content can be:
        - A string: "Hello"
        - A list of content parts: [{"type": "text", "text": "Hello"}, {"type": "image_url", "image_url": {...}}]
        """
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            openai_parts = []
            text_parts = []

            for block in content:
                if not isinstance(block, dict):
                    continue

                block_type = block.get("type", "")

                if block_type == "text":
                    text = block.get("text", "")
                    text_parts.append(text)
                    openai_parts.append({"type": "text", "text": text})

                elif block_type == "image":
                    source = block.get("source", {})
                    media_type = source.get("media_type", "")
                    data = source.get("data", "")

                    if media_type and data:
                        image_url = f"data:{media_type};base64,{data}"
                        openai_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        })

                elif block_type == "tool_use":
                    openai_parts.append({
                        "type":
                        "text",
                        "text":
                        f"[Tool use: {block.get('name', 'unknown')}]"
                    })

                elif block_type == "tool_result":
                    tool_content = block.get("content", "")
                    if isinstance(tool_content, list):
                        tool_text = " ".join(
                            p.get("text", "") for p in tool_content
                            if isinstance(p, dict) and p.get("type") == "text")
                    else:
                        tool_text = str(tool_content)
                    openai_parts.append({"type": "text", "text": tool_text})

            if len(openai_parts) == 1 and openai_parts[0].get(
                    "type") == "text":
                return openai_parts[0].get("text", "")

            if len(openai_parts) == 0:
                return " ".join(text_parts) if text_parts else ""

            return openai_parts

        return str(content)

    # ─── Anthropic → Gemini ───────────────────────────────────────────────────

    @staticmethod
    def _request_anthropic_to_gemini(
            body: Dict[str,
                       Any]) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
        """
        Transform Anthropic messages request to Gemini format.
        
        Args:
            body: Anthropic request body
            
        Returns:
            Tuple of (gemini_body, model_name, extra_info)
        """
        messages = body.get("messages", [])
        system_prompt = body.get("system")
        model = body.get("model", "gemini-pro")

        gemini_contents = []

        def extract_text_from_content(content) -> str:
            """Extract text from content which can be string or list of parts."""
            if content is None:
                return ""
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                return " ".join(text_parts)
            return str(content)

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                text_content = extract_text_from_content(content)
                gemini_contents.append({
                    "role": "user",
                    "parts": [{
                        "text": text_content
                    }]
                })
            elif role == "assistant":
                text_content = extract_text_from_content(content)
                gemini_contents.append({
                    "role": "model",
                    "parts": [{
                        "text": text_content
                    }]
                })

        result = {"contents": gemini_contents, "generationConfig": {}}

        if system_prompt:
            system_text = extract_text_from_content(system_prompt)
            result["systemInstruction"] = {"parts": [{"text": system_text}]}

        if "max_tokens" in body:
            result["generationConfig"]["maxOutputTokens"] = body["max_tokens"]
        if "temperature" in body:
            result["generationConfig"]["temperature"] = body["temperature"]
        if "top_p" in body:
            result["generationConfig"]["topP"] = body["top_p"]
        if "stop_sequences" in body:
            result["generationConfig"]["stopSequences"] = body[
                "stop_sequences"]

        is_stream = body.get("stream", False)
        return result, model, {"is_stream": is_stream}

    # ─── Gemini → OpenAI ──────────────────────────────────────────────────────

    @staticmethod
    def _request_gemini_to_openai(
            body: Dict[str,
                       Any]) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
        """
        Transform Gemini request to OpenAI chat format.
        
        Args:
            body: Gemini request body
            
        Returns:
            Tuple of (openai_body, model_name, extra_info)
        """
        contents = body.get("contents", [])
        system_instruction = body.get("system_instruction") or body.get(
            "systemInstruction", {})
        generation_config = body.get("generationConfig", {})

        openai_messages = []

        system_parts = system_instruction.get("parts", [])
        if system_parts:
            system_text = " ".join(
                p.get("text", "") for p in system_parts if "text" in p)
            if system_text:
                openai_messages.append({
                    "role": "system",
                    "content": system_text
                })

        for content in contents:
            role = content.get("role", "")
            parts = content.get("parts", [])
            text = " ".join(p.get("text", "") for p in parts if "text" in p)

            if role == "user":
                openai_messages.append({"role": "user", "content": text})
            elif role == "model":
                openai_messages.append({"role": "assistant", "content": text})

        model = body.get("model", "gpt-4")
        result = {"model": model, "messages": openai_messages}

        if "maxOutputTokens" in generation_config:
            result["max_tokens"] = generation_config["maxOutputTokens"]
        if "temperature" in generation_config:
            result["temperature"] = generation_config["temperature"]
        if "topP" in generation_config:
            result["top_p"] = generation_config["topP"]
        if "stopSequences" in generation_config:
            stop = generation_config["stopSequences"]
            if len(stop) == 1:
                result["stop"] = stop[0]
            else:
                result["stop"] = stop

        return result, model, {}

    # ─── Gemini → Anthropic ───────────────────────────────────────────────────

    @staticmethod
    def _request_gemini_to_anthropic(
            body: Dict[str,
                       Any]) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
        """
        Transform Gemini request to Anthropic messages format.
        
        Args:
            body: Gemini request body
            
        Returns:
            Tuple of (anthropic_body, model_name, extra_info)
        """
        contents = body.get("contents", [])
        system_instruction = body.get("system_instruction") or body.get(
            "systemInstruction", {})
        generation_config = body.get("generationConfig", {})

        anthropic_messages = []

        system_parts = system_instruction.get("parts", [])
        system_text = " ".join(
            p.get("text", "") for p in system_parts if "text" in p)

        for content in contents:
            role = content.get("role", "")
            parts = content.get("parts", [])
            text = " ".join(p.get("text", "") for p in parts if "text" in p)

            if role == "user":
                anthropic_messages.append({"role": "user", "content": text})
            elif role == "model":
                anthropic_messages.append({
                    "role": "assistant",
                    "content": text
                })

        model = body.get("model", "claude-3-5-sonnet-20241022")
        result = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": 4096
        }

        if system_text:
            result["system"] = system_text

        if "maxOutputTokens" in generation_config:
            result["max_tokens"] = generation_config["maxOutputTokens"]
        if "temperature" in generation_config:
            result["temperature"] = generation_config["temperature"]
        if "topP" in generation_config:
            result["top_p"] = generation_config["topP"]
        if "stopSequences" in generation_config:
            result["stop_sequences"] = generation_config["stopSequences"]

        return result, model, {}

    # ─────────────────────────────────────────────────────────────────────────
    # Response Transformations
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def transform_response(
        data: Dict[str, Any],
        source: ProviderType,
        target: ProviderType,
        model: str = "",
    ) -> Dict[str, Any]:
        """
        Transform response body from source format to target format.
        
        Args:
            data: Original response body
            source: Source provider format
            target: Target provider format
            model: Model name (required for some transformations)
            
        Returns:
            Transformed response dict
        """
        if source == target:
            return data

        transform_key = f"{source.value}_to_{target.value}"
        transform_map = {
            "openai_to_anthropic":
            FormatConverter._response_openai_to_anthropic,
            "openai_to_gemini": FormatConverter._response_openai_to_gemini,
            "anthropic_to_openai":
            FormatConverter._response_anthropic_to_openai,
            "anthropic_to_gemini":
            FormatConverter._response_anthropic_to_gemini,
            "gemini_to_openai": FormatConverter._response_gemini_to_openai,
            "gemini_to_anthropic":
            FormatConverter._response_gemini_to_anthropic,
        }

        if transform_key not in transform_map:
            raise ValueError(f"Unsupported transformation: {transform_key}")

        return transform_map[transform_key](data, model)

    # ─── Anthropic → OpenAI ───────────────────────────────────────────────────

    @staticmethod
    def _response_anthropic_to_openai(data: Dict[str, Any],
                                      model: str = "") -> Dict[str, Any]:
        """
        Transform Anthropic response to OpenAI format.
        
        Args:
            data: Anthropic response body
            model: Model name (unused, kept for interface consistency)
            
        Returns:
            OpenAI-compatible response dict
        """
        if data.get("type") == "error":
            return data

        content_blocks = data.get("content", [])
        text_content = ""

        for block in content_blocks:
            if block.get("type") == "text":
                text_content += block.get("text", "")

        usage = data.get("usage", {})

        return {
            "id":
            data.get("id", ""),
            "object":
            "chat.completion",
            "created":
            0,
            "model":
            data.get("model", ""),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text_content,
                },
                "finish_reason": data.get("stop_reason", "stop"),
            }],
            "usage": {
                "prompt_tokens":
                usage.get("input_tokens", 0),
                "completion_tokens":
                usage.get("output_tokens", 0),
                "total_tokens":
                usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            }
        }

    # ─── Gemini → OpenAI ──────────────────────────────────────────────────────

    @staticmethod
    def _response_gemini_to_openai(data: Dict[str, Any],
                                   model: str = "") -> Dict[str, Any]:
        """
        Transform Gemini response to OpenAI format.
        
        Args:
            data: Gemini response body
            model: Model name used in the request
            
        Returns:
            OpenAI-compatible response dict
        """
        if "error" in data:
            return {"error": data["error"]}

        candidates = data.get("candidates", [])
        text_content = ""
        finish_reason = "stop"

        if candidates:
            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            for part in parts:
                if "text" in part:
                    text_content += part["text"]

            finish_reason_map = {
                "STOP": "stop",
                "MAX_TOKENS": "length",
                "SAFETY": "content_filter",
                "RECITATION": "content_filter",
                "OTHER": "stop",
            }
            finish_reason = finish_reason_map.get(
                candidate.get("finishReason", "STOP"), "stop")

        usage_metadata = data.get("usageMetadata", {})

        return {
            "id":
            data.get("responseId", f"gemini-{model}"),
            "object":
            "chat.completion",
            "created":
            0,
            "model":
            model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text_content,
                },
                "finish_reason": finish_reason,
            }],
            "usage": {
                "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
                "completion_tokens":
                usage_metadata.get("candidatesTokenCount", 0),
                "total_tokens": usage_metadata.get("totalTokenCount", 0),
            }
        }

    # ─── OpenAI → Anthropic ───────────────────────────────────────────────────

    @staticmethod
    def _response_openai_to_anthropic(data: Dict[str, Any],
                                      model: str = "") -> Dict[str, Any]:
        """
        Transform OpenAI response to Anthropic format.
        
        Args:
            data: OpenAI response body
            model: Model name (unused, kept for interface consistency)
            
        Returns:
            Anthropic-compatible response dict
        """
        if data.get("error"):
            return {"type": "error", "error": data.get("error")}

        choices = data.get("choices", [])
        text_content = ""
        finish_reason = "end_turn"

        if choices:
            choice = choices[0]
            message = choice.get("message", {})
            text_content = message.get("content", "")

            openai_finish_map = {
                "stop": "end_turn",
                "length": "max_tokens",
                "content_filter": "stop_sequence",
            }
            finish_reason = openai_finish_map.get(
                choice.get("finish_reason", "stop"), "end_turn")

        usage = data.get("usage", {})

        return {
            "id": data.get("id", ""),
            "type": "message",
            "role": "assistant",
            "model": data.get("model", ""),
            "content": [{
                "type": "text",
                "text": text_content,
            }],
            "stop_reason": finish_reason,
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            }
        }

    # ─── OpenAI → Gemini ──────────────────────────────────────────────────────

    @staticmethod
    def _response_openai_to_gemini(data: Dict[str, Any],
                                   model: str = "") -> Dict[str, Any]:
        """
        Transform OpenAI response to Gemini format.
        
        Args:
            data: OpenAI response body
            model: Model name used in the request
            
        Returns:
            Gemini-compatible response dict
        """
        if data.get("error"):
            return {"error": data["error"]}

        choices = data.get("choices", [])
        text_content = ""
        finish_reason = "STOP"

        if choices:
            choice = choices[0]
            message = choice.get("message", {})
            text_content = message.get("content", "")

            openai_finish_map = {
                "stop": "STOP",
                "length": "MAX_TOKENS",
                "content_filter": "SAFETY",
            }
            finish_reason = openai_finish_map.get(
                choice.get("finish_reason", "stop"), "STOP")

        usage = data.get("usage", {})

        return {
            "candidates": [{
                "content": {
                    "role": "model",
                    "parts": [{
                        "text": text_content
                    }]
                },
                "finishReason": finish_reason,
            }],
            "usageMetadata": {
                "promptTokenCount": usage.get("prompt_tokens", 0),
                "candidatesTokenCount": usage.get("completion_tokens", 0),
                "totalTokenCount": usage.get("total_tokens", 0),
            }
        }

    # ─── Anthropic → Gemini ───────────────────────────────────────────────────

    @staticmethod
    def _response_anthropic_to_gemini(data: Dict[str, Any],
                                      model: str = "") -> Dict[str, Any]:
        """
        Transform Anthropic response to Gemini format.
        
        Args:
            data: Anthropic response body
            model: Model name used in the request
            
        Returns:
            Gemini-compatible response dict
        """
        if data.get("type") == "error":
            return {"error": data.get("error", {})}

        content_blocks = data.get("content", [])
        text_content = ""

        for block in content_blocks:
            if block.get("type") == "text":
                text_content += block.get("text", "")

        usage = data.get("usage", {})

        finish_reason_map = {
            "end_turn": "STOP",
            "max_tokens": "MAX_TOKENS",
            "stop_sequence": "STOP",
        }
        finish_reason = finish_reason_map.get(
            data.get("stop_reason", "end_turn"), "STOP")

        return {
            "candidates": [{
                "content": {
                    "role": "model",
                    "parts": [{
                        "text": text_content
                    }]
                },
                "finishReason": finish_reason,
            }],
            "usageMetadata": {
                "promptTokenCount":
                usage.get("input_tokens", 0),
                "candidatesTokenCount":
                usage.get("output_tokens", 0),
                "totalTokenCount":
                usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            }
        }

    # ─── Gemini → Anthropic ───────────────────────────────────────────────────

    @staticmethod
    def _response_gemini_to_anthropic(data: Dict[str, Any],
                                      model: str = "") -> Dict[str, Any]:
        """
        Transform Gemini response to Anthropic format.
        
        Args:
            data: Gemini response body
            model: Model name used in the request
            
        Returns:
            Anthropic-compatible response dict
        """
        if "error" in data:
            return {"type": "error", "error": data["error"]}

        candidates = data.get("candidates", [])
        text_content = ""
        finish_reason = "end_turn"

        if candidates:
            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            for part in parts:
                if "text" in part:
                    text_content += part["text"]

            finish_reason_map = {
                "STOP": "end_turn",
                "MAX_TOKENS": "max_tokens",
                "SAFETY": "stop_sequence",
                "RECITATION": "stop_sequence",
                "OTHER": "end_turn",
            }
            finish_reason = finish_reason_map.get(
                candidate.get("finishReason", "STOP"), "end_turn")

        usage_metadata = data.get("usageMetadata", {})

        return {
            "id": data.get("responseId", ""),
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [{
                "type": "text",
                "text": text_content,
            }],
            "stop_reason": finish_reason,
            "usage": {
                "input_tokens": usage_metadata.get("promptTokenCount", 0),
                "output_tokens": usage_metadata.get("candidatesTokenCount", 0),
            }
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Stream Chunk Transformations
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def transform_stream_chunk(
        data: Dict[str, Any],
        source: ProviderType,
        target: ProviderType,
        model: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Transform a single stream chunk from source format to target format.
        
        Args:
            data: Stream chunk data
            source: Source provider format
            target: Target provider format
            model: Model name
            
        Returns:
            Transformed chunk dict or None if chunk should be skipped
        """
        if source == target:
            return data

        transform_key = f"{source.value}_to_{target.value}"
        transform_map = {
            "anthropic_to_openai": FormatConverter._stream_anthropic_to_openai,
            "gemini_to_openai": FormatConverter._stream_gemini_to_openai,
            "openai_to_anthropic": FormatConverter._stream_openai_to_anthropic,
            "openai_to_gemini": FormatConverter._stream_openai_to_gemini,
            "anthropic_to_gemini": FormatConverter._stream_anthropic_to_gemini,
            "gemini_to_anthropic": FormatConverter._stream_gemini_to_anthropic,
        }

        if transform_key not in transform_map:
            raise ValueError(
                f"Unsupported stream transformation: {transform_key}")

        return transform_map[transform_key](data, model)

    # ─── Anthropic Stream → OpenAI ────────────────────────────────────────────

    @staticmethod
    def _stream_anthropic_to_openai(
            event_data: Dict[str, Any],
            model: str = "") -> Optional[Dict[str, Any]]:
        """
        Transform Anthropic SSE event to OpenAI delta format.
        
        Args:
            event_data: Anthropic stream event data
            model: Model name
            
        Returns:
            OpenAI-compatible chunk dict or None
        """
        event_type = event_data.get("type", "")

        if event_type == "content_block_delta":
            delta = event_data.get("delta", {})
            if delta.get("type") == "text_delta":
                return {
                    "id":
                    "chatcmpl-stream",
                    "object":
                    "chat.completion.chunk",
                    "created":
                    0,
                    "model":
                    model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": delta.get("text", "")
                        },
                        "finish_reason": None,
                    }]
                }
        elif event_type == "message_stop":
            return {
                "id": "chatcmpl-stream",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }]
            }
        elif event_type == "message_start":
            return {
                "id":
                event_data.get("message", {}).get("id", "chatcmpl-stream"),
                "object":
                "chat.completion.chunk",
                "created":
                0,
                "model":
                event_data.get("message", {}).get("model", model),
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant"
                    },
                    "finish_reason": None,
                }]
            }

        return None

    # ─── Gemini Stream → OpenAI ───────────────────────────────────────────────

    @staticmethod
    def _stream_gemini_to_openai(data: Dict[str, Any],
                                 model: str = "") -> Optional[Dict[str, Any]]:
        """
        Transform Gemini SSE event to OpenAI delta format.
        
        Args:
            data: Gemini stream chunk data
            model: Model name
            
        Returns:
            OpenAI-compatible chunk dict or None
        """
        if "error" in data:
            return {
                "id":
                "chatcmpl-stream",
                "object":
                "chat.completion.chunk",
                "created":
                0,
                "model":
                model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "content": f"Error: {data['error']}"
                    },
                    "finish_reason": None,
                }]
            }

        candidates = data.get("candidates", [])
        if not candidates:
            return None

        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])

        text_content = ""
        for part in parts:
            if "text" in part:
                text_content += part["text"]

        finish_reason = None
        if candidate.get("finishReason"):
            finish_reason_map = {
                "STOP": "stop",
                "MAX_TOKENS": "length",
                "SAFETY": "content_filter",
                "RECITATION": "content_filter",
                "OTHER": "stop",
            }
            finish_reason = finish_reason_map.get(
                candidate.get("finishReason"), "stop")

        return {
            "id":
            data.get("responseId", "chatcmpl-stream"),
            "object":
            "chat.completion.chunk",
            "created":
            0,
            "model":
            model,
            "choices": [{
                "index": 0,
                "delta": {
                    "content": text_content
                } if text_content else {},
                "finish_reason": finish_reason,
            }]
        }

    # ─── OpenAI Stream → Anthropic ────────────────────────────────────────────

    @staticmethod
    def _stream_openai_to_anthropic(data: Dict[str, Any],
                                    model: str = ""
                                    ) -> Optional[Dict[str, Any]]:
        """
        Transform OpenAI SSE event to Anthropic format.
        
        Args:
            data: OpenAI stream chunk data
            model: Model name
            
        Returns:
            Anthropic-compatible chunk dict or None
        """
        choices = data.get("choices", [])
        if not choices:
            return None

        choice = choices[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        if finish_reason == "stop":
            return {"type": "message_stop"}

        if "role" in delta:
            return {
                "type": "message_start",
                "message": {
                    "id": data.get("id", ""),
                    "model": data.get("model", model),
                    "role": "assistant",
                }
            }

        if "content" in delta:
            return {
                "type": "content_block_delta",
                "index": 0,
                "delta": {
                    "type": "text_delta",
                    "text": delta["content"],
                }
            }

        return None

    # ─── OpenAI Stream → Gemini ───────────────────────────────────────────────

    @staticmethod
    def _stream_openai_to_gemini(data: Dict[str, Any],
                                 model: str = "") -> Optional[Dict[str, Any]]:
        """
        Transform OpenAI SSE event to Gemini format.
        
        Args:
            data: OpenAI stream chunk data
            model: Model name
            
        Returns:
            Gemini-compatible chunk dict or None
        """
        choices = data.get("choices", [])
        if not choices:
            return None

        choice = choices[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        text_content = delta.get("content", "")

        finish_reason_map = {
            "stop": "STOP",
            "length": "MAX_TOKENS",
            "content_filter": "SAFETY",
        }
        gemini_finish = finish_reason_map.get(
            finish_reason, "STOP") if finish_reason else None

        result = {
            "candidates": [{
                "content": {
                    "role": "model",
                    "parts": [{
                        "text": text_content
                    }] if text_content else []
                },
            }]
        }

        if gemini_finish:
            result["candidates"][0]["finishReason"] = gemini_finish

        return result

    # ─── Anthropic Stream → Gemini ────────────────────────────────────────────

    @staticmethod
    def _stream_anthropic_to_gemini(data: Dict[str, Any],
                                    model: str = ""
                                    ) -> Optional[Dict[str, Any]]:
        """
        Transform Anthropic SSE event to Gemini format.
        
        Args:
            data: Anthropic stream event data
            model: Model name
            
        Returns:
            Gemini-compatible chunk dict or None
        """
        event_type = data.get("type", "")

        if event_type == "content_block_delta":
            delta = data.get("delta", {})
            if delta.get("type") == "text_delta":
                return {
                    "candidates": [{
                        "content": {
                            "role": "model",
                            "parts": [{
                                "text": delta.get("text", "")
                            }]
                        }
                    }]
                }
        elif event_type == "message_stop":
            return {
                "candidates": [{
                    "content": {
                        "role": "model",
                        "parts": []
                    },
                    "finishReason": "STOP"
                }]
            }

        return None

    # ─── Gemini Stream → Anthropic ────────────────────────────────────────────

    @staticmethod
    def _stream_gemini_to_anthropic(data: Dict[str, Any],
                                    model: str = ""
                                    ) -> Optional[Dict[str, Any]]:
        """
        Transform Gemini SSE event to Anthropic format.
        
        Args:
            data: Gemini stream chunk data
            model: Model name
            
        Returns:
            Anthropic-compatible chunk dict or None
        """
        candidates = data.get("candidates", [])
        if not candidates:
            return None

        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])

        text_content = ""
        for part in parts:
            if "text" in part:
                text_content += part["text"]

        finish_reason = candidate.get("finishReason")
        if finish_reason in ("STOP", "MAX_TOKENS"):
            return {"type": "message_stop"}

        if text_content:
            return {
                "type": "content_block_delta",
                "index": 0,
                "delta": {
                    "type": "text_delta",
                    "text": text_content,
                }
            }

        return None


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions (for backward compatibility with existing proxy.py)
# ─────────────────────────────────────────────────────────────────────────────


def transform_request_for_provider(
    body: Dict[str, Any],
    provider_type: str,
) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
    """
    Transform request body for a specific provider.
    Assumes input is in OpenAI format (gateway's internal format).
    
    Args:
        body: OpenAI-format request body
        provider_type: Target provider type (openai, anthropic, gemini)
        
    Returns:
        Tuple of (transformed_body, model_name, extra_info)
    """
    provider_map = {
        "openai": ProviderType.OPENAI,
        "anthropic": ProviderType.ANTHROPIC,
        "gemini": ProviderType.GEMINI,
        "ollama": ProviderType.OPENAI,
        "custom": ProviderType.OPENAI,
    }

    target = provider_map.get(provider_type.lower(), ProviderType.OPENAI)
    return FormatConverter.transform_request(body, ProviderType.OPENAI, target)


def transform_response_from_provider(
    data: Dict[str, Any],
    provider_type: str,
    model: str = "",
) -> Dict[str, Any]:
    """
    Transform response body from a specific provider to OpenAI format.
    
    Args:
        data: Provider-specific response body
        provider_type: Source provider type (openai, anthropic, gemini)
        model: Model name
        
    Returns:
        OpenAI-format response dict
    """
    provider_map = {
        "openai": ProviderType.OPENAI,
        "anthropic": ProviderType.ANTHROPIC,
        "gemini": ProviderType.GEMINI,
        "ollama": ProviderType.OPENAI,
        "custom": ProviderType.OPENAI,
    }

    source = provider_map.get(provider_type.lower(), ProviderType.OPENAI)
    return FormatConverter.transform_response(data, source,
                                              ProviderType.OPENAI, model)


def transform_stream_chunk_from_provider(
    data: Dict[str, Any],
    provider_type: str,
    model: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Transform stream chunk from a specific provider to OpenAI format.
    
    Args:
        data: Provider-specific stream chunk
        provider_type: Source provider type
        model: Model name
        
    Returns:
        OpenAI-format chunk dict or None
    """
    provider_map = {
        "openai": ProviderType.OPENAI,
        "anthropic": ProviderType.ANTHROPIC,
        "gemini": ProviderType.GEMINI,
        "ollama": ProviderType.OPENAI,
        "custom": ProviderType.OPENAI,
    }

    source = provider_map.get(provider_type.lower(), ProviderType.OPENAI)
    return FormatConverter.transform_stream_chunk(data, source,
                                                  ProviderType.OPENAI, model)
