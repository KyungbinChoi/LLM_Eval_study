"""
marketing_agent.py — 마케팅 콘텐츠 에이전트 + 설정 가능한 병렬 에이전트

Export:
    agent: 단일 마케팅 에이전트 (웹 검색 도구 포함)
    build_parallel_agent(n_workers): N명 카피라이터 병렬 에이전트 팩토리
"""

from typing import Annotated, TypedDict
import operator

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.agents import create_agent
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Send

load_dotenv()

# ============================================================
# 1. LLM & 도구
# ============================================================
from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-pro-preview",
        temperature=1
    )

tavily_search = TavilySearchResults(max_results=3)
tools = [tavily_search]

# ============================================================
# 2. 단일 에이전트
# ============================================================
agent = create_agent(
    llm,
    tools,
    system_prompt="""You are a senior marketing copywriter at a top creative agency.

Your job is to create marketing content that meets the client's brief EXACTLY.

You have access to the following tool:
- Tavily Search: Use this to research trends, competitors, target audience insights, and industry benchmarks BEFORE writing any copy. Good research leads to better copy.

CRITICAL RULES:
1. ALWAYS research the topic with Tavily Search before writing copy. Never write without research.
2. Follow the brief's requirements precisely: tone, length, format, target audience, key messages.
3. Include ALL mandatory elements specified in the brief (CTAs, hashtags, keywords, etc.)
4. If the brief specifies a character or word limit, count carefully and stay within it.
5. Present your final content clearly at the end of your response.
""",
)

# ============================================================
# 3. 병렬 에이전트 팩토리
# ============================================================

class WorkerResult(TypedDict):
    worker_id: int
    answer: str
    success: bool

class WorkerInput(TypedDict):
    question: str
    worker_id: int

class ParallelAgentState(TypedDict):
    question: str
    worker_results: Annotated[list[WorkerResult], operator.add]
    final_answer: str
    messages: Annotated[list, add_messages]

selector_llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-pro-preview",
        temperature=0
    )

SELECTOR_PROMPT = """You are a senior creative director reviewing multiple drafts from your copywriting team.
Given the original BRIEF and multiple CANDIDATE drafts, select the one that best meets the brief.
Evaluation criteria (in order of importance):
1. BRIEF COMPLIANCE: Does it include ALL required elements (tone, format, length, CTA, hashtags, keywords)?
2. ACCURACY: Are any claims or statistics factually correct and not made up?
3. TARGET AUDIENCE FIT: Does the language and style match the specified audience?
4. CREATIVITY: Is it engaging and memorable, not generic or cliché?
5. COMPLETENESS: Is it a finished, ready-to-publish piece (not a draft or outline)?
Return ONLY the best draft text. Do not add commentary or explanation."""


def build_parallel_agent(n_workers: int):
    """N명의 카피라이터를 병렬 실행하는 에이전트를 생성합니다."""

    def fan_out(state: ParallelAgentState) -> list[Send]:
        return [
            Send("worker", {"question": state["question"], "worker_id": i})
            for i in range(n_workers)
        ]

    def worker(state: WorkerInput) -> dict:
        try:
            result = agent.invoke({"messages": [HumanMessage(content=state["question"])]})
            return {"worker_results": [{"worker_id": state["worker_id"], "answer": result["messages"][-1].content, "success": True}]}
        except Exception as e:
            return {"worker_results": [{"worker_id": state["worker_id"], "answer": f"Error: {e}", "success": False}]}

    def aggregate(state: ParallelAgentState) -> dict:
        successful = [r for r in state["worker_results"] if r["success"]]
        if not successful:
            final = "모든 카피라이터가 실패했습니다."
        elif len(successful) == 1:
            final = successful[0]["answer"]
        else:
            candidates = "\n\n".join(f"--- Draft {r['worker_id']} ---\n{r['answer']}" for r in successful)
            response = selector_llm.invoke([
                SystemMessage(content=SELECTOR_PROMPT),
                HumanMessage(content=f"BRIEF: {state['question']}\n\nCANDIDATE DRAFTS:\n{candidates}"),
            ])
            final = response.content
        return {"final_answer": final, "messages": [AIMessage(content=final)]}

    builder = StateGraph(ParallelAgentState)
    builder.add_node("worker", worker)
    builder.add_node("aggregate", aggregate)
    builder.add_conditional_edges(START, fan_out, ["worker"])
    builder.add_edge("worker", "aggregate")
    builder.add_edge("aggregate", END)
    return builder.compile()