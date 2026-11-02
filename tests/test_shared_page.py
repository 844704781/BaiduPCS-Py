import json
import unittest
from unittest.mock import Mock

import requests

from baidupcs_py.baidupcs import BaiduPCS, BaiduPCSApi, BaiduPCSError
from baidupcs_py.baidupcs.errors import BaiduPCSShareParseError, assert_ok
from baidupcs_py.baidupcs.share import parse_shared_page


SHARE = {"errno": 0, "shareid": 123, "share_uk": "456", "bdstoken": "test-token", "file_list": []}


class SharedPageTest(unittest.TestCase):
    def test_legacy_initializers_and_multiline_strings(self):
        data = dict(SHARE, description='a ); string with a quote " and Chinese 中文')
        for name in ("yunData.setData", "locals.mset"):
            for indent in (None, 2):
                with self.subTest(name=name, indent=indent):
                    html = "<script>" + name + " (\n" + json.dumps(data, indent=indent) + ");</script>"
                    self.assertEqual(parse_shared_page(html), data)

    def test_json_script_attributes_and_unrelated_scripts(self):
        html = '<script type="application/json">{"analytics":true}</script>'
        html += "<script id='share-data' TYPE='application/json' nonce='test'>\n"
        html += json.dumps(SHARE, indent=2) + "\n</script>"
        self.assertEqual(parse_shared_page(html), SHARE)

    def test_modern_metadata_precedes_legacy_error_placeholder(self):
        html = '<script>locals.mset({"errno":145});</script>'
        html += '<script type="application/json">' + json.dumps(SHARE) + '</script>'
        self.assertEqual(parse_shared_page(html), SHARE)

    def test_unrelated_and_malformed_json_does_not_mask_legacy(self):
        for content in ('{"analytics":true}', '[1, 2]', '{invalid', '{"errno":0}'):
            html = '<script type="application/json">' + content + '</script>'
            html += '<script>locals.mset(' + json.dumps(SHARE) + ');</script>'
            self.assertEqual(parse_shared_page(html), SHARE)

    def test_no_page_data_has_safe_typed_error(self):
        for html in ('<html>login</html>', '<script type="application/json">{bad}</script>',
                     '<script>locals.mset({"XDUSS":"secret" broken});</script>',
                     '<p>locals.mset({"errno":0});</p>'):
            with self.subTest(html=html), self.assertRaises(BaiduPCSShareParseError) as ctx:
                parse_shared_page(html)
            self.assertIsNone(ctx.exception.error_code)
            self.assertNotIn('secret', str(ctx.exception))

    def test_error_only_modern_page_preserves_errno(self):
        self.assertEqual(parse_shared_page('<script type="application/json">{"errno":145}</script>'),
                         {'errno': 145})

    def client(self, html, status=200):
        pcs = BaiduPCS.__new__(BaiduPCS)
        pcs._stoken = 'test-stoken'
        pcs._cookies_update = Mock()
        response = requests.Response()
        response.status_code = status
        response.encoding = 'utf-8'
        response._content = html.encode('utf-8')
        response.cookies.set('BDCLND', 'test-share-cookie')
        pcs._request = Mock(return_value=response)
        return pcs

    def test_real_sdk_method_updates_share_cookies(self):
        pcs = self.client('<script type="application/json">' + json.dumps(SHARE) + '</script>')
        api = BaiduPCSApi.__new__(BaiduPCSApi)
        api._baidupcs = pcs
        self.assertEqual(api.shared_paths('https://pan.baidu.com/s/1test'), [])
        pcs._cookies_update.assert_called_once_with({'BDCLND': 'test-share-cookie'})

    def test_http_error_is_not_reclassified_as_parse_error(self):
        pcs = self.client('<html>blocked</html>', 403)
        with self.assertRaises(requests.HTTPError) as ctx:
            pcs.shared_paths('https://pan.baidu.com/s/1test')
        self.assertEqual(ctx.exception.response.status_code, 403)

    def test_public_api_returns_files_with_transfer_metadata(self):
        file = {'fs_id': 789, 'path': '/测试.mp4', 'size': 1024, 'isdir': 0}
        for listing in ([file], {'list': [file]}):
            with self.subTest(listing=listing):
                data = dict(SHARE, file_list=listing)
                pcs = self.client('<script type="application/json">' + json.dumps(data) + '</script>')
                api = BaiduPCSApi.__new__(BaiduPCSApi)
                api._baidupcs = pcs
                paths = api.shared_paths('https://pan.baidu.com/s/1test')
                self.assertEqual(len(paths), 1)
                self.assertEqual((paths[0].fs_id, paths[0].path, paths[0].size), (789, '/测试.mp4', 1024))
                self.assertEqual((paths[0].uk, paths[0].share_id, paths[0].bdstoken), (456, 123, 'test-token'))

    def test_real_baidu_errors_remain_errors_and_never_include_credentials(self):
        for code in (117, 145, -6, 999999):
            for modern in (True, False):
                with self.subTest(code=code, modern=modern):
                    data = dict(SHARE, errno=code, XDUSS='private-xduss', bdstoken='private-token')
                    html = ('<script type="application/json">' + json.dumps(data) + '</script>' if modern
                            else '<script>locals.mset(' + json.dumps(data) + ');</script>')
                    with self.assertRaises(BaiduPCSError) as ctx:
                        self.client(html).shared_paths('https://pan.baidu.com/s/1test')
                    self.assertEqual(ctx.exception.error_code, code)
                    self.assertEqual(ctx.exception.api, 'shared_paths')
                    self.assertNotIn('private-', str(ctx.exception))

    def test_generic_api_error_does_not_include_unknown_response(self):
        @assert_ok
        def sample():
            return {'error_code': 145, 'XDUSS': 'private-xduss', 'csrf': 'private-csrf'}
        with self.assertRaises(BaiduPCSError) as ctx:
            sample()
        self.assertEqual(ctx.exception.error_code, 145)
        self.assertNotIn('private-', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
