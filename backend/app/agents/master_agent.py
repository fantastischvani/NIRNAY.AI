from langgraph.graph import StateGraph, END
from pydantic import BaseModel
import json
from app.utils.schemas import RouterOutput, SynthOutput
from app.utils.prompts import MASTER_AGENT_ROUTER_PROMPT, SYNTH_PROMPT
from app.agents import (report_generator_agent, web_intel_agent)
    
from app.config.settings import settings
from openai import OpenAI


client = OpenAI(
    api_key=settings.GOOGLE_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

class MasterState(BaseModel):
    selected_agents: list = []
    routing_reason: str = ""
    results: dict = {}  # safe when workers run sequentially
    
    
    
    
# PUBLIC ENTRY FUNCTION
async def run_master_agent(query: str):
    state = MasterState()
    final = await master_chain.ainvoke(
        state,
        config={"configurable": {"user_query": query}}
    )
    return final

