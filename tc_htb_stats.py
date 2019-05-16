#!/usr/bin/python3
# vim: tabstop=8 expandtab shiftwidth=2 softtabstop=2
# Author: Ryan McGuire <rmcguire@libretechconsulting.com>

import subprocess
import psycopg2
import argparse
import atexit
import signal
import sys
import time
import re

db_c = {}
db_c['dbname']		= 'DBNAME'
db_c['host']		= 'DBHOST'
db_c['user']		= 'DBUSER'
db_c['password']	= 'DBPASS'

# Statistics pruning retention -- uses postgres "interval" syntax
keep_time   = '48 hours'
stat_period = time.strftime('%Y-%m-%d %H:%M:00')

class statsdb:
  def __init__(self):
    self.db 	= psycopg2.connect(**db_c)
    self.query 	= self.db.cursor()

  def createdb(self):
    self.query.execute('CREATE TABLE IF NOT EXISTS statistics (datetime TIMESTAMP, interface varchar(10), class varchar(128), metric varchar(64), PRIMARY KEY (datetime,interface,class,metric), value float(3))')
    self.db.commit()

  def close(self):
    self.db.close()

  def store(self,classes):
    for tc_cls in classes.values():
      for k, v in tc_cls['stats'].items():
        print("Inserting Data:",stat_period,tc_cls['nif'],tc_cls['name'],k,v)
        self.query.execute('INSERT INTO statistics values(%s, %s, %s, %s, %s)',(stat_period,tc_cls['nif'],tc_cls['name'],k,v))
    self.db.commit()

  def prune(self):
    print('>> Pruning database')
    self.query.execute("delete from statistics where datetime < now() - interval %s", (keep_time,))
    print(">>>> Database pruned,",self.query.rowcount,'rows deleted from statistics table')

class tcstats:
  def __init__(self, interface):
    self.nif = interface
    self.classes = dict()

  def collect(self):
    tc_cmd = subprocess.run(["/sbin/tc", '-s', '-nm', 'class', 'show', 'dev', self.nif], stdout=subprocess.PIPE, text=True)
    stats = tc_cmd.stdout
    cur_class=None
    patterns = []
    ptrn_root = re.compile('^\s*class htb.*root rate')
    ptrn_class = re.compile('^\s*class')
    patterns.append(re.compile('^\s+Sent (?P<sent_bytes>\d+) bytes (?P<sent_pkts>\d+) pkt \(dropped (?P<dropped>\d+), overlimits (?P<overlimits>\d+) requeues (?P<requeues>\d+)'))
    patterns.append(re.compile('^\s+rate (?P<rate>[^\s]+) (?P<pps>\d+)pps backlog (?P<backlog_bytes>\d+)b (?P<backlog_pkts>\d+)p requeues (?P<requeues>\d+)'))
    patterns.append(re.compile('^\s+lended: (?P<lended>\d+) borrowed: (?P<borrowed>\d+) giants: (?P<giants>\d+)'))
    patterns.append(re.compile('^\s+tokens: (?P<tokens>\d+) ctokens: (?P<ctokens>\d+)'))
    for line in iter(stats.splitlines()):
      # Process the root class
      if ptrn_root.search(line):
        root_info = line.split(' ')
        cur_class = root_info[2]
        self.classes[cur_class] = dict()
        self.classes[cur_class]['nif'] = self.nif
        self.classes[cur_class]['name'] = root_info[2]
        self.classes[cur_class]['id'] = 'root'
        self.classes[cur_class]['parent'] = self.nif
        self.classes[cur_class]['prio'] = None
        self.classes[cur_class]['rate'] = root_info[5]
        self.classes[cur_class]['ceil'] = root_info[7]
        self.classes[cur_class]['stats'] = dict()
        continue
      # Set up a new class if we've encountered one
      if ptrn_class.search(line):
        class_info = line.split(' ')
        cur_class = class_info[2]
        self.classes[cur_class] = dict()
        self.classes[cur_class]['nif'] = self.nif
        self.classes[cur_class]['name'] = class_info[2]
        self.classes[cur_class]['id'] = class_info[6]
        self.classes[cur_class]['parent'] = class_info[4]
        self.classes[cur_class]['prio'] = class_info[8]
        self.classes[cur_class]['rate'] = class_info[10]
        self.classes[cur_class]['ceil'] = class_info[12]
        self.classes[cur_class]['stats'] = dict()
        continue
      # Carry on if we've not found a class yet
      if cur_class is None:
        continue
      # Retrieve class statistics
      for pattern in patterns:
        match = pattern.match(line)
        if match:
          for key in pattern.groupindex.keys():
            self.classes[cur_class]['stats'][key] = match.group(key)
            continue
    # Process class statistics
    for tc_class in self.classes.values():
      self.process(tc_class)

  def convert_rate(self,rate):
    if re.match('\d+bit',rate.lower()):
      rate = rate.lower().replace('bit','')
    elif re.match('\d+kbit',rate.lower()):
      rate = rate.lower().replace('kbit','')
      rate = float(rate) * 1000
    elif re.match('\d+mbit',rate.lower()):
      rate = rate.lower().replace('mbit','')
      rate = float(rate) * 1000000
    return float(rate)

  def process(self,tc_cls):
    tc_cls['rate'] = self.convert_rate(tc_cls['rate'])
    tc_cls['ceil'] = self.convert_rate(tc_cls['ceil'])
    tc_cls['stats']['rate'] = self.convert_rate(tc_cls['stats']['rate'])
    tc_cls['stats']['utilization_base'] = tc_cls['stats']['rate'] / tc_cls['rate']
    tc_cls['stats']['utilization_ceil'] = tc_cls['stats']['rate'] / tc_cls['ceil']

def main():
  # Argument Parser
  parser = argparse.ArgumentParser(description='Collect and Store HTB Class Statistics')
  parser.add_argument('-i', '--interface', help="Select an interface to poll HTB Class statistics")
  parser.add_argument('-v', '--verbose')
  parser.add_argument('-p', '--prune', help="Prune statistics table", action='store_true')
  args = parser.parse_args()

  # Make sure we're either pruning or collecting
  if not args.prune and not args.interface:
    parser.error('Interface [-i <interface> | --interface <interface>] required if not pruning database')

  # Connect to our statistics database
  db = statsdb()
  db.createdb()

  # Interrupt Handler
  def exit_handler(*args):
    db.close()
    if len(args) < 1:
      print(">> Closing statistics collection...")
      sys.exit(0)
    else:
      print("!! Caught Signal, closing statistics connection...")
      sys.exit(args[1])
  atexit.register(exit_handler)
  signal.signal(signal.SIGTERM, exit_handler)
  signal.signal(signal.SIGINT, exit_handler)

  # Prune Database
  if args.prune:
    db.prune()
    sys.exit(0)

  # Start polling statistics
  print(">> Beginning stats collection on",args.interface,"at",stat_period)
  tc = tcstats(args.interface)
  tc.collect()

  # Write to DB
  db.store(tc.classes)

if __name__ == '__main__':
  main()
