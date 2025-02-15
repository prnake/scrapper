import asyncio
import datetime
from typing import Annotated

import tldextract
import validators

from fastapi import APIRouter, Query, Depends, status
from fastapi.requests import Request
from fastapi.exceptions import HTTPException
from pydantic import BaseModel
from playwright.async_api import Browser

from settings import READABILITY_SCRIPT, PARSER_SCRIPTS_DIR
from internal import cache
from internal.browser import (
    new_context,
    page_processing,
    get_screenshot,
)
from internal.util import htmlutil, split_url
from .query_params import (
    query_parsing_error,
    CommonQueryParams,
    BrowserQueryParams,
    ProxyQueryParams,
    ReadabilityQueryParams,
)
import traceback


router = APIRouter(prefix='/api/article', tags=['article'])


class Article(BaseModel):
    byline: Annotated[str | None, Query(description='author metadata')]
    content: Annotated[str | None, Query(description='HTML string of processed article content')]
    dir: Annotated[str | None, Query(description='content direction')]
    excerpt: Annotated[str | None, Query(description='article description, or short excerpt from the content')]
    id: Annotated[str, Query(description='unique result ID')]
    url: Annotated[str, Query(description='page URL after redirects, may not match the query URL')]
    domain: Annotated[str, Query(description="page's registered domain")]
    lang: Annotated[str | None, Query(description='content language')]
    length: Annotated[int | None, Query(description='length of extracted article, in characters')]
    date: Annotated[str, Query(description='date of extracted article in ISO 8601 format')]
    query: Annotated[dict, Query(description='request parameters')]
    meta: Annotated[dict, Query(description='social meta tags (open graph, twitter)')]
    resultUri: Annotated[str, Query(description='URL of the current result, the data here is always taken from cache')]
    html: Annotated[str | None, Query(description='full HTML contents of the page')] = None
    screenshotUri: Annotated[str | None, Query(description='URL of the screenshot of the page')] = None
    siteName: Annotated[str | None, Query(description='name of the site')]
    textContent: Annotated[str | None, Query(description='text content of the article, with all the HTML tags removed')]
    title: Annotated[str | None, Query(description='article title')]
    publishedTime: Annotated[str | None, Query(description='article publication time')]


class URLParam:
    def __init__(
        self,
        url: Annotated[
            str,
            Query(
                description='Page URL. The page should contain the text of the article that needs to be extracted.<br><br>',
                examples=['http://example.com/article.html'],
            ),
        ],
    ):
        if validators.url(url) is not True:
            raise query_parsing_error('url', 'Invalid URL', url)
        self.url = url


@router.get('')
async def parse_article(
    request: Request,
    url: Annotated[URLParam, Depends()],
    common_params: Annotated[CommonQueryParams, Depends()],
    browser_params: Annotated[BrowserQueryParams, Depends()],
    proxy_params: Annotated[ProxyQueryParams, Depends()],
    readability_params: Annotated[ReadabilityQueryParams, Depends()],
) -> Article:
    # pylint: disable=duplicate-code
    # split URL into parts: host with scheme, path with query, query params as a dict
    host_url, full_path, query_dict = split_url(request.url)

    # get cache data if exists
    r_id = cache.make_key(full_path)  # unique result ID
    if common_params.cache:
        data = cache.load_result(key=r_id)
        if data:
            return data

    browser: Browser = request.state.browser
    semaphore: asyncio.Semaphore = request.state.semaphore

    async def browser_fetch(context):
        try:
            page = await context.new_page()
            page_timeout = await page_processing(
                page=page,
                url=url.url,
                params=common_params,
                browser_params=browser_params,
            )
            page_content = await page.content()
            page_url = page.url
            return page_content, page_url, page_timeout
        except Exception as e:
            traceback.print_exc()
        return None, None
    
    page_content = None

    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=0.5)
        async with new_context(browser, browser_params, proxy_params) as context:
            try:
                page_content, page_url, page_timeout = await asyncio.wait_for(browser_fetch(context), timeout=30)
            except:
                traceback.print_exc()
        semaphore.release()
    except:
        raise article_parsing_error(url.url, "no page content")
    
    if not page_content:
        raise article_parsing_error(url.url, "no page content")

            # # evaluating JavaScript: parse DOM and extract article content
            # parser_args = {
            #     # Readability options:
            #     'maxElemsToParse': readability_params.max_elems_to_parse,
            #     'nbTopCandidates': readability_params.nb_top_candidates,
            #     'charThreshold': readability_params.char_threshold,
            # }
            # with open(PARSER_SCRIPTS_DIR / 'article.js', encoding='utf-8') as fd:
            #     article = await page.evaluate(fd.read() % parser_args)

    # if article is None:
    #     raise article_parsing_error(page_url, "The page doesn't contain any articles.")

    # # parser error: article is not extracted, result has 'err' field
    # if 'err' in article:
    #     raise article_parsing_error(page_url, article['err'])

    # set common fields
    article = {'byline': '', 'content': '', 'dir': '', 'excerpt': '', 'id': '', 'url': '', 'domain': '', 'lang': '', 'length': 0, 'date': '', 'query': {}, 'meta': {}, 'resultUri': '', 'html': '', 'screenshotUri': None, 'siteName': '', 'textContent': '', 'title': '', 'publishedTime': ''}
    article['id'] = r_id
    article['url'] = page_url
    article['domain'] = tldextract.extract(page_url).registered_domain
    article['date'] = datetime.datetime.utcnow().isoformat()  # ISO 8601 format
    article['resultUri'] = f'{host_url}/result/{r_id}'
    article['query'] = query_dict
    article['meta'] = htmlutil.social_meta_tags(page_content)

    if common_params.full_content:
        article['html'] = page_content
    if common_params.screenshot:
        article['screenshotUri'] = f'{host_url}/screenshot/{r_id}'

    # if 'title' in article and 'content' in article:
    #     article['content'] = htmlutil.improve_content(
    #         title=article['title'],
    #         content=article['content'],
    #     )

    # save result to disk
    if not page_timeout:
        cache.dump_result(article, key=r_id, screenshot=None)
    return Article(**article)


def article_parsing_error(url: str, msg: str) -> HTTPException:  # pragma: no cover
    obj = {
        'type': 'article_parsing',
        'loc': ('readability.js',),
        'msg': msg,
        'input': url,
    }
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=[obj]
    )
