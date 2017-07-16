"""Helpers for accessing the GCE instance metadata service."""

import urllib2


class InstanceMetadata(object):
    """Simple helper for fetching instance metadata."""

    BASE_URL = 'http://metadata.google.internal/computeMetadata/v1/instance'

    def _fetch(self, entry):
        """Fetch the requested instance metadata entry."""
        request = urllib2.Request(
            url='%s/%s' % (self.BASE_URL, entry),
            headers={'Metadata-Flavor': 'Google'})
        try:
            instance_id = urllib2.urlopen(request).read()
        except:
            instance_id = None
        return instance_id

    def instance_id(self):
        """Fetch the instance id."""
        return self._fetch('id')

    def instance_zone(self, shorten=True):
        """Fetch the instance zone."""
        zone = self._fetch('zone')
        if zone is not None and shorten:
            zone = zone.split('/')[-1]
        return zone
