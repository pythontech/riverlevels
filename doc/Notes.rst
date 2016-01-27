The API is described in
  http://environment.data.gov.uk/flood-monitoring/doc/reference

In the following notes, we use $ROOT to mean "http://environment.data.gov.uk/flood-monitoring"


find stations
=============

  $ROOT/id/stations?search=Abingdon

From the results we find items of interest

================ =================== ========= ========= ==========
stationReference label               riverName parameter qualifiers
================ =================== ========= ========= ==========
1681TH           Abingdon Peachcroft Ock       level     Stage
1790TH           Abingdon            Ock       level     Stage
							 Downstream Stage
1679TH           Abingdon            Stert     level     Stage
1503TH           Abingdon Lock       Thames    level     Stage
							 Downstream Stage
1799TH           Culham Lock         Thames    level     Stage
							 Downstream Stage
================ =================== ========= ========= ==========


Get measures
============

  $root/id/measures?stationReference=1503TH

result.items[*].latestReading.value

Get single measure
==================

  $root/id/measures/1681TH-level-stage-i-15_min-mASD

  also with .rdf .ttl .html suffix
