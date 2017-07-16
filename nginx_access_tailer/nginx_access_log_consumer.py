"""Consumer responsible for writing to stackdriver and associated helpers."""

import logging
from datetime import tzinfo, timedelta, datetime


class _FixedOffsetTimeZone(tzinfo):
    """Hack for dealing w/ lack of %z in 2.7 strptime.

    See https://docs.python.org/2/library/datetime.html#datetime.tzinfo.fromutc
    """

    def __init__(self, offset):
        self.__offset = timedelta(seconds=offset)
        self.__name = 'UTC%+is' % (offset)

    def utcoffset(self, dt):
        _ = dt
        return self.__offset

    def tzname(self, dt):
        _ = dt
        return self.__name

    def dst(self, dt):
        _ = dt
        return timedelta(0)


class NginxAccessLogConsumer(object):
    """Consumes nginx log lines and exports to custom stackdriver metrics.

    Currently only supports exporting request counts by status code.
    """

    NGINX_BASE_TIMESTAMP_FORMAT = '%d/%b/%Y:%H:%M:%S'

    def __init__(self, client, resource, http_response_metric_name):
        """Initialize NginxAccessLogConsumer.

        Args:
          client: cloud monitoring client.
          resource: resource object identifying the monitored instance.
        """
        self._client = client
        self._resource = resource
        self._reset_time = None
        self._reset_time_internal = None
        self._response_codes = {}
        self._response_code_metrics = {}
        self._has_delta = False
        self._http_response_metric_name = http_response_metric_name

    def _parse_nginx_timestamp(self, ts_str):
        """Parse the provided timestamp string.

        Args:
          ts_str: nginx format timestamp string '02/Jul/2017:00:00:00 +0000'

        Returns:
          datetime object.
        """
        base, offset = ts_str.split(' ')
        base_dt = datetime.strptime(base, self.NGINX_BASE_TIMESTAMP_FORMAT)
        return base_dt.replace(tzinfo=_FixedOffsetTimeZone(int(offset)))

    def record(self, parsed_groups):
        """Record supported metrics from the parsed log line.

        Args:
          parsed_groups: dict of str => str elements from an nginx access log
            line; only relevant fields are datetime and statuscode.
        """
        log_time = self._parse_nginx_timestamp(parsed_groups['datetime'])
        if self._reset_time is None:
            self._reset_time = datetime.utcnow()
            self._reset_time_internal = datetime.now(log_time.tzinfo)
        if log_time < self._reset_time_internal:
            return
        code = int(parsed_groups['statuscode'])
        if code not in self._response_codes:
            self._response_codes[code] = 0
        self._response_codes[code] += 1
        self._has_delta = True

    def commit(self):
        """Write the supported metrics to cloud monitoring."""
        if self._has_delta:
            logging.info('Writing updated counters to %s: %s',
                         self._http_response_metric_name,
                         str(self._response_codes))
            for code, count in self._response_codes.iteritems():
                if code not in self._response_code_metrics:
                    self._response_code_metrics[code] = self._client.metric(
                        type_=self._http_response_metric_name,
                        labels={'response_code': str(code)})
                self._client.write_point(
                    self._response_code_metrics[code],
                    self._resource,
                    count,
                    start_time=self._reset_time)
            self._has_delta = False
