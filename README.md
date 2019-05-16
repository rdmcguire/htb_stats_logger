# htb_stats_logger

Linux TC HTB Class Statistics Collection and Storage. This is a simple python script that will poll HTB classes for a given interface and store statistics in a postgres database.
Contributions are welcome, I'm not a software engineer by trade so there is sure to be room for improvement.

## Purpose

The primary goal is to funnel this data into a database so that it can later be graphed.
In the screenshot below I've hooked a Grafana instance into the postgres schema for these statistics.

## Screenshot

![GrafanaExample](/docs/htb_stats_grafana.png)

## Usage

* Create your database and user
* Configure database parameters
* Create a cron job for each interface that you wish to monitor htb stats for

Cron example:
```
# Downlink statistics
* * * * * /path/to/tc_htb_stats.py -i ifb0 >> /var/log/htb_stats_log
# Uplink statistics
* * * * * /path/to/tc_htb_stats.py -i eth0 >> /var/log/htb_stats_log
```
