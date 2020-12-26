#!/usr/bin/python
#=======================================================================
"""
Get river levels from Environment Agency
"""
#-----------------------------------------------------------------------
# Copyright (C) 2016-2019  Colin Hogben <colin@pythontech.co.uk>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301  USA
#=======================================================================
from __future__ import print_function
import os
import logging
import sys
if sys.version_info[0] < 3:
    from urllib2 import urlopen
else:
    from urllib.request import urlopen
from collections import namedtuple
import json
import subprocess
try:
    from html import escape
except ImportError:             # PY2
    from cgi import escape

DEFAULT_CONFIG_FILE = '~/.riverlevels.conf'
DEFAULT_SAVE_FILE = '~/.riverlevels.save'
API_ROOT = 'http://environment.data.gov.uk/flood-monitoring'
WEB_BASE = 'https://flood-warning-information.service.gov.uk/station'
# Acknowledgement of data source, requested by EA
ACKNOWLEDGEMENT = 'This uses Environment Agency flood and river level data'\
                  ' from the real-time data API (Beta)'

_log = logging.getLogger('riverlevels')

Alert = namedtuple('Alert', ['updown', # 'UP' or 'DOWN' for level change
                             'name',
                             'RLOIid',
                             'direction', # 'u' or 'd' for monitor
                             'text'])

class Monitor(object):
    """Handler for a single measurement at a station."""
    def __init__(self, station, qualifier='Stage', name=None, RLOIid=None, threshold=0.1):
        self.station = station
        self.qualifier = qualifier
        self.name = name  or  station
        self.RLOIid = RLOIid
        self.threshold = threshold
        self.key = '%s.%s' % (station, qualifier)
        self.alert_level = None
        self.alert_date = None

    def from_save(self, save):
        """Update internal state from savefile data."""
        if self.key not in save:
            return
        data = save[self.key]
        self.alert_level = data['alert_level']
        self.alert_date = data['alert_date']

    def to_save(self, save):
        """Update savefile data from internal state."""
        data = dict()
        data['alert_level'] = self.alert_level
        data['alert_date'] = self.alert_date
        save[self.key] = data

    def get_measures(self):
        url = API_ROOT+'/id/measures?stationReference='+self.station
        f = urlopen(url)
        body = f.read()
        data = json.loads(body)
        return data

    def get_level(self):
        data = self.get_measures()
        for item in data['items']:
            if item['qualifier'] == self.qualifier:
                if item['parameter'] == 'level':
                    latest = item['latestReading']
                    return latest['value'], latest['dateTime']
        raise KeyError('No level measure for %s' % self.qualifier)

    def check_alert(self, value, date):
        """Return an alert for the monitor if the level has changed.
        The criterion is that the current level differs from the
        level at the last alert (or the first measurement) by more than
        the given threshold.  That way (1) small changes in level do
        not raise spurious alerts; and (2) a fast-changing level will
        result in a sequence of alerts - which is no bad thing.
        """
        if self.alert_level is None:
            # First reading
            self.alert_level = value
            self.alert_date = date
            return None
        delta = value - self.alert_level
        _log.debug('value=%g delta=%g', value, delta)
        if abs(delta) > self.threshold:
            updown = 'UP' if delta > 0 else 'DOWN'
            text = ('now %.2fm, %s by %.0fcm since %s' %
                    (value,
                     updown,
                     abs(delta) * 100,
                     self.alert_date.replace('T',' ').replace('Z','')))
            self.alert_level = value
            self.alert_date = date
            dirn = 'd'  if 'Downstream' in self.qualifier  else 'u'
            return Alert(updown, self.name, self.RLOIid, dirn, text)
        return None

