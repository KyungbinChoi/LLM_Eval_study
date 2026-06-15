# %% [markdown]
# ## Summary
# * 사내 문서를 기반으로 직원들의 질문에 답변하는 AI agent
#     * 직원들의 질문을 받아 관련 사내 문서를 검색
#     * FAQ 문서에서 빠르게 답변을 찾거나, 일반 문서에서 정보를 추출
#     * retrieval_tool 활용하여 정확한 답변 제공
# 
# 

# %% [markdown]
# ### 사내 문서 목록
# - delegation_of_authority - 권한 위임 규정
# - employee_benefits_and_welfare_faq - 복리후생 FAQ
# - employee_benefits_and_welfare_guide - 복리후생 가이드
# - employee_handbook_and_hr_policy - 인사 규정 핸드북
# expense_management_guide - 경비 처리 가이드
# it_support_guide - IT 지원 가이드
# legal_and_compliance_policy - 법무/컴플라이언스 정책

# %%
from dotenv import load_dotenv
load_dotenv()

# %%
from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

# # 문서 로드
# loader = DirectoryLoader(
#     "./documents_with_english_titles_md",
#     glob="**/*.md",
#     loader_cls=UnstructuredMarkdownLoader,
#     show_progress=True,
# )
# documents = loader.load()
# print(f"로드된 문서 수: {len(documents)}개")

# # 텍스트 분할
# text_splitter = RecursiveCharacterTextSplitter(
#     chunk_size=1000,
#     chunk_overlap=200,
# )
# splits = text_splitter.split_documents(documents)
# print(f"분할된 청크 수: {len(splits)}개")

# # Gemini 임베딩 모델 초기화
# embeddings = GoogleGenerativeAIEmbeddings(
#     model="models/gemini-embedding-001",
#     task_type="retrieval_document",
# )

# # Chroma vector store 생성 및 배치 추가 (from_documents 배치 버그 우회)
# PERSIST_DIR = "./inhouse_collection"
# BATCH_SIZE = 100

# vectorstore = Chroma(
#     collection_name="inhouse-collection",
#     embedding_function=embeddings,
#     persist_directory=PERSIST_DIR,
# )

# for i in range(0, len(splits), BATCH_SIZE):
#     batch = splits[i : i + BATCH_SIZE]
#     vectorstore.add_documents(batch)
#     print(f"  {min(i + BATCH_SIZE, len(splits))}/{len(splits)} 청크 추가 완료")

# print(f"\nChroma vector store 저장 완료 → {PERSIST_DIR}")

# # Retriever 생성
# retriever = vectorstore.as_retriever()
# print("Retriever 생성 완료")

# %%
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    task_type="retrieval_document",
)

# Chroma 벡터 스토어 연결
vectorstore = Chroma(
    collection_name="inhouse-collection",
    embedding_function=embeddings,
    persist_directory="inhouse_collection",
)

# Retriever 생성 (벡터 스토어에서 관련 문서를 검색하는 역할)
retriever = vectorstore.as_retriever()

# %%
query = '연차 휴가는 총 몇일인가요?'
retrieved_docs = vectorstore.similarity_search(query, k =3)
retrieved_docs

# %% [markdown]
# ## Tool 정의
# * check_faq : FAQ 문서에서 질문에 대한 답변이 있는지 확인
# * get_document_name : 질문에 가장 적합한 문서 이름을 결정
# * retriever_tool : 특정 문서에서 관련 내용을 검색

# %%
from langchain_core.prompts import ChatPromptTemplate 
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import tool
from langchain_core.documents import Document
from pydantic import BaseModel

# 반환 타입 정의 (Pydantic 모델)
# - is_in_faq: FAQ에 관련 내용이 있는지 여부
# - context: FAQ에서 찾은 관련 문서 리스트
class CheckFaqResponse(BaseModel):
    is_in_faq: bool
    context: list[Document]

@tool
def check_faq(question: str) -> CheckFaqResponse:
    """Check if the question is in the FAQ.
    If the question is in the FAQ, return the context of the question.
    Otherwise, return an empty list.
    """
    # 1단계: FAQ 문서에서 관련 내용 검색 (필터링: source="employee_benefits_and_welfare_faq")
    context = retriever.invoke(question, filter={"source": 'documents_with_english_titles_md/employee_benefits_and_welfare_faq.md'})
    
    # 2단계: LLM을 사용하여 검색된 내용이 질문과 관련있는지 판단
    check_faq_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful assistant that checks if the question is in the FAQ. 
