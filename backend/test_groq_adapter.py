import os
from langchain_groq import ChatGroq
from langchain_core.language_models.llms import BaseLLM
from langchain_core.outputs import LLMResult, Generation
from crewai import Agent

os.environ["GROQ_API_KEY"] = os.environ.get("GROQ_API_KEY", "")

chat = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)

class GroqAdapter(BaseLLM):
    chat: ChatGroq
    
    @property
    def _llm_type(self) -> str:
        return "groq_adapter"
        
    def _generate(self, prompts, stop=None, run_manager=None, **kwargs):
        results = []
        for prompt in prompts:
            response = self.chat.invoke(prompt)
            results.append([Generation(text=response.content)])
        return LLMResult(generations=results)

try:
    agent = Agent(
        role="Test",
        goal="Test",
        backstory="Test",
        llm=GroqAdapter(chat=chat)
    )
    print("SUCCESS")
except Exception as e:
    print("ERROR:", e)
