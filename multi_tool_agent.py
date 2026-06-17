from dotenv import load_dotenv
load_dotenv()

from langchain_google_community import GmailToolkit

gmail_toolkit = GmailToolkit()

gmail_tools = gmail_toolkit.get_tools()

from langchain_tavily import TavilySearch

tavily_search_tool = TavilySearch(
    max_results=5,    
    topic="general",  
)

from langchain.tools import tool
from langchain_experimental.utilities import PythonREPL

python_repl = PythonREPL() 

@tool
def python_repl_tool(command: str) -> str:
    """A Python shell. Use this to execute python commands. 
    Input should be a valid python command. 
    If you want to see the output of a value, you should print it out with `print(...)`."""
    # 주어진 Python 명령어 실행 후 결과 반환
    return python_repl.run(command)

from langchain_community.agent_toolkits.load_tools import load_tools
from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-pro-preview",
        temperature=1
    )

arxiv_tool = load_tools(
    ["arxiv"],  
)
tools = [python_repl_tool, tavily_search_tool] + arxiv_tool + gmail_tools

from langchain.agents import create_agent

agent = create_agent(
    llm, 
    tools, 
    system_prompt="""You are a helpful assistant that can answer questions and help with tasks. Make sure to use one of the tools provdied to you to answer the users question.
You have an access to the following tools:
Do not use Tavily Search for searching academic papers. Use ArXiv tool for that.
And make sure you do not use Tavily Search along with ArXiv unless one fails. 
- Tavily Search: Use this tool to search the web for information. It can return up to 5 results. Use this tool for general information search.
- Python REPL: Use this tool to execute Python code. If you want to see the output of a value, you should print it out with `print(...)`.
- ArXiv: Use this tool to search for academic papers on arXiv.org. You can search by title, author, or keywords.
- Gmail Toolkit: Use these tools to interact with Gmail. You can search for emails, read specific emails, create drafts, and send emails. Use these tools to help the user manage their email.
"""
)