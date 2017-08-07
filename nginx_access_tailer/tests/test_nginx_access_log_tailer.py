"""Tests for NginxAccessLogTailer and supporting bits.

TODO(swfrench): Add test for SimpleTailer.
"""

import unittest

import mock

from nginx_access_tailer import NginxAccessLogTailer


class SleepExit(Exception):
    """Exception used to exit the wait loop via side-effect."""
    pass


class TestNginxAccessLogTailer(unittest.TestCase):
    """Tests for NginxAccessLogTailer."""

    @mock.patch('nginx_access_tailer.nginx_access_log_tailer.SimpleTailer')
    @mock.patch('time.time')
    @mock.patch('time.sleep')
    def test_basic_logging(self, mock_sleep, mock_time, mock_simple_tailer):
        """Ensure basic logging / parsing functionality."""
        mock_simple_tailer_instance = mock_simple_tailer.return_value
        mock_simple_tailer_instance.get_lines.side_effect = [
            [
                '1.2.3.4 - - [07/Aug/2017:00:00:00 +0000] ' +
                '"GET / HTTP/1.1" 200 1105 "-" "SomeClient"',
                '2.3.4.5 - - [07/Aug/2017:00:00:01 +0000] ' +
                '"GET / HTTP/1.1" 500 1105 "-" "SomeClient"',
            ],
            [
                '1.2.3.4 - - [07/Aug/2017:00:00:02 +0000] ' +
                '"GET / HTTP/1.1" 200 1105 "-" "SomeClient"',
                '2.3.4.5 - - [07/Aug/2017:00:00:03 +0000] ' +
                '"GET / HTTP/1.1" 403 1105 "-" "SomeClient"',
            ],
            [],
        ]

        mock_consumer = mock.MagicMock(name='Consumer')

        tailer = NginxAccessLogTailer('log_file', mock_consumer, 3, 1)

        mock_simple_tailer.assert_called_once_with(
            'log_file',
            rotation_check_idle_time_s=3,
            rotation_check_period_s=1)

        mock_time.return_value = 0

        # Hack to break out of the watch loop after a bounded number of passes
        mock_sleep.side_effect = [None, None, SleepExit()]
        try:
            tailer.watch(30)
        except SleepExit:
            pass

        self.assertEqual(mock_simple_tailer_instance.get_lines.call_count, 3)
        mock_sleep.assert_has_calls(
            [mock.call(30), mock.call(30),
             mock.call(30)])
        self.assertEqual(mock_consumer.record.call_count, 4)
        mock_consumer.record.assert_has_calls([
            mock.call({
                'ipaddress': '1.2.3.4',
                'datetime': '07/Aug/2017:00:00:00 +0000',
                'url': '/',
                'statuscode': '200'
            }),
            mock.call({
                'ipaddress': '2.3.4.5',
                'datetime': '07/Aug/2017:00:00:01 +0000',
                'url': '/',
                'statuscode': '500'
            }),
            mock.call({
                'ipaddress': '1.2.3.4',
                'datetime': '07/Aug/2017:00:00:02 +0000',
                'url': '/',
                'statuscode': '200'
            }),
            mock.call({
                'ipaddress': '2.3.4.5',
                'datetime': '07/Aug/2017:00:00:03 +0000',
                'url': '/',
                'statuscode': '403'
            }),
        ])

    @mock.patch('nginx_access_tailer.nginx_access_log_tailer.SimpleTailer')
    @mock.patch('time.time')
    @mock.patch('time.sleep')
    def test_nothing_logged(self, mock_sleep, mock_time, mock_simple_tailer):
        """If the tailer provides no log lines, nothing is logged."""
        mock_consumer = mock.MagicMock(name='Consumer')

        mock_simple_tailer_instance = mock_simple_tailer.return_value
        mock_simple_tailer_instance.get_lines.side_effect = [[], [], []]

        tailer = NginxAccessLogTailer('log_file', mock_consumer, 3, 1)

        mock_simple_tailer.assert_called_once_with(
            'log_file',
            rotation_check_idle_time_s=3,
            rotation_check_period_s=1)

        mock_time.return_value = 0

        # Hack to break out of the watch loop after a bounded number of passes
        mock_sleep.side_effect = [None, None, SleepExit()]
        try:
            tailer.watch(30)
        except SleepExit:
            pass

        self.assertEqual(mock_simple_tailer_instance.get_lines.call_count, 3)
        mock_sleep.assert_has_calls(
            [mock.call(30), mock.call(30),
             mock.call(30)])
        mock_consumer.record.assert_not_called()

    @mock.patch('nginx_access_tailer.nginx_access_log_tailer.SimpleTailer')
    @mock.patch('time.time')
    @mock.patch('time.sleep')
    def test_omit_unparseable(self, mock_sleep, mock_time, mock_simple_tailer):
        """If the tailer provides an unparseable log line, nothing is logged."""
        mock_simple_tailer_instance = mock_simple_tailer.return_value
        mock_simple_tailer_instance.get_lines.side_effect = [
            [
                '1.2.3.4 - - [07/Aug/2017:00:00:00 +0000] ' +
                '"GET / HTTP/1.1" 200 1105 "-" "SomeClient"',
                # bad IP address
                'a.3.4.5 - - [07/Aug/2017:00:00:01 +0000] ' +
                '"GET / HTTP/1.1" 500 1105 "-" "SomeClient"',
            ],
            [
                # BLAH is not a method
                '1.2.3.4 - - [07/Aug/2017:00:00:02 +0000] ' +
                '"BLAH / HTTP/1.1" 200 1105 "-" "SomeClient"',
                '2.3.4.5 - - [07/Aug/2017:00:00:03 +0000] ' +
                '"GET / HTTP/1.1" 403 1105 "-" "SomeClient"',
            ],
            [],
        ]

        mock_consumer = mock.MagicMock(name='Consumer')

        tailer = NginxAccessLogTailer('log_file', mock_consumer, 3, 1)

        mock_simple_tailer.assert_called_once_with(
            'log_file',
            rotation_check_idle_time_s=3,
            rotation_check_period_s=1)

        mock_time.return_value = 0

        # Hack to break out of the watch loop after a bounded number of passes
        mock_sleep.side_effect = [None, None, SleepExit()]
        try:
            tailer.watch(30)
        except SleepExit:
            pass

        self.assertEqual(mock_simple_tailer_instance.get_lines.call_count, 3)
        mock_sleep.assert_has_calls(
            [mock.call(30), mock.call(30),
             mock.call(30)])
        self.assertEqual(mock_consumer.record.call_count, 2)
        mock_consumer.record.assert_has_calls([
            mock.call({
                'ipaddress': '1.2.3.4',
                'datetime': '07/Aug/2017:00:00:00 +0000',
                'url': '/',
                'statuscode': '200'
            }),
            mock.call({
                'ipaddress': '2.3.4.5',
                'datetime': '07/Aug/2017:00:00:03 +0000',
                'url': '/',
                'statuscode': '403'
            }),
        ])
