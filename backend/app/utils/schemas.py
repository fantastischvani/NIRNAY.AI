from pydantic import BaseModel
from typing import List, Optional


class RouterOutput(BaseModel):
    selected_agents: List[str]
    reason: str


class TableSpec(BaseModel):
    title: str
    columns: List[str]
    rows: List[List[str]]


class ChartSpec(BaseModel):
    title: str
    labels: List[str]
    values: List[float]


class SynthOutput(BaseModel):
    final_summary: str
    recommendations: str
    tables: List[TableSpec] = []
    charts: List[ChartSpec] = []
