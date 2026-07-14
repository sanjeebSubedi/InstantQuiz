import requests

from backend.core.config import config
from backend.sources.wikipedia.models import SearchResult, WikipediaPage


class WikipediaClient:
    BASE_URL = "https://en.wikipedia.org/w/api.php"
    headers = {"User-Agent": f"QuizApp/0.1 ({config.EMAIL})"}

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": limit,
        }

        response = requests.get(self.BASE_URL, headers=self.headers, params=params)
        response.raise_for_status()

        data = response.json()["query"]["search"]

        return [
            SearchResult(
                page_id=result["pageid"],
                title=result["title"],
                snippet=result["snippet"],
            )
            for result in data
        ]

    def get_page(self, title: str) -> WikipediaPage:
        params = {
            "action": "query",
            "prop": "extracts",
            "titles": title,
            "explaintext": True,
            "format": "json",
        }

        response = requests.get(self.BASE_URL, headers=self.headers, params=params)

        pages = response.json()["query"]["pages"]

        page = next(iter(pages.values()))

        return WikipediaPage(
            page_id=page["pageid"],
            title=page["title"],
            url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
            content=page.get("extract", ""),
        )

    def get_page_by_id(self, page_id: int) -> WikipediaPage:
        pass

    def page_exists(self, title: str) -> bool:
        pass
