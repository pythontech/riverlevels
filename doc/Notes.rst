The API is described in
  http://environment.data.gov.uk/flood-monitoring/doc/reference

In the following notes, we use $ROOT to mean "http://environment.data.gov.uk/flood-monitoring"


find stations
=============

  $ROOT/id/stations?search=Abingdon

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

Note that a human-friendly web page can be found at e.g.
https://check-for-flooding.service.gov.uk/station/7083
where 7083 is the RLOIid (append "/downstream" for downstream stage).


Get measures
============

  $root/id/measures?stationReference=1503TH

result.items[*].latestReading.value

Get single measure
==================

  $root/id/measures/1681TH-level-stage-i-15_min-mASD

  also with .rdf .ttl .html suffix
