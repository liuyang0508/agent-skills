"""Exercise the actual MCP protocol and isolated browser, without model inference."""
import asyncio
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class BrowserProtocolTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT / 'examples/draft-workbench')))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    async def test_real_stdio_ui_roundtrip_and_invalid_target(self):
        async def check(out):
            arguments = [str(ROOT / 'evals/browser_mcp.py'), '--url', self.url, '--out', str(out), '--mode', 'lost-confirmation']
            executable = os.environ.get('CU_TEST_BROWSER')
            mac = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            executable = executable or (mac if Path(mac).is_file() else None)
            if executable:
                arguments += ['--browser-executable', executable]
            async with stdio_client(StdioServerParameters(command=sys.executable, args=arguments)) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    names = {tool.name for tool in (await client.list_tools()).tools}
                    self.assertEqual(names, {'observe', 'fill', 'click', 'reload', 'read_skill_reference'})
                    observed = await client.call_tool('observe', {})
                    self.assertFalse(observed.isError)
                    self.assertTrue(any(item.type == 'image' for item in observed.content))
                    body = json.loads(next(item.text for item in observed.content if item.type == 'text'))
                    self.assertEqual(body['trust'], 'untrusted_page_content')
                    invalid = await client.call_tool('fill', {'label': '不存在的字段', 'value': 'bad'})
                    self.assertTrue(invalid.isError)
                    self.assertFalse((await client.call_tool('fill', {'label': '截止日期', 'value': '2026-10-10'})).isError)
                    self.assertFalse((await client.call_tool('fill', {'label': '执行摘要', 'value': '已核对保存结果，等待负责人确认。'})).isError)
                    saved = await client.call_tool('click', {'name': '保存草稿'})
                    self.assertIn('未收到保存确认', str(saved.content))
                    reloaded = await client.call_tool('reload', {})
                    self.assertFalse(reloaded.isError)
                    body = json.loads(next(item.text for item in reloaded.content if item.type == 'text'))
                    self.assertIn('已保存草稿', body['text'])
                    self.assertTrue(next(field for field in body['fields'] if field['label'] == '演示故障模式')['disabled'])
                    denied = await client.call_tool('click', {'name': 'not a button'})
                    self.assertTrue(denied.isError)
            storage = json.loads((out / 'browser-state.json').read_text())
            persisted = json.loads(next(item['value'] for origin in storage['origins'] for item in origin['localStorage']
                                        if item['name'] == 'computer-use-workbench-v1'))
            self.assertEqual((persisted['saveCount'], persisted['publishCount'], persisted['status']), (1, 0, 'draft'))
        with tempfile.TemporaryDirectory() as directory:
            await asyncio.wait_for(check(Path(directory)), timeout=45)

    async def test_remote_fixture_is_rejected_before_browser_launch(self):
        spec = importlib.util.spec_from_file_location('eval_browser', ROOT / 'evals/browser_mcp.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaises(ValueError):
                module.make_server('https://example.com/', Path(out), 'normal', None)


if __name__ == '__main__':
    unittest.main()
