#!/usr/bin/python
#=======================================================================
# Get river levels from Environment Agency
#-----------------------------------------------------------------------
# Copyright (C) 2016  Colin Hogben <colin@pythontech.co.uk>
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
import os
import logging
import urllib2
import json

API_ROOT = 'http://environment.data.gov.uk/flood-monitoring'

_log = logging.getLogger('riverlevels')

class Monitor(object):
    def __init__(self, station, qualifier, name=None, threshold=0.1):
        self.station = station
        self.qualifier = qualifier
        self.name = name  or  station
        self.threshold = threshold
        self.key = '%s.%s' % (station, qualifier)
        self.alert_level = None
        self.alert_date = None

    def from_save(self, save):
        if self.key not in save:
            return
        data = save[self.key]
        self.alert_level = data['alert_level']
        self.alert_date = data['alert_date']

    def to_save(self, save):
        data = dict()
        data['alert_level'] = self.alert_level
        data['alert_date'] = self.alert_date
        save[self.key] = data

    def get_measures(self):
        url = API_ROOT+'/id/measures?stationReference='+self.station
        f = urllib2.urlopen(url)
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
        if self.alert_level is None:
            return None
        delta = value - self.alert_level
        if abs(delta) > self.threshold:
            alert = ('%s now %.2f, %s by %.2f since %s' %
                     (self.name,
                      value,
                      'UP' if delta > 0 else 'DOWN',
                      abs(delta),
                      self.alert_date))
            self.alert_level = value
            self.alert_date = date
            return alert
        return None

class Manager(object):
    def __init__(self, monitors, savefile):
        self.monitors = monitors
        self.savefile = savefile
        try:
            self.read_save()
        except IOError as e:
            self.save = {}

    @classmethod
    def from_config(cls, config):
        monitors = []
        for mondef in config.get('monitors', []):
            monitors.append(Monitor(**mondef))
        savefile = config.get('savefile',
                              os.path.expanduser('~/.riverlevels.save'))
        return cls(monitors, savefile)

    @classmethod
    def from_config_file(cls, filespec):
        if isinstance(filespec, file):
            config = json.load(filespec)
        else:
            with open(filespec,'r') as f:
                config = json.load(f)
        return cls.from_config(config)

    def read_save(self):
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
            #print self.save
            data = json.dumps(self.save)
            #print data
            json.dump(self.save, f, indent=2, sort_keys=True)
        os.rename(newsave, self.savefile)

    def evaluate_alerts(self):
        """Check level for each monitor and return alerts.
        An alert is raised if the current level differs from the previously
        alerted level by more than the configured threshold.
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

if __name__=='__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-v','--verbose', dest='loglevel',
                    action='store_const', const=logging.INFO,
                    default=logging.WARNING)
    ap.add_argument('-d','--debug', dest='loglevel',
                    action='store_const', const=logging.DEBUG)
    sub = ap.add_subparsers(dest='action')
    # level [-q qual] stationref
    level = sub.add_parser('level')
    level.add_argument('-q','--qualifier', default='Stage',
                       help='Select which measure (default: Stage)')
    level.add_argument('station')
    # alerts
    alerts = sub.add_parser('alerts')
    alerts.add_argument('-c','--config', type=argparse.FileType('r'),
                        help='Configuration file (default: ~/.riverlevels.conf)')
    # --
    args = ap.parse_args()
    logging.basicConfig(level=args.loglevel)
    if args.action == 'level':
        mon = Monitor(args.station, args.qualifier)
        value, date = mon.get_level()
        print value, date
    elif args.action == 'alerts':
        conffile = args.config or os.path.expanduser('~/.riverlevels.conf')
        manager = Manager.from_config_file(conffile)
        alerts = manager.evaluate_alerts()
        manager.write_save()
        for alert in alerts:
            print alert
