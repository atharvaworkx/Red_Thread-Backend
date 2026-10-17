import hashlib
import logging
import re
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
import feedparser
from .ssrf_guard import safe_fetch_url, SSRFValidationError

logger = logging.getLogger(__name__)


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()[:32]


def clean_html_text(html_content: str) -> str:
    soup = BeautifulSoup(html_content, 'html.parser')
    for elem in soup([
        'script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript',
        'button', 'form', 'svg', 'iframe', 'head'
    ]):
        elem.extract()
    for cl in [
        'file-navigation', 'repohead', 'pagehead', 'site-header', 'site-footer',
        'breadcrumbs', 'breadcrumb', 'Box-header', 'flash', 'sr-only', 'btn'
    ]:
        for tag in soup.find_all(class_=cl):
            tag.extract()
    text = soup.get_text(separator=' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class SourceDiscoveryEngine:
    """
    Discovers relevant public information from free public feeds, APIs,
    and articles without requiring any paid API keys.
    """

    def __init__(self, max_sources: int = 8):
        self.max_sources = max_sources

    def discover(self, query: str) -> list[dict]:
        """
        Gathers sources from multiple free public channels based on the research query.
        Returns a list of deduplicated raw source dicts:
        [{
            'title': str,
            'url': str,
            'source_name': str,
            'excerpt': str,
            'publication_date': datetime | None,
            'content_hash': str
        }]
        """
        discovered = []
        seen_urls = set()

        # Channel 1: Free Public Wikipedia Search & Full Extract (Foundation & Primer)
        wiki_sources = self._search_wikipedia(query)
        for s in wiki_sources:
            if s['url'] not in seen_urls:
                seen_urls.add(s['url'])
                discovered.append(s)

        # Channel 2: Free Algolia Hacker News Search API (free, open, no auth)
        if len(discovered) < self.max_sources:
            hn_sources = self._search_hackernews(query)
            for s in hn_sources:
                if s['url'] not in seen_urls:
                    seen_urls.add(s['url'])
                    discovered.append(s)

        # Channel 3: Free ArXiv Public API if relevant to science/tech/AI
        if len(discovered) < self.max_sources:
            arxiv_sources = self._search_arxiv(query)
            for s in arxiv_sources:
                if s['url'] not in seen_urls:
                    seen_urls.add(s['url'])
                    discovered.append(s)

        # Channel 4: Public Tech & Industry RSS Feeds
        if len(discovered) < self.max_sources:
            rss_sources = self._search_public_feeds(query)
            for s in rss_sources:
                if s['url'] not in seen_urls:
                    seen_urls.add(s['url'])
                    discovered.append(s)

        return discovered[:self.max_sources]

    def _search_wikipedia(self, query: str) -> list[dict]:
        results = []
        try:
            cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', query).strip()
            stop_words = {'what', 'is', 'the', 'how', 'does', 'investigate', 'track', 'why', 'who', 'and', 'or', 'in', 'of', 'for', 'about'}
            keywords = [w for w in cleaned.split() if w.lower() not in stop_words]
            term = " ".join(keywords[:3]) if keywords else cleaned
            if not term:
                return results

            encoded = urllib.parse.quote_plus(term)
            # Step 1: Use Wikipedia search to identify the most accurate articles
            search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json"
            res = safe_fetch_url(search_url, timeout=5.0)
            if res['status_code'] == 200:
                import json
                data = json.loads(res['content'])
                search_items = data.get('query', {}).get('search', [])[:2]

                for item in search_items:
                    page_title = item.get('title')
                    if not page_title:
                        continue

                    # Step 2: Fetch the full multi-section extract for this page
                    extract_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={urllib.parse.quote(page_title)}&format=json"
                    e_res = safe_fetch_url(extract_url, timeout=5.0)
                    if e_res['status_code'] == 200:
                        e_data = json.loads(e_res['content'])
                        pages = e_data.get('query', {}).get('pages', {})
                        if pages:
                            page_obj = list(pages.values())[0]
                            full_extract = page_obj.get('extract', '')
                            if full_extract and len(full_extract) > 100:
                                # Clean out raw wiki header markers like == Background ==
                                clean_extract = re.sub(r'==+\s*([^=]+)\s*==+', r'\1.', full_extract)
                                clean_extract = re.sub(r'\s+', ' ', clean_extract).strip()
                                page_link = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(page_title.replace(' ', '_'))}"
                                results.append({
                                    'title': f"{page_title}: Comprehensive Architectural Overview",
                                    'url': page_link,
                                    'source_name': "Wikipedia Open Knowledge Repository",
                                    'excerpt': clean_extract[:5000],
                                    'publication_date': None,
                                    'content_hash': compute_content_hash(clean_extract[:5000])
                                })
        except Exception as e:
            logger.warning(f"Wikipedia search failed: {e}")
        return results

    def _search_hackernews(self, query: str) -> list[dict]:
        results = []
        try:
            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://hn.algolia.com/api/v1/search?query={encoded_query}&tags=story&hitsPerPage=6"
            res = safe_fetch_url(url, timeout=6.0)
            if res['status_code'] == 200:
                import json
                data = json.loads(res['content'])
                hits = data.get('hits', [])
                for hit in hits:
                    target_url = hit.get('url')
                    title = hit.get('title')
                    if not target_url or not title:
                        continue
                    # Parse publication date
                    created_at_str = hit.get('created_at')
                    pub_date = None
                    if created_at_str:
                        try:
                            pub_date = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        except Exception:
                            pass

                    # Fetch excerpt / content if possible
                    excerpt = self._extract_article_content(target_url) or hit.get('story_text') or title
                    chash = compute_content_hash(excerpt or title)

                    domain = urllib.parse.urlparse(target_url).netloc
                    source_name = domain.replace('www.', '') if domain else "Hacker News Story"

                    results.append({
                        'title': title[:500],
                        'url': target_url[:1000],
                        'source_name': source_name[:250],
                        'excerpt': excerpt[:2000],
                        'publication_date': pub_date,
                        'content_hash': chash
                    })
        except Exception as e:
            logger.warning(f"Failed HackerNews search: {e}")
        return results

    def _search_arxiv(self, query: str) -> list[dict]:
        results = []
        try:
            cleaned_query = re.sub(r'[^a-zA-Z0-9\s]', '', query).strip()
            stop_words = {'investigate', 'what', 'is', 'the', 'how', 'does', 'why', 'who', 'and', 'or', 'in', 'of', 'for', 'about', 'track', 'compare', 'to'}
            meaningful_terms = [w for w in cleaned_query.split() if w.lower() not in stop_words]
            search_term = " ".join(meaningful_terms[:2]) if meaningful_terms else "AI"
            url = f"https://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote_plus(search_term)}&start=0&max_results=3"
            res = safe_fetch_url(url, timeout=6.0)
            if res['status_code'] == 200:
                parsed = feedparser.parse(res['content'])
                for entry in parsed.entries:
                    link = entry.get('link', '')
                    title = entry.get('title', '').replace('\n', ' ').strip()
                    summary = entry.get('summary', '').replace('\n', ' ').strip()
                    if not link or not title:
                        continue
                    pub_date = None
                    if entry.get('published_parsed'):
                        try:
                            pub_date = datetime(*entry.published_parsed[:6])
                        except Exception:
                            pass

                    results.append({
                        'title': title[:500],
                        'url': link[:1000],
                        'source_name': 'arXiv Pre-print Archive',
                        'excerpt': summary[:2000],
                        'publication_date': pub_date,
                        'content_hash': compute_content_hash(summary or title)
                    })
        except Exception as e:
            logger.warning(f"Failed arXiv search: {e}")
        return results

    def _search_public_feeds(self, query: str) -> list[dict]:
        """Scans curated public technology RSS feeds for matching keywords."""
        feeds = [
            ('Ars Technica', 'https://feeds.arstechnica.com/arstechnica/index'),
            ('TechCrunch', 'https://techcrunch.com/feed/'),
        ]
        results = []
        query_words = set(query.lower().split())

        for source_name, feed_url in feeds:
            try:
                res = safe_fetch_url(feed_url, timeout=5.0)
                if res['status_code'] == 200:
                    parsed = feedparser.parse(res['content'])
                    for entry in parsed.entries:
                        title = entry.get('title', '')
                        summary = entry.get('summary', '') or entry.get('description', '')
                        combined = f"{title} {summary}".lower()

                        # Check relevance
                        if any(w in combined for w in query_words if len(w) > 3) or not query_words:
                            link = entry.get('link', '')
                            if not link:
                                continue
                            clean_summary = clean_html_text(summary)
                            results.append({
                                'title': title[:500],
                                'url': link[:1000],
                                'source_name': source_name,
                                'excerpt': clean_summary[:2000] or title,
                                'publication_date': None,
                                'content_hash': compute_content_hash(clean_summary or title)
                            })
                            if len(results) >= 3:
                                break
            except Exception as e:
                logger.warning(f"Failed RSS feed search {feed_url}: {e}")
        return results

    def _extract_article_content(self, url: str) -> str | None:
        """Attempts safe HTTP fetch and text extraction for an individual article."""
        try:
            res = safe_fetch_url(url, timeout=5.0)
            if res['status_code'] == 200:
                text = clean_html_text(res['content'])
                return text[:2500]
        except (SSRFValidationError, Exception) as e:
            logger.debug(f"Article fetch bypassed for {url}: {e}")
        return None
