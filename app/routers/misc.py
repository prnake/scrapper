import datetime
from typing import Annotated

from fastapi import APIRouter, Query, HTTPException
from fastapi.requests import Request
from pydantic import BaseModel
from playwright.async_api import Browser

from version import revision
from settings import BROWSER_CONTEXT_LIMIT


router = APIRouter(tags=['misc'])


class PingData(BaseModel):
    browserType: Annotated[str, Query(description='the browser type (chromium, firefox or webkit)')]
    browserVersion: Annotated[str, Query(description='the browser version')]
    contexts: Annotated[int, Query(description='number of active browser contexts')]
    isConnected: Annotated[bool, Query(description='indicates that the browser is connected')]
    now: Annotated[datetime.datetime, Query(description='UTC time now')]
    revision: Annotated[str, Query(description='the scrapper revision')]


@router.get('/ping')
async def ping(request: Request) -> PingData:
    browser: Browser = request.state.browser
    r = {
        'browserType': browser.browser_type.name,
        'browserVersion': browser.version,
        'contexts': len(browser.contexts),
        'isConnected': browser.is_connected(),
        'now': datetime.datetime.utcnow(),
        'revision': revision,
    }

    # if r["contexts"] >= int(BROWSER_CONTEXT_LIMIT):
    #     raise HTTPException(status_code=500, detail="Too many active browser contexts")
    # if not r["isConnected"]:
    #     raise HTTPException(status_code=500, detail="Browser disconnected")
    
    return PingData(**r)
