"""Main access log tailer / exporter program."""

import logging
import logging.handlers
import sys

import gflags
from google.cloud import monitoring

from . import InstanceMetadata, NginxAccessLogConsumer, NginxAccessLogTailer

FLAGS = gflags.FLAGS
gflags.DEFINE_string('access_log', '/var/log/nginx/access.log',
                     'Nginx access log file.')
gflags.DEFINE_float('polling_period_s', 30.0,
                    'Time between periodic log tail checks.')
gflags.DEFINE_float(
    'rotation_check_idle_time_s', 120.0,
    'How long to wait after seeing no further log lines in the '
    'tailed file before starting rotation checks.')
gflags.DEFINE_float('rotation_check_period_s', 60.0,
                    'Period between rotation checks on attempts to retrieve '
                    'log lines (unsuccessfully) from an idle log file.')
gflags.DEFINE_string(
    'http_response_metric_name', 'custom.googleapis.com/http_response_count',
    'Name of the custom stackdriver metric you would like to use.')


def main():
    """Run the tailer."""
    _ = FLAGS(sys.argv)

    # Setup logging: Send to syslog.
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.handlers.SysLogHandler(address='/dev/log')
    fmt = logging.Formatter(
        '%(levelname)s nginx-access-tailer %(asctime)s] %(message)s')
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    # Fetch required metadata.
    meta = InstanceMetadata()
    instance_id = meta.instance_id()
    if instance_id is None:
        logging.critical('Could not fetch instance id')
        sys.exit(1)
    instance_zone = meta.instance_zone()
    if instance_zone is None:
        logging.critical('Could not fetch instance zone')
        sys.exit(1)

    # Create logging client and resource object.
    client = monitoring.Client()
    resource = client.resource(
        'gce_instance',
        labels={'instance_id': instance_id,
                'zone': instance_zone})
    logging.info('Created monitoring client and resource object '
                 '(instance: %s; zone: %s)', instance_id, instance_zone)

    # Initialize consumer and tailer.
    consumer = NginxAccessLogConsumer(client, resource,
                                      FLAGS.http_response_metric_name)
    tailer = NginxAccessLogTailer(FLAGS.access_log, consumer,
                                  FLAGS.rotation_check_idle_time_s,
                                  FLAGS.rotation_check_period_s)

    # Enter loop ...
    logging.info('Entering polling loop')
    tailer.watch(FLAGS.polling_period_s)