class Manager(object):
    def __init__(self, monitors, config={}):
        self.monitors = monitors
        self.config = config
        self.savefile = os.path.expanduser(config.get('savefile',
                                                      DEFAULT_SAVE_FILE))
        self.save = {}
        self.read_save()

    @classmethod
    def from_config(cls, config):
        monitors = []
        for mondef in config.pop('monitors', []):
            monitors.append(Monitor(**mondef))
        return cls(monitors, config)

    @classmethod
    def from_config_file(cls, filespec):
        if hasattr(filespec, 'read'):
            config = json.load(filespec)
        else:
            with open(filespec,'r') as f:
                config = json.load(f)
        return cls.from_config(config)

    def read_save(self):
        if not os.path.exists(self.savefile):
            return
        with open(self.savefile,'r') as f:
            data = f.read()
            self.save = json.loads(data)
        for mon in self.monitors:
            mon.from_save(self.save)

    def write_save(self):
        for mon in self.monitors:
            mon.to_save(self.save)
        newsave = self.savefile + '.new'
        with open(newsave,'w') as f:
            data = json.dumps(self.save)
            json.dump(self.save, f, indent=2, sort_keys=True)
        os.rename(newsave, self.savefile)

    def evaluate_alerts(self):
        """Check level for each monitor and return alerts.
        An alert is raised if the current level differs from the previously
        alerted level by more than the configured threshold.
        Each alert is a tuple ('UP' or 'DOWN', name, text)
        """
        alerts = []
        for mon in self.monitors:
            mon.from_save(self.save)
            try:
                value, date = mon.get_level()
            except Exception as e:
                _log.warn('%s: %s', mon.name, e)
            else:
                _log.info('%s: old=%s new=%s',
                          mon.name, mon.alert_level, value)
                alert = mon.check_alert(value, date)
                if alert:
                    alerts.append(alert)
        return alerts

    def email_alerts(self, no_action=False):
        """Evaluate alerts and send via email.
        """
        email = self.config.get('email')
        if not email:
            raise ValueError('No "email" group in configuration')
        recipients = email.get('recipients')
        if not recipients:
            raise ValueError('No email recipients in configuration')
        html = email.get('html')
        alerts = self.evaluate_alerts()
        if not alerts:
            return
        up = any([a.updown == 'UP' for a in alerts])
        down = any([a.updown == 'DOWN' for a in alerts])
        updown = 'UP/DOWN' if up and down  else 'UP' if up  else 'DOWN'
        subject = email.get('subject', 'River level changes ' + updown)
        headers = ['To: %s' % ','.join(recipients),
                   'Subject: %s' % subject]
        from_ = email.get('from')
        if from_:
            headers.append('From: %s' % from_)
        if html:
            body = ['<!doctype html>',
                    '<html lang="en">',
                    '<head><title>%s</title></head>' % escape(subject),
                    '<body>',
                    '<div id="alerts">']
            for a in alerts:
                hname = escape(a.name)
                if a.RLOIid is not None:
                    url = '%s/%s?direction=%s' % \
                          (WEB_BASE, a.RLOIid, a.direction)
                    hname = '<a href="%s">%s</a>' % (escape(url), hname)
                body.append('%s %s<br>' % (hname, escape(a.text)))
            body += ['</div>',
                     '<div id="ack">%s</div>' % escape(ACKNOWLEDGEMENT),
                     '</body>',
                     '</html>']
            headers.append('Content-type: text/html; charset=UTF-8')
        else:
            body = ['%s %s' % (alert.name, alert.text)  for alert in alerts]
            body += ['', ACKNOWLEDGEMENT]
            headers.append('Content-type: text/plain; charset=UTF-8')
        text = '\n'.join(headers +
                         [''] +
                         [b.encode('utf-8') for b in body]) + '\n'
        if no_action:
            print(text, end='')
        else:
            sendmail = email.get('sendmail', '/usr/sbin/sendmail')
            p = subprocess.Popen([sendmail, '-t', '-oi'],
                                 stdin=subprocess.PIPE)
            p.communicate(text.encode('utf8'))

def cmdline():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-v','--verbose', dest='loglevel',
                    action='store_const', const=logging.INFO,
                    default=logging.WARNING)
    ap.add_argument('-d','--debug', dest='loglevel',
                    action='store_const', const=logging.DEBUG)
    sub = ap.add_subparsers(dest='action', metavar='ACTION')
    # level [-q qual] stationref
    level = sub.add_parser('level',
                           help='Get the current level from a given station')
    level.add_argument('-q','--qualifier', default='Stage',
                       help='Select which measure (default: Stage)')
    level.add_argument('station')
    # alerts [-c conf]
    alerts = sub.add_parser('alerts',
                            help=Manager.evaluate_alerts.__doc__.split('\n')[0])
    alerts.add_argument('-c','--config', type=argparse.FileType('r'),
                        help='Configuration file (default: %s)' %
                        DEFAULT_CONFIG_FILE)
    # email-alerts [-c conf] [-n]
    email = sub.add_parser('email-alerts',
                           help=Manager.email_alerts.__doc__.split('\n')[0])
    email.add_argument('-c','--config', type=argparse.FileType('r'),
                       help='Configuration file (default: %s)' %
                       DEFAULT_CONFIG_FILE)
    email.add_argument('-n','--no-action', action='store_true',
                       help='Output email but do not send it.')
    # --
    args = ap.parse_args()
    logging.basicConfig(level=args.loglevel)
    if args.action == 'level':
        mon = Monitor(args.station, args.qualifier)
        value, date = mon.get_level()
        print(value, date)
    elif args.action == 'alerts':
        conffile = args.config or os.path.expanduser(DEFAULT_CONFIG_FILE)
        manager = Manager.from_config_file(conffile)
        alerts = manager.evaluate_alerts()
        manager.write_save()
        for alert in alerts:
            print(alert)
    elif args.action == 'email-alerts':
        conffile = args.config or os.path.expanduser(DEFAULT_CONFIG_FILE)
        manager = Manager.from_config_file(conffile)
        manager.email_alerts(no_action=args.no_action)
        manager.write_save()

if __name__=='__main__':
    cmdline()
