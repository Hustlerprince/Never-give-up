#!/usr/bin/env python3
"""Convert Cloudfront pixel logs from benhoyt.com to combined log format for goaccess."""

import collections
import csv
import datetime
import fileinput
import sys
import urllib.parse


#Fields: date time x-edge-location sc-bytes c-ip cs-method cs(Host)
#        cs-uri-stem sc-status cs(Referer) cs(User-Agent) cs-uri-query
#        cs(Cookie) x-edge-result-type x-edge-request-id x-host-header
#        cs-protocol cs-bytes time-taken x-forwarded-for ssl-protocol
#        ssl-cipher x-edge-response-result-type cs-protocol-version
#        fle-status fle-encrypted-fields
REQUIRED_FIELDS = [
    'date', 'time', 'c-ip', 'cs-uri-stem', 'cs(Referer)',
    'cs(User-Agent)', 'cs-uri-query', 'x-forwarded-for',
]
PIXEL_PATH = '/pixel.png'

finput = fileinput.input(openhook=fileinput.hook_compressed)


def process_input():
    for line in finput:
        if finput.isfirstline():
            field_names = None

        if isinstance(line, bytes):
            line = line.decode('utf-8')
        line = line.rstrip()
        if line.startswith('#'):
            parts = line[1:].split(':', 1)
            if len(parts) != 2:
                log_error(': not found not # directive line')
                continue
            directive, value = parts
            value = value.strip()
            if directive == 'Fields':
                field_names = value.split()
            continue

        if field_names is None:
            log_error('#Fields directive not found at start of file')
            return False

        field_list = line.split('\t')
        if len(field_list) != len(field_names):
            log_error('number of fields ({}) != expected number ({})'.format(
                len(field_list), len(field_names)))
            continue
        fields = dict(zip(field_names, line.split('\t')))

        missing_fields = [f for f in REQUIRED_FIELDS if f not in fields]
        if missing_fields:
            log_error('missing fields: {}'.format(', '.join(missing_fields)))
            continue

        if fields['cs-uri-stem'] != PIXEL_PATH:
            continue
        query = urllib.parse.parse_qs(fields['cs-uri-query'])
        if 'u' not in query or not query['u'][0].startswith('%2F'):
            continue
        path = urllib.parse.unquote(query['u'][0])
        referrer = urllib.parse.unquote(query.get('r', ['-'])[0])

        try:
            date = datetime.datetime.strptime(fields['date'], '%Y-%m-%d')
        except ValueError:
            log_error('invalid date: {}'.format(fields['date']))
            continue

        user_agent = unquote(fields['cs(User-Agent)'])

        ip = fields['c-ip']
        if fields['x-forwarded-for'] != '-':
            ip = fields['x-forwarded-for']

        print('{ip} - - [{date:%d/%b/%Y}:{time} +0000] "GET {path} HTTP/1.1" 200 - {referrer} {user_agent}'.format(
            ip=ip,
            date=date,
            time=fields['time'],
            path=quote(path),
            referrer='"'+quote(referrer)+'"' if referrer != '-' else '-',
            user_agent='"'+quote(user_agent)+'"' if user_agent != '-' else '-',
        ))


def quote(text):
    return text.replace('"', '%22')


def unquote(text):
    # See https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/AccessLogs.html#LogFileFormat
    text = text.replace('%2522', '%25')
    text = text.replace('%255C', '%5C')
    text = text.replace('%2520', '%20')
    return urllib.parse.unquote(text)


def log_error(message):
    print('{}:{}: {}'.format(finput.filename(), finput.filelineno(), message),
          file=sys.stderr)


if __name__ == '__main__':
    sys.exit(0 if process_input() else 1)