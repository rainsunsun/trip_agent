from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

# 加载我们在 .env 里写的配置
load_dotenv()

def get_llm():
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL_ID"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        timeout=int(os.getenv("LLM_TIMEOUT", 60)),
        temperature=0 # 设置为 0 以获得更稳定的输出
    )