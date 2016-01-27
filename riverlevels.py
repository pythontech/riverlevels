#!/usr/bin/python
#=======================================================================
#       Get river levels from Environment Agency
#=======================================================================
import os
import logging
import urllib2
import json

API_ROOT = 'http://environment.data.gov.uk/flood-monitoring'

SAVEFILE = os.path.expanduser('~/.riverlevels.save')
def my_monitors():
    return (Monitor(name='Abingdon Lock',
                    station='1503TH',qualifier='Downstream Stage',
                    threshold=0.05),
            Monitor(name='Ock at Tesco',
                    station='1790TH',qualifier='Downstream Stage',
                    threshold=0.05),
            )

_log = logging.getLogger('riverlevels')

class Monitor(object):
    def __init__(self, name, station, qualifier, threshold=0.1):
        self.name = name
        self.station = station
        self.qualifier = qualifier
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
        raise KeyError('No level measure for %s' % qualifier)

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

    def do_update(self):
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

def get_measures(station, qualifier='Stage'):
    f = urllib2.urlopen(API_ROOT+'/id/measures?stationReference='+station)
    body = f.read()
    data = json.loads(body)
    return data

def get_level(station, qualifier='Stage'):
    data = get_measures(station, qualifier)
    for item in data['items']:
        if item['qualifier'] == qualifier:
            latest = item['latestReading']
            return latest['value'], latest['dateTime']
    raise KeyError('No measure for %s' % qualifier)

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
    # update
    update = sub.add_parser('update')
    update.add_argument('-n','--noaction', action='store_true')
    # --
    args = ap.parse_args()
    logging.basicConfig(level=args.loglevel)
    if args.action == 'level':
        mon = Monitor(args.station, args.station, args.qualifier)
        value, date = mon.get_level()
        print value, date
    elif args.action == 'update':
        # do_update()
        manager = Manager(my_monitors(), SAVEFILE)
        alerts = manager.do_update()
        manager.write_save()
        for alert in alerts:
            print alert


