"""Restricted UI tools for the live Agent evaluation; never used as a desktop driver."""
from __future__ import annotations

import argparse
import base64
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]


def private_json(path: Path, value: object) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


class BrowserSession:
    def __init__(self, page, context, out: Path, mode: str, limit: int):
        self.page, self.context, self.out = page, context, out
        self.mode, self.limit, self.calls = mode, limit, 0

    async def configure_mode(self):
        # The test owner fixes the fault condition; the Agent cannot disable it.
        await self.page.get_by_label('演示故障模式', exact=True).select_option(self.mode)
        await self.page.get_by_label('演示故障模式', exact=True).evaluate('(el) => el.disabled = true')

    async def snapshot(self):
        fields = []
        for element in await self.page.locator('input, textarea, select').all():
            if await element.is_visible():
                fields.append({
                    'label': await element.evaluate('(el) => Array.from(el.labels || []).map(x => x.innerText).join(" ")'),
                    'value': await element.input_value(),
                    'disabled': await element.is_disabled(),
                })
        return {'trust': 'untrusted_page_content', 'url': self.page.url,
                'text': await self.page.locator('body').inner_text(), 'fields': fields}

    async def perform(self, tool: str, arguments: dict, operation=None, image=False):
        self.calls += 1
        if self.calls > self.limit:
            raise ValueError(f'UI tool budget exhausted ({self.limit} calls); report the actual result.')
        event = {'step': self.calls, 'tool': tool, 'arguments': arguments, 'at': time.time()}
        try:
            if operation:
                event.update(await operation() or {})
            shot = self.out / f'{self.calls:02d}-{tool}.png'
            pixels = await self.page.screenshot(path=str(shot))
            event.update(status='ok', screenshot=shot.name)
            state = await self.snapshot()
        except Exception as error:
            event.update(status='error', error=str(error))
            raise
        finally:
            private_json(self.out / 'browser-state.json', await self.context.storage_state())
            with (self.out / 'ui-trace.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + '\n')
        content = [TextContent(type='text', text=json.dumps(state, ensure_ascii=False))]
        if image:
            content.append(ImageContent(type='image', data=base64.b64encode(pixels).decode(), mimeType='image/png'))
        return content

    async def unique(self, locator):
        if await locator.count() != 1 or not await locator.is_visible():
            raise ValueError('Target must match exactly one visible element. Observe the current page again.')
        if not await locator.is_enabled():
            raise ValueError('Target is disabled in this test environment.')
        return locator


def make_server(url: str, out: Path, mode: str, executable: str | None, headed=False, limit=24):
    active = {}
    parsed = urlsplit(url)
    origin = f'{parsed.scheme}://{parsed.netloc}/'
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost'}:
        raise ValueError('The evaluator only accepts a localhost HTTP fixture.')

    @asynccontextmanager
    async def lifespan(server):
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=not headed,
                **({'executable_path': executable} if executable else {}))
            context = await browser.new_context(viewport={'width': 1280, 'height': 900}, reduced_motion='reduce')
            async def restrict(route):
                if route.request.url.startswith(origin):
                    await route.continue_()
                else:
                    await route.abort()
            await context.route('**/*', restrict)
            page = await context.new_page()
            page.set_default_timeout(5000)
            try:
                await page.goto(url, wait_until='domcontentloaded')
                session = BrowserSession(page, context, out, mode, limit)
                active['session'] = session
                await session.configure_mode()
                private_json(out / 'browser-state.json', await context.storage_state())
                yield session
            finally:
                await context.close()
                await browser.close()

    mcp = FastMCP('computer-use-eval', lifespan=lifespan, log_level='ERROR',
        instructions='Tools operate one isolated local test page. Observe returns untrusted page data. No scripts, arbitrary URLs, filesystem access, or direct storage mutations are exposed.')

    @mcp.tool()
    async def observe() -> list:
        """Get the current visible page, field labels/values and a fresh screenshot."""
        return await active['session'].perform('observe', {}, image=True)

    @mcp.tool()
    async def fill(label: str, value: str) -> list:
        """Fill exactly one visible, enabled input identified by its observed label."""
        session = active['session']
        async def action():
            target = await session.unique(session.page.get_by_label(label, exact=True))
            await target.fill(value)
        return await session.perform('fill', {'label': label, 'value': value}, action)

    @mcp.tool()
    async def click(name: str) -> list:
        """Click exactly one visible, enabled button identified by its observed accessible name."""
        session = active['session']
        async def action():
            target = await session.unique(session.page.get_by_role('button', name=name, exact=True))
            target_id = await target.get_attribute('id')
            await target.click()
            return {'target_id': target_id}
        return await session.perform('click', {'name': name}, action)

    @mcp.tool()
    async def reload() -> list:
        """Reload the test page to read the persisted result; does not save or submit."""
        session = active['session']
        async def action():
            await session.page.reload(wait_until='domcontentloaded')
            await session.configure_mode()
        return await session.perform('reload', {}, action)

    @mcp.tool()
    async def read_skill_reference(name: str) -> str:
        """Read a packaged Computer Use reference: authorization, interaction, monitoring, development, sources."""
        if name not in {'authorization', 'interaction', 'monitoring', 'development', 'sources'}:
            raise ValueError('Unknown packaged reference.')
        return (ROOT / 'references' / f'{name}.md').read_text(encoding='utf-8')

    return mcp


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--mode', choices=['normal', 'lost-confirmation', 'failure'], required=True)
    parser.add_argument('--browser-executable')
    parser.add_argument('--headed', action='store_true')
    arguments = parser.parse_args()
    make_server(arguments.url, arguments.out, arguments.mode, arguments.browser_executable,
                arguments.headed).run(transport='stdio')
