Usage
=====

Typically you will set up a cron job to run the script at regular intervals
e.g. to check at 54 minutes past every hour::

  54 * * * *  python PATH/TO/riverlevels.py email-alerts


Find stations for configuration file
====================================

For example:

  http://environment.data.gov.uk/flood-monitoring/id/stations?search=Abingdon

From the results we find items of interest

================ ====== =================== ========= ========= ==========
stationReference RLOIid label               riverName parameter qualifiers
================ ====== =================== ========= ========= ==========
1681TH           7402   Abingdon Peachcroft Ock       level     Stage
1790TH           7081   Abingdon            Ock       level     Stage
                                                                Downstream Stage
1679TH           7003   Abingdon            Stert     level     Stage
1503TH           7073   Abingdon Lock       Thames    level     Stage
                                                                Downstream Stage
1799TH           7083   Culham Lock         Thames    level     Stage
                                                                Downstream Stage
================ ====== =================== ========= ========= ==========

Use these results to create the configuration file ~/.riverlevels

Configuration File Format
=========================

Example::

  {
    "monitors": [
      {
        "name": "Abingdon Lock",
        "station": "1503TH",
	"RLOIid": "7073",
        "qualifier": "Downstream Stage",
        "threshold": 0.10
      },
      {
        "name": "Ock near Tesco",
        "station": "1790TH",
	"RLOIid": "7081",
        "qualifier": "Downstream Stage",
        "threshold": 0.05
      }
    ],
    "savefile": "/home/colin/.riverlevels.save",
    "email": {
      "recipients": [
        "colin@example.com",
	"someone.else@example.org"
      ],
      "html": true,
      "subject": "River level changes"
    }
  }
