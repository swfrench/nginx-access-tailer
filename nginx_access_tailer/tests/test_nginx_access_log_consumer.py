"""Tests for NginxAccessLogConsumer."""

import datetime
import unittest

import mock

from nginx_access_tailer import NginxAccessLogConsumer


class TestNginxAccessLogConsumer(unittest.TestCase):
    """Tests for NginxAccessLogConsumer."""

    NGINX_BASE_TIMESTAMP_FORMAT = '%d/%b/%Y:%H:%M:%S'

    def timestamp_at_delta(self, consumer, **kwargs):
        """Return an nginx timestamp at some delta from the reset time.

        Args:
          consumer: an NginxAccessLogConsumer instance.

        Kwargs:
          All keyword arguments accepted by datetime.timedelta.

        Returns:
          An nginx access log timestamp (string) at some delta relative to the
          counte reset time of the supplied NginxAccessLogConsumer.
        """
        now = consumer.reset_time_utc() + datetime.timedelta(**kwargs)
        return '%s +0000' % (
            now.strftime(self.NGINX_BASE_TIMESTAMP_FORMAT))

    def test_basic_recording(self):
        """Verify basic functionality for recording a logging metrics."""
        mock_monitoring_client = mock.MagicMock(name='Client')
        mock_monitoring_resource = mock.MagicMock(name='Resource')

        consumer = NginxAccessLogConsumer(mock_monitoring_client,
                                          mock_monitoring_resource,
                                          'custom.googleapis.com/foo')

        # Timestamp data in the future relative to the counter reset time.
        timestamp = self.timestamp_at_delta(consumer, seconds=10)

        records = [
            {
                'datetime': timestamp,
                'statuscode': '200'
            },
            {
                'datetime': timestamp,
                'statuscode': '200'
            },
            {
                'datetime': timestamp,
                'statuscode': '200'
            },
            {
                'datetime': timestamp,
                'statuscode': '500'
            },
        ]

        mock_monitoring_client.metric.side_effect = [
            '200_metric', '500_metric'
        ]

        for record in records:
            consumer.record(record)
        consumer.commit()

        mock_monitoring_client.metric.assert_has_calls([
            mock.call(
                type_='custom.googleapis.com/foo',
                labels={'response_code': '200'}),
            mock.call(
                type_='custom.googleapis.com/foo',
                labels={'response_code': '500'})
        ])
        mock_monitoring_client.write_point.assert_has_calls(
            [
                mock.call(
                    '200_metric',
                    mock_monitoring_resource,
                    3,
                    start_time=mock.ANY),
                mock.call(
                    '500_metric',
                    mock_monitoring_resource,
                    1,
                    start_time=mock.ANY),
            ],
            any_order=True)

    def test_no_update_logs_nothing(self):
        """No metrics should be logged if nothing is recorded."""
        mock_monitoring_client = mock.MagicMock(name='Client')
        mock_monitoring_resource = mock.MagicMock(name='Resource')
        consumer = NginxAccessLogConsumer(mock_monitoring_client,
                                          mock_monitoring_resource,
                                          'custom.googleapis.com/foo')
        consumer.commit()
        mock_monitoring_client.metric.assert_not_called()
        mock_monitoring_client.write_point.assert_not_called()

    def test_skip_data_in_the_past(self):
        """Records with a timestamp before the reset time are skipped."""
        mock_monitoring_client = mock.MagicMock(name='Client')
        mock_monitoring_resource = mock.MagicMock(name='Resource')

        consumer = NginxAccessLogConsumer(mock_monitoring_client,
                                          mock_monitoring_resource,
                                          'custom.googleapis.com/foo')

        # Timestamp data in the past relative to the counter reset time.
        timestamp = self.timestamp_at_delta(consumer, seconds=-10)

        records = [
            {
                'datetime': timestamp,
                'statuscode': '200'
            },
            {
                'datetime': timestamp,
                'statuscode': '500'
            },
        ]

        mock_monitoring_client.metric.side_effect = [
            '200_metric', '500_metric'
        ]

        for record in records:
            consumer.record(record)
        consumer.commit()
        mock_monitoring_client.metric.assert_not_called()
        mock_monitoring_client.write_point.assert_not_called()

    def test_skip_unparseable(self):
        """Records that cannot be parsed are skipped."""
        mock_monitoring_client = mock.MagicMock(name='Client')
        mock_monitoring_resource = mock.MagicMock(name='Resource')

        consumer = NginxAccessLogConsumer(mock_monitoring_client,
                                          mock_monitoring_resource,
                                          'custom.googleapis.com/foo')

        # Timestamp data in the future relative to the counter reset time.
        timestamp = self.timestamp_at_delta(consumer, seconds=10)

        records = [
            {
                'datetime': timestamp,
                'statuscode': '2zz'  # bad status code
            },
            {
                'datetime': timestamp,
                'statuscode': '200'
            },
            {
                'datetime': timestamp,
                'statuscode': '200'
            },
            {
                'datetime': 'x... xl2',  # bad timestamp
                'statuscode': '500'
            },
            {
                'datetime': timestamp,
                'statuscode': '500'
            },
        ]

        mock_monitoring_client.metric.side_effect = [
            '200_metric', '500_metric'
        ]

        for record in records:
            consumer.record(record)
        consumer.commit()

        mock_monitoring_client.metric.assert_has_calls([
            mock.call(
                type_='custom.googleapis.com/foo',
                labels={'response_code': '200'}),
            mock.call(
                type_='custom.googleapis.com/foo',
                labels={'response_code': '500'})
        ])
        mock_monitoring_client.write_point.assert_has_calls(
            [
                mock.call(
                    '200_metric',
                    mock_monitoring_resource,
                    2,
                    start_time=mock.ANY),
                mock.call(
                    '500_metric',
                    mock_monitoring_resource,
                    1,
                    start_time=mock.ANY),
            ],
            any_order=True)
