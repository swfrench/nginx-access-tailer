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
        self._reset_time_utc = datetime.utcnow()
        self._reset_time_utc_offset = self._reset_time_utc.replace(
            tzinfo=_FixedOffsetTimeZone(0))
        self._response_codes = {}
        self._response_code_metrics = {}
        self._has_delta = False
        self._http_response_metric_name = http_response_metric_name

    def _parse_nginx_timestamp(self, ts_str):
        """Parse the provided timestamp string.

        Args:
          ts_str: nginx format timestamp string '02/Jul/2017:00:00:00 +0000'

        Returns:
          datetime object or None if the timestamp could not be parsed.
        """
        try:
            base, offset = ts_str.split(' ')
            base_dt = datetime.strptime(base, self.NGINX_BASE_TIMESTAMP_FORMAT)
        except ValueError:
            return None
        return base_dt.replace(tzinfo=_FixedOffsetTimeZone(int(offset)))

    def reset_time_utc(self):
        """Returns the time relative to which metric counters are registered.

        Returns:
          datetime object relative to UTC (no tzinfo).
        """
        return self._reset_time_utc

    def record(self, parsed_groups):
        """Record supported metrics from the parsed log line.

        Args:
          parsed_groups: dict of str => str elements from an nginx access log
            line; only relevant fields are datetime and statuscode.
        """
        log_time = self._parse_nginx_timestamp(parsed_groups['datetime'])
        if log_time is None:
            logging.warn('Could not parse datetime: "%s"',
                         parsed_groups['datetime'])
            return
        if log_time < self._reset_time_utc_offset:
            return
        try:
            code = int(parsed_groups['statuscode'])
        except ValueError:
            logging.warn('Could not parse statuscode: "%s"',
                         parsed_groups['statuscode'])
            return
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
                    start_time=self._reset_time_utc)
            self._has_delta = False
