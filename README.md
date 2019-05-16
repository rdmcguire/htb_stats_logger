# htb_stats_logger

Linux TC HTB Class Statistics Collection and Storage. This is a simple python script that will poll HTB classes for a given interface and store statistics in a postgres database.
Contributions are welcome, I'm not a software engineer by trade so there is sure to be room for improvement.

## Purpose

The primary goal is to funnel this data into a database so that it can later be graphed.
In the screenshot below I've hooked a Grafana instance into the postgres schema for these statistics.

## Screenshot

![GrafanaExample](/docs/htb_stats_grafana.png)

## Installation and Usage

* Name your HTB classes in '/etc/iproute2/tc\_cls'
```
# Example tc_cls file
1:1     WISP.DL.
1:20    VoIP....
1:40    Audio...
1:50    Web.....
```
* Create your database and user
* Allow access in pg\_hba.conf as needed
* Configure database parameters in tc\_htb\_stats.py
* Create a cron job for each interface that you wish to monitor htb stats for

### Cron example
```
# Downlink statistics
* * * * * /path/to/tc_htb_stats.py -i ifb0 >> /var/log/htb_stats_log
# Uplink statistics
* * * * * /path/to/tc_htb_stats.py -i eth0 >> /var/log/htb_stats_log
```

## Grafana Dataset sample

The following is a sample dataset query for grafana that will allow you to compare data rate between HTB classes.
As I'm using IFB for downlink traffic shaping, my interface is ifb0. Replace as appropriate.
I also excluded my root HTB class to avoid rollup-statistics skewing graph data.

```
SELECT
  datetime AS "time",
  concat(class,' ',metric) AS metric,
  avg(value) AS "value"
  FROM statistics
  WHERE
    $__timeFilter(datetime)
    AND metric = 'rate'
    AND interface = 'ifb0'
    AND class not like 'WISP%'
  GROUP BY class, datetime,2
  ORDER BY 1,2
  ```
