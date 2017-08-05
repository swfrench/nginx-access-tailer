"""Tests for InstanceMetadata."""

import unittest
import urllib2

import mock

from nginx_access_tailer import InstanceMetadata


class TestInstanceMetadata(unittest.TestCase):
    """Test basic functionality of InstanceMetadata."""

    @mock.patch('urllib2.Request')
    @mock.patch('urllib2.urlopen')
    def test_fetch(self, mock_urlopen, mock_request):
        """fetch returns the value read from urlopen's return value."""
        mock_req = mock.MagicMock(name='Request')

        mock_readable = mock.MagicMock(name='Readable')
        mock_readable.read.return_value = 'foo'

        mock_request.return_value = mock_req
        mock_urlopen.return_value = mock_readable

        metadata = InstanceMetadata()
        self.assertEqual(metadata.fetch('blah'), 'foo')
        mock_urlopen.assert_called_once_with(mock_req)
        mock_request.assert_called_once()
        mock_readable.read.assert_called_once()

    @mock.patch('urllib2.Request')
    @mock.patch('urllib2.urlopen')
    def test_fetch_none_on_exception(self, mock_urlopen, mock_request):
        """fetch returns None when urlopen raises an exception."""
        mock_req = mock.MagicMock(name='Request')

        mock_request.return_value = mock_req
        mock_urlopen.side_effect = urllib2.URLError('Oops')

        metadata = InstanceMetadata()
        self.assertEqual(metadata.fetch('blah'), None)
        mock_urlopen.assert_called_once_with(mock_req)
        mock_request.assert_called_once()

    @mock.patch.object(InstanceMetadata, 'fetch')
    def test_instance_id(self, mock_fetch):
        """instance_id calls fetch('id') and returns the same value."""
        mock_fetch.return_value = '12345'

        metadata = InstanceMetadata()
        self.assertEqual(metadata.instance_id(), '12345')
        mock_fetch.assert_called_once_with('id')

    @mock.patch.object(InstanceMetadata, 'fetch')
    def test_instance_zone(self, mock_fetch):
        """instance_zone calls fetch('zone') and strips the return value."""
        mock_fetch.return_value = 'foo/bar/baz'

        metadata = InstanceMetadata()
        self.assertEqual(metadata.instance_zone(), 'baz')
        mock_fetch.assert_called_once_with('zone')
