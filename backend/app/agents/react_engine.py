"""
ReAct 引擎 - ReAct Execution Engine
实现 Thought → Action → Observation 循环
支持对话场景和自动化场景
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import logging
import json
import re
from app.agents.base import AgentResult
from app.agents.tools import Tool, ToolResult, get_registry
from app.config import settings

logger = logging.getLogger(__name__)


class ReActStepType(str, Enum):
    """ReAct 步骤类型"""
    THINK = "think"
    ACTION = "action"
    OBSERVATION = "observation"
    FINAL = "final"
    ERROR = "error"


@dataclass
class ReActStep:
    """ReAct 执行步骤"""
    step_type: ReActStepType
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict] = None
    tool_result: Optional[Any] = None

    def to_dict(self) -> Dict:
        return {
            "type": self.step_type.value,
            "content": self.content,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_result": self.tool_result
        }


class ReActEngine:
    """ReAct 执行引擎"""

    def __init__(
        self,
        max_iterations: int = 10,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ):
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.registry = get_registry()
        self.logger = logging.getLogger("react_engine")

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        tools_schema = self.registry.get_schemas()
        tools_desc = json.dumps(tools_schema, ensure_ascii=False, indent=2)

        return f"""你是一个智能邮件助手，使用 ReAct (Reasoning + Acting) 模式来完成任务。

## 可用工具
{tools_desc}

## ReAct 模式说明
你可以通过以下步骤来完成任务：
1. THINK: 分析用户问题，决定下一步做什么
2. ACTION: 选择一个工具并提供输入参数来执行
3. OBSERVATION: 观察工具执行的结果
4. FINAL: 基于所有观察给出最终答案

## 输出格式
请严格按照以下 JSON 格式输出你的思考：
{{
    "thought": "分析当前情况和决定下一步",
    "action": "工具名称（如果需要执行工具，否则为 null）",
    "action_input": {{"参数": "值"}}  // 如果 action 为 null 则为空对象
}}

