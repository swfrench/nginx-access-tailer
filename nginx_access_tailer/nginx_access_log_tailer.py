"""Access log tailer and associated helpers."""

import logging
import os
import re
import time


class SimpleTailer(object):
    """A simple file tailer supporting basic log rotation detection."""

    def __init__(self,
                 filename,
                 rotation_check_idle_time_s=30,
                 rotation_check_period_s=10):
        """Create the tailer.

        Args:
          filename: filename of the log to read from.
          rotation_check_idle_time_s: number of seconds of idle time (no new
            log lines) before starting rotation checks (seconds; default: 30)
          rotation_check_period_s: period between log rotation checks (seconds;
            default: 10)
        """
        self._filename = filename
        self._flog = None
        self._flog_ino = None
        self._last_read_time = None
        self._last_rotation_check_time = None
        self._rotation_check_idle_time_s = rotation_check_idle_time_s
        self._rotation_check_period_s = rotation_check_period_s

    def _maybe_rotate(self):
        """Periodically check for log rotation by comparing inode numbers."""
        # If we've never performed a full rotation check, do so.
        now = time.time()
        if self._last_rotation_check_time is not None:
            # Otherwise, only do so if a full rotation check period has passed.
            next_check_time = (
                self._last_rotation_check_time + self._rotation_check_period_s)
            if now < next_check_time:
                return
        self._last_rotation_check_time = now
        try:
            ino = os.stat(self._filename).st_ino
        except OSError:
            # It's possible that the log writer has not created the new log
            # file yet
            return
        if ino != self._flog_ino:
            logging.info('Detected file rotation: reopening %s',
                         self._filename)
            self._flog.close()
            self._flog = open(self._filename, 'r')
            self._flog_ino = os.fstat(self._flog.fileno()).st_ino

    def get_lines(self):
        """Returns the latest lines in the log file (possibly none).

        Returns:
          List of the latest log lines, potentially empty if nothing has been
          written or None if the log file cannot be opened.
        """
        if self._flog is None:
            try:
                self._flog = open(self._filename, 'r')
                self._flog_ino = os.fstat(self._flog.fileno()).st_ino
            except IOError as err:
                logging.warning('Could not open log file: %s', err)
                return None
        lines = self._flog.readlines()
        if lines:
            self._last_read_time = time.time()
        else:
            if self._last_read_time is None:
                # We've never read anything: Start rotation checks.
                self._maybe_rotate()
            else:
                # We've read data in the past: Enter rotation checks only after
                # the idle timeout.
                idle_time = time.time() - self._last_read_time
                if idle_time > self._rotation_check_idle_time_s:
                    self._maybe_rotate()
        return lines


class NginxAccessLogTailer(object):
    """Tails the provided access log, passing parsed log lines to the consumer."""

    # Partial regex for a full nginx access log line
    NGINX_ACCESS_LOG_RE = (
        r'(?P<ipaddress>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) - - '
        r'\[(?P<datetime>\d{2}\/[A-Z,a-z]{3}\/\d{4}:\d{2}:\d{2}:\d{2} '
        r'(\+|\-)\d{4})\] ((\"(GET|POST) )(?P<url>.+) (HTTP\/1\.1")) '
        r'(?P<statuscode>\d{3}) .*')

    def __init__(self, log_file, consumer, rotation_check_idle_time_s,
                 rotation_check_period_s):
        """Initialize the tailer.

        Args:
          log_file: path to the nginx access log
          consumer: the log consumer object, exporting both a record method,
            which takes a parsed access log line, and a commit method, which
            writes metrics to stackdriver.
          rotation_check_idle_time_s: min log idle time before starting
            rotation checks (see SimpleTailer).
          rotation_check_period_s: min period between rotation checks (see
            SimpleTailer).
        """
        self._tailer = SimpleTailer(
            log_file,
            rotation_check_idle_time_s=rotation_check_idle_time_s,
            rotation_check_period_s=rotation_check_period_s)
        self._consumer = consumer
        self._re_parser = re.compile(self.NGINX_ACCESS_LOG_RE)

    def _parse_nginx_access_log(self, log_line):
        """Parse an nginx access log line.

        Args:
          log_line: log line from the access log

        Returns:
          dict containing a mapping from matched groups to substrings; only the
          datetime and statuscode fields are assumed present.
        """
        match = self._re_parser.match(log_line)
        if match:
            return match.groupdict()
        return None

    def watch(self, polling_period_s):
        """Watch the configured log file in perpetuity.

        Args:
          polling_period_s: number of seconds between tail checks (optional)
        """
        while True:
            t_start = time.time()
            lines = self._tailer.get_lines()
            if lines is None:
                logging.warning('Could not open log file.')
            else:
                for line in lines:
                    result = self._parse_nginx_access_log(line)
                    if result:
                        self._consumer.record(result)
                    else:
                        logging.warning('Could not parse log line: "%s"', line)
                self._consumer.commit()
            time.sleep(max(0, polling_period_s - time.time() + t_start))
