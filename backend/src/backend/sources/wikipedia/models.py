from pydantic import BaseModel


class SearchResult(BaseModel):
    page_id: int
    title: str
    snippet: str


class WikipediaPage(BaseModel):
    page_id: int
    title: str
    url: str
    content: str