## 重要规则
- 如果问题可以一次性回答，直接输出 FINAL 格式
- 如果需要获取信息，使用工具来获取
- 每个思考只做一件事，不要一次请求多个工具
- 确保 action_input 中的参数名和类型与工具定义一致
"""

    def _parse_response(self, response_content: str) -> Dict:
        """解析 AI 响应"""
        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            self.logger.warning(f"Failed to parse response: {e}")

        return {"thought": response_content, "action": None, "action_input": {}}

    def _execute_action(self, tool_name: str, tool_input: Dict) -> ToolResult:
        """执行工具"""
        self.logger.info(f"Executing tool: {tool_name} with input: {tool_input}")
        result = self.registry.execute(tool_name, **tool_input)
        return result

    def _build_messages(
        self,
        user_message: str,
        conversation_history: List[Dict] = None
    ) -> List[Dict]:
        """构建消息列表"""
        messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]

        # 添加历史对话
        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        return messages

    def chat(
        self,
        message: str,
        conversation_history: List[Dict] = None,
        context: Dict = None
    ) -> AgentResult:
        """ReAct 对话模式"""
        result = AgentResult(success=False)
        steps: List[ReActStep] = []

        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL
            )

            messages = self._build_messages(message, conversation_history)

            # 添加上下文信息
            if context:
                context_str = json.dumps(context, ensure_ascii=False, default=str)
                messages.insert(1, {
                    "role": "system",
                    "content": f"当前上下文信息：\n{context_str}"
                })

            for iteration in range(self.max_iterations):
                self.logger.info(f"ReAct iteration {iteration + 1}/{self.max_iterations}")

                # 调用 AI
                response = client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )

                response_content = response.choices[0].message.content
                parsed = self._parse_response(response_content)

                thought = parsed.get("thought", "")
                action = parsed.get("action")
                action_input = parsed.get("action_input", {})

                # 添加思考步骤
                steps.append(ReActStep(
                    step_type=ReActStepType.THINK,
                    content=thought
                ))
                result.add_step({"type": "think", "content": thought})

                # 如果没有动作，返回 FINAL
                if action is None:
                    steps.append(ReActStep(
                        step_type=ReActStepType.FINAL,
                        content=thought
                    ))
                    result.add_step({"type": "final", "content": thought})
                    result.success = True
                    result.data = {"response": thought, "steps": [s.to_dict() for s in steps]}
                    break

                # 执行动作
                tool_result = self._execute_action(action, action_input)

                steps.append(ReActStep(
                    step_type=ReActStepType.ACTION,
                    content=f"执行工具: {action}",
                    tool_name=action,
                    tool_input=action_input,
                    tool_result=tool_result.to_dict()
                ))
                result.add_step({
                    "type": "action",
                    "tool": action,
                    "input": action_input,
                    "result": tool_result.to_dict()
                })

                # 添加观察结果
                observation = tool_result.raw_output if tool_result.success else tool_result.error
                steps.append(ReActStep(
                    step_type=ReActStepType.OBSERVATION,
                    content=observation,
                    tool_result=tool_result.to_dict()
                ))
                result.add_step({"type": "observation", "content": observation[:200]})

                # 将工具结果添加到消息历史
                messages.append({"role": "assistant", "content": response_content})
                messages.append({
                    "role": "user",
                    "content": f"工具执行结果：\n{observation}\n\n请基于以上结果继续思考或给出最终回答。"
                })

            else:
                # 达到最大迭代次数
                result.error = f"达到最大迭代次数 {self.max_iterations}"
                result.add_step({"type": "error", "content": "max iterations reached"})

        except Exception as e:
            self.logger.error(f"ReAct engine error: {e}")
            result.error = str(e)
            result.add_step({"type": "error", "message": str(e)})

        return result

    def process(
        self,
        task: str,
        initial_input: Dict = None,
        callbacks: Dict[str, Callable] = None
    ) -> AgentResult:
        """ReAct 自动化处理模式"""
        result = AgentResult(success=False)
        steps: List[ReActStep] = []

        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL
            )

            # 构建初始任务描述
            task_desc = task
            if initial_input:
                task_desc += f"\n\n初始输入：{json.dumps(initial_input, ensure_ascii=False, default=str)}"

            messages = [
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": f"请自动执行以下任务：\n{task_desc}"}
            ]

            for iteration in range(self.max_iterations):
                self.logger.info(f"ReAct process iteration {iteration + 1}/{self.max_iterations}")

                response = client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )

                response_content = response.choices[0].message.content
                parsed = self._parse_response(response_content)

                thought = parsed.get("thought", "")
                action = parsed.get("action")
                action_input = parsed.get("action_input", {})

                steps.append(ReActStep(
                    step_type=ReActStepType.THINK,
                    content=thought
                ))
                result.add_step({"type": "think", "content": thought})

                if action is None:
                    steps.append(ReActStep(
                        step_type=ReActStepType.FINAL,
                        content=thought
                    ))
                    result.success = True
                    result.data = {"result": thought, "steps": [s.to_dict() for s in steps]}
                    break

                tool_result = self._execute_action(action, action_input)

                steps.append(ReActStep(
                    step_type=ReActStepType.ACTION,
                    content=f"执行工具: {action}",
                    tool_name=action,
                    tool_input=action_input,
                    tool_result=tool_result.to_dict()
                ))

                observation = tool_result.raw_output if tool_result.success else tool_result.error
                steps.append(ReActStep(
                    step_type=ReActStepType.OBSERVATION,
                    content=observation
                ))

                messages.append({"role": "assistant", "content": response_content})
                messages.append({
                    "role": "user",
                    "content": f"工具执行结果：\n{observation}\n\n请继续执行任务。"
                })

            else:
                result.error = f"达到最大迭代次数 {self.max_iterations}"

        except Exception as e:
            self.logger.error(f"ReAct process error: {e}")
            result.error = str(e)

        return result


# 全局 ReAct 引擎实例
_react_engine = ReActEngine()


def get_react_engine() -> ReActEngine:
    """获取全局 ReAct 引擎"""
    return _react_engine
