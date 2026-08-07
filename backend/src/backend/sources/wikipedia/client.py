import logging
import re
from urllib.parse import quote

import requests

from backend.core.config import config
from backend.sources.wikipedia.models import SearchResult, WikipediaPage

logger = logging.getLogger(__name__)


class WikipediaClient:
    BASE_URL = "https://en.wikipedia.org/w/api.php"
    BOILERPLATE_SECTIONS = {
        "see also",
        "references",
        "external links",
        "further reading",
        "notes",
        "citations",
        "bibliography",
        "sources",
    }
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
            "exsectionformat": "wiki",
            "redirects": 1,
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

    def resolve_topic_to_article(self, topic):
        results = self.search(topic, limit=3)
        if not results:
            logger.warning("No Wikipedia article resolved for topic '%s'", topic)
            return None
        top = results[0]
        content = self.get_page(top.title)
        logger.info("Resolved topic '%s' -> article '%s'", topic, top.title)
        return {"title": top.title, "content": content.content}

    def parse_sections(self, full_text):
        heading_pattern = re.compile(r"^(=+)\s*(.*?)\s*=+$")
        lines = full_text.split("\n")

        raw_sections = []
        current = {"title": None, "level": 2, "text_lines": []}

        for line in lines:
            match = heading_pattern.match(line.strip())
            if match:
                raw_sections.append(current)
                level = len(match.group(1))
                current = {
                    "title": match.group(2).strip(),
                    "level": level,
                    "text_lines": [],
                }
            else:
                current["text_lines"].append(line)
        raw_sections.append(current)

        stack = []
        sections = []
        for s in raw_sections:
            title = s["title"] or "Introduction"
            if title.lower() in self.BOILERPLATE_SECTIONS:
                continue

            while stack and stack[-1][0] >= s["level"]:
                stack.pop()
            stack.append((s["level"], title))

            text = "\n".join(l for l in s["text_lines"] if l.strip())
            if not text:
                continue

            sections.append(
                {
                    "title": title,  # leaf title — new
                    "breadcrumb": " > ".join(t for _, t in stack),
                    "text": text,
                }
            )

        logger.info("Parsed %d sections from article", len(sections))
        return sections

    def get_section_url(self, article_title, section_title):
        base = f"https://en.wikipedia.org/wiki/{quote(article_title.replace(' ', '_'))}"
        if section_title == "Introduction":
            return base  # intro has no heading, so no anchor to link to
        anchor = quote(section_title.replace(" ", "_"))
        return f"{base}#{anchor}"

    def get_page_by_id(self, page_id: int) -> WikipediaPage:
        pass

    def page_exists(self, title: str) -> bool:
        pass
