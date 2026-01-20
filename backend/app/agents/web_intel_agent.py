from openai import OpenAI
from app.config.settings import settings
import json
from app.tools.web_tools import search_all
from app.utils.prompts import WEB_INTEL_SYSTEM_PROMPT, WEB_INTEL_SUMMARY_PROMPT, MASTER_PROMPT
from .base_agent import BaseAgent


client = OpenAI(
    api_key=settings.GOOGLE_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web (papers, guidelines, news, forums). Returns a JSON array of normalized documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                    "types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional filter: paper, web, news, forum"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

import re

def _unwrap_codeblock(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else text.strip()

def _choose_quotes_from_docs(docs, max_quotes=2, max_words=25):
    quotes = []
    for d in docs:
        text_source = (d.get("full_text") or d.get("snippet") or "")
        if not text_source:
            continue
        # split into sentences & pick the first sentence with >6 words
        sents = re.split(r'(?<=[.!?])\s+', text_source)
        for s in sents:
            words = s.strip().split()
            if len(words) >= 6:
                quote = " ".join(words[:max_words])
                quotes.append({"text": quote, "source_url": d.get("url"), "context": d.get("title")})
                break
        if len(quotes) >= max_quotes:
            break
    return quotes[:max_quotes]

def synthesize_summary(query: str, documents: list):
    # Build docs_payload including full_text when available
    docs_payload = []
    for d in documents:
        docs_payload.append({
            "title": d.get("title"),
            "url": d.get("url"),
            "snippet": d.get("snippet"),
            "full_text": d.get("full_text", ""),
            "source": d.get("source"),
            "type": d.get("type"),
            "date": d.get("date")
        })

    messages = [
        {"role": "system", "content": WEB_INTEL_SUMMARY_PROMPT},
        {"role": "user", "content": f"Create a concise structured summary for the query: {query}"},
        {"role": "assistant", "content": json.dumps(docs_payload)}
    ]

    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=messages,
        temperature=0.0
    )
    msg = response.choices[0].message
    raw = msg.content or ""
    cleaned = _unwrap_codeblock(raw)

    # Try parse JSON - if parsing fails, fallback to building structure ourselves
    try:
        parsed = json.loads(cleaned)
        summary = parsed.get("summary", [])
        quotes = parsed.get("quotes", [])[:2]
        top_sources = parsed.get("top_sources", [])
        notes = parsed.get("notes", "")
    except Exception:
        summary = [f"{d.get('title')} — {d.get('url')}" for d in docs_payload[:3]]
        quotes = _choose_quotes_from_docs(docs_payload, max_quotes=2)
        top_sources = [{"title": d.get("title"), "url": d.get("url"), "type": d.get("type"), "credibility": "High"} for d in docs_payload[:3]]
        notes = "Auto-generated summary (fallback parsing)."

    # Ensure quotes are well-formed and truncated to 25 words
    for i, q in enumerate(quotes):
        text = q.get("text") if isinstance(q, dict) else str(q)
        words = text.split()
        if len(words) > 25:
            text = " ".join(words[:25]) + "..."
        quotes[i] = {"text": text, "source_url": q.get("source_url"), "context": q.get("context")}

    out = {
        "query": query,
        "summary": summary,
        "quotes": quotes,
        "top_sources": top_sources,
        "guideline_extracts": parsed.get("guideline_extracts", []) if 'parsed' in locals() and isinstance(parsed, dict) else [],
        "notes": notes,
        "documents_used": docs_payload
    }
    return out

def handle_user_query(user_query: str):
    """
    Orchestrator:
    - Ask the LLM (system prompt) to call search_web tool
    - Execute search_web when requested by the LLM
    - Call LLM synthesizer for final structured summary
    """
    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[
            {"role": "system", "content": WEB_INTEL_SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ],
        tools=tools,
        tool_choice="auto"
    )
    message = response.choices[0].message

    if message.tool_calls:
        tool_call = message.tool_calls[0]
        args = json.loads(tool_call.function.arguments)
        query = args.get("query")
        limit = args.get("limit", 6)
        types = args.get("types", None)

        print("LLM called tool: search_web")
        print("Args:", args)

        docs = search_all(query, limit=limit, types=types)
        print(f"Retrieved {len(docs)} documents from connectors")
        summary = synthesize_summary(query, docs)
        final_prompt = MASTER_PROMPT.format(
            docs_array=json.dumps(docs, indent=2),
            summary_array=json.dumps(summary, indent=2)
        )

        messages=[
            {"role": "user", "content": final_prompt}
        ],
        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=messages,
            temperature=0.0
        )
        final_result = response.choices[0].message.content
        return {
            "query": query,
            "documents_count": len(docs),
            "result": final_result
        }
    
    # If no tool used, return LLM content (unlikely with strict prompt)
    return {"response": message["content"]}

class WebIntelligenceAgent(BaseAgent):

    async def run(self, query: str, context=None):
        # print("Web Intelligence Agent CALLED")
        result = handle_user_query(query)
        return {
            "agent": "Web Intelligence Agent",
            "output": result.model_dump()
        }


def main():
    print("\nWeb Intelligence Agent ")
    q = input("\nEnter your query: ")
    out = handle_user_query(q)
    print("\nRESULT:  ")
    print(out["result"])

if __name__ == "__main__":
    main()