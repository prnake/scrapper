
import datetime

# noinspection PyPackageRequirements
from playwright.sync_api import sync_playwright

from scrapper.cache import dump_result
from scrapper.settings import IN_DOCKER, READABILITY_SCRIPT, PARSER_SCRIPTS_DIR
from scrapper.parser import new_context, close_context, page_processing
from scrapper.util import check_fields
from scrapper.parser import ParserError


def parse(request, args, _id):
    with sync_playwright() as playwright:
        context = new_context(playwright, args)
        page = context.new_page()
        page_content, screenshot = page_processing(page, args=args, init_scripts=[READABILITY_SCRIPT])

        # evaluating JavaScript: parse DOM and extract article content
        parser_args = {
            # Readability options:
            'maxElemsToParse': args.max_elems_to_parse,
            'nbTopCandidates': args.nb_top_candidates,
            'charThreshold': args.char_threshold,
        }
        with open(PARSER_SCRIPTS_DIR / 'article.js') as fd:
            article = page.evaluate(fd.read() % parser_args)
        close_context(context)

    # parser error: article is not extracted, result has 'err' field
    if 'err' in article:
        raise ParserError(article)

    # set common fields
    article['id'] = _id
    article['date'] = datetime.datetime.utcnow().isoformat()  # ISO 8601 format
    article['resultUri'] = f'{request.host_url}result/{_id}'
    article['query'] = request.args.to_dict(flat=True)

    if args.full_content:
        article['fullContent'] = page_content
    if args.screenshot:
        article['screenshotUri'] = f'{request.host_url}screenshot/{_id}'

    # save result to disk
    dump_result(article, filename=_id, screenshot=screenshot)

    # self-check for development
    if not IN_DOCKER:
        check_fields(article, args=args, fields=ARTICLE_FIELDS)
    return article


NoneType = type(None)
ARTICLE_FIELDS = (
    # (name, types, condition)

    # author metadata
    ('byline', (NoneType, str), None),
    # HTML string of processed article content
    ('content', (NoneType, str), None),
    # content direction
    ('dir', (NoneType, str), None),
    # article description, or short excerpt from the content
    ('excerpt', (NoneType, str), None),
    # full HTML contents of the page
    ('fullContent', str, lambda args: args.full_content),
    # unique request ID
    ('id', str, None),
    # content language
    ('lang', (NoneType, str), None),
    # length of an article, in characters
    ('length', (NoneType, int), None),
    # date of extracted article in ISO 8601 format
    ('date', str, None),
    # request parameters
    ('query', dict, None),
    # URL of the current result, the data here is always taken from cache
    ('resultUri', str, None),
    # URL of the screenshot of the page
    ('screenshotUri', str, lambda args: args.screenshot),
    # name of the site
    ('siteName', (NoneType, str), None),
    # text content of the article, with all the HTML tags removed
    ('textContent', (NoneType, str), None),
    # article title
    ('title', (NoneType, str), None),
)
