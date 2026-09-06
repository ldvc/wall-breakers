import re

import requests
from bs4 import BeautifulSoup

from .common import Article, add_figure, fix_links, make_figcaption

_URL_ID_PATTERN = re.compile(
    r"https?:\/\/www\.nature\.com\/articles\/(d41586-\d{3}-\d{5}-[0-9a-z])"
)


def _meta(soup, **attrs):
    tag = soup.find("meta", attrs=attrs)
    return tag.get("content") if tag else None


def _rebuild_figure(figure):
    img = figure.find("img")
    if img is None:
        figure.decompose()
        return

    src = img.get("src", "")
    if src.startswith("//"):
        src = "https:" + src

    spans = figure.select("figcaption span")
    caption = spans[0].get_text(strip=True) if len(spans) > 0 else ""
    credit = spans[1].get_text(strip=True) if len(spans) > 1 else ""
    credit = credit.removeprefix("Credit: ")

    figcaption = make_figcaption(caption or None, credit or None)
    figure.replace_with(BeautifulSoup(add_figure(src, figcaption), features="html.parser"))


def _sanitize(soup):
    for junk in soup.select("script, article.recommended, div[data-test='access-wall']"):
        junk.decompose()

    for sup in soup.find_all("sup"):
        link = sup.find("a", href=True)
        if (link and link["href"].startswith("#")) or sup.get_text(strip=True) in (",", ";"):
            sup.decompose()

    for figure in soup.find_all("figure"):
        _rebuild_figure(figure)

    for tag in soup.find_all():
        if (
            not tag.get_text(strip=True)
            and not tag.find()
            and tag.name not in ["img", "br", "hr", "input"]
        ):
            tag.decompose()

    for tag in soup.find_all():
        tag.attrs = {
            key: value
            for key, value in tag.attrs.items()
            if key in ("href", "src", "srcset", "fetchpriority", "alt", "aria-label",)
        }

    fix_links(soup)

    return soup.decode_contents()


class NatureArticle(Article):
    SLUG = "nat"
    PROVIDER = "Nature"
    FAVICON = "https://www.nature.com/oscar-static/images/favicons/nature/apple-touch-icon-f39cb19454.png"

    def __init__(self, article_id: str):
        soup = BeautifulSoup(NatureArticle.get_data(article_id), features="html.parser")

        body = soup.find("div", class_="c-article-body")
        if body is None:
            raise NotImplementedError("Article body is behind a subscription paywall")

        teaser = body.find("div", attrs={"data-test": "access-teaser"})
        content = _sanitize(teaser or body)

        headline = soup.find("h1", class_="c-article-magazine-title")
        teaser_text = soup.find(class_="c-article-teaser-text")

        super().__init__(
            id=article_id,
            headline=headline.get_text(strip=True) if headline else _meta(soup, name="dc.title"),
            subheadline=teaser_text.get_text(" ", strip=True) if teaser_text else (_meta(soup, name="dc.description") or ""),
            content=content,
            url=f"https://www.nature.com/articles/{article_id}",
            image=_meta(soup, property="og:image"),
        )

    def get_id_from_url(url: str):
        match = _URL_ID_PATTERN.search(url)
        if match is None:
            return None

        return match.group(1)

    def get_data(id):
        r = requests.get(f"https://www.nature.com/articles/{id}")
        r.raise_for_status()

        return r.content


if __name__ == "__main__":
    article = NatureArticle.get_from_url("https://www.nature.com/articles/d41586-026-02764-2")

    print(article)
