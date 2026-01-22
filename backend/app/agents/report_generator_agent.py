from pydantic import BaseModel
from typing import List
import json
from app.utils.schemas import SynthOutput, TableSpec, ChartSpec
from app.config.settings import settings
from openai import OpenAI


client = OpenAI(
    api_key=settings.GOOGLE_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)


class ReportState(BaseModel):
    """State for the report generator agent"""
    query: str = ""
    context: str = ""
    report_sections: List[str] = []
    final_report: str = ""


def run_report_generator_agent(query: str, context: str = "") -> SynthOutput:
    """
    Report Generator Agent - Creates comprehensive reports based on data.
    
    Args:
        query: The original user query
        context: Context from previous agents
        
    Returns:
        SynthOutput with comprehensive report
    """
    try:
        # Build the message
        context_str = f"\nContext from previous analysis:\n{context}" if context else ""
        
        message = f"""You are a professional report generator. Create a comprehensive report based on the following:

User Query: {query}
{context_str}

Generate a professional report with:
1. Executive Summary
2. Key Findings
3. Recommendations
4. Conclusions

Format the response as JSON with:
{{"final_summary": "summary text", "recommendations": "recommendations text", "tables": [], "charts": []}}
"""
        
        response = client.chat.completions.create(
            model="gemini-3-flash-preview",
            messages=[
                {"role": "user", "content": message}
            ]
        )
        
        content = response.choices[0].message.content
        
        try:
            # Try to parse JSON response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                result = json.loads(json_str)
                
                return SynthOutput(
                    final_summary=result.get("final_summary", content),
                    recommendations=result.get("recommendations", ""),
                    tables=result.get("tables", []),
                    charts=result.get("charts", [])
                )
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Fallback to plain text response
        return SynthOutput(
            final_summary=content,
            recommendations="See findings above for detailed recommendations.",
            tables=[],
            charts=[]
        )
        
    except Exception as e:
        print(f"Error in report generator agent: {str(e)}")
        return SynthOutput(
            final_summary=f"Error generating report: {str(e)}",
            recommendations="Please try again with a different query.",
            tables=[],
            charts=[]
        )