If the question is in the FAQ, return 'Yes'. Otherwise, return 'No'."""),
        ("user", "Question: {question}\nContext: {context}"),
    ])
    check_faq_chain = check_faq_prompt | llm | StrOutputParser()
    is_in_faq = check_faq_chain.invoke({"question": question, "context": context})
    
    # 3단계: 결과 반환 (FAQ에 있으면 context 포함, 없으면 빈 리스트)
    return {"is_in_faq": is_in_faq == "Yes", "context": context if is_in_faq == "Yes" else []}

# %%
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate 
from langchain_core.output_parsers import StrOutputParser

@tool
def get_document_name(question: str) -> str:
    """Get the document name based on the question."""
    
    # 문서 분류 프롬프트
    # - 사용 가능한 문서 목록을 제시하고
    # - 질문에 가장 적합한 문서를 선택하도록 지시
    determine_document_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", """You are a helpful assistant that determines the most relevant document name based on the user's question. 
Choose from the following document names:
- delegation_of_authority
- employee_benefits_and_welfare_guide
- employee_handbook_and_hr_policy
- expense_management_guide
- it_support_guide
- legal_and_compliance_policy

Return ONLY the document name (e.g., 'it_support_guide').

Examples:
- If the question is about who can approve expenses, return 'delegation_of_authority' or 'expense_management_guide' as appropriate.
- If the question is about employee benefits, return 'employee_benefits_and_welfare_guide'.
- If the question is about HR policies or the employee handbook, return 'employee_handbook_and_hr_policy'.
- If the question is about IT support or technical issues, return 'it_support_guide'.
- If the question is about legal or compliance matters, return 'legal_and_compliance_policy'.
"""),
        ("user", "Question: {question}"),
    ]
)
    # Chain 실행: 프롬프트 → LLM → 문자열 파싱
    determine_document_chain = determine_document_prompt | llm | StrOutputParser()
    document_name = determine_document_chain.invoke({"question": question})
    return document_name

# %%
from typing import List
from langchain_core.tools.retriever import create_retriever_tool

@tool
def retriever_tool(question: str, document_name: str) -> List[Document]:
    """Retrieve the document based on the question and document name."""
    # 벡터 스토어에서 검색 (특정 문서만 필터링)
    # - filter={"source": document_name}를 통해 특정 문서에서만 검색
    # - 이렇게 하면 검색 정확도가 높아짐
    context = retriever.invoke(question, filter={"source": "documents_with_english_titles_md/"+document_name+".md"})
    return context

# %% [markdown]
# ### 에이전트의 작동 방식
# 1. 사용자 질문 수신
# 2. 먼저 check_faq로 FAQ에서 답변 확인 시도
# 3. FAQ에 없으면 get_document_name으로 적절한 문서 결정
# 4. retriever_tool로 해당 문서에서 관련 내용 검색
# 5. 검색된 내용을 바탕으로 답변 생성

# %%
from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-pro-preview",
        temperature=1
    )

# %%

from langchain.agents import create_agent

# 에이전트 생성
# - model: 사용할 LLM 모델
# - tools: 에이전트가 사용할 도구 목록
# - system_prompt: 에이전트의 행동 지침
agent = create_agent(
    model=llm,
    tools=[retriever_tool, check_faq, get_document_name],
    system_prompt="""You are an AI assistant that helps employees answer questions about company policies and procedures. 
First use the `check_faq` tool to see if the question is in the FAQ. If it is, use the provided context to answer the question.
If the question is not in the FAQ, use the `get_document_name` tool to determine which document is most relevant to the question, 
and then use the `retriever_tool` to retrieve
Use the tools provided to you to answer the user's question
Please provide a fianl answer to the user's question based on the information you have retrieved from your tool  without adding any extra information.
Make sure not to mention anything that is not in the retrieved documents or the FAQ context in your final answer.
""",
)

# %%
#agent.invoke({"messages": [{"role": "user", "content": "연차 휴가는 몇 일인가요?"}]})

# %%



