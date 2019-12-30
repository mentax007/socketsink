# socketsink
A tool for 2600hz kazoo users to gather and store websocket events. Then import them into a database for analysis in a NON-realtime manner.

Websocket events are initially captured and stored by sink.py. The events are captured, saved in memory and then writted out to a gziped file after 30 minutes. While it is technically possible to capture all events on a single VPS, using 2 using a staggered time highly reccomended.  For example, VPS1 should have a cron running the script every 0 and 30 min. VPS 2 should have a cron running every 15 and 45 min. This provides good overlap. Many of these events such as hold and park events are never stored in kazoo and will be lost if not catured here. After capture, they are uploaded to backblaze. Why backblaze you ask? Well, their storage is super cheap, they have an SDK for python and great scalability. Kafka would be a really nice alternative and could offer some really nice realtime data, but there's less to maintain here without it.

dbupload.py scans backblaze for uploaded files and commits them to a MySQL database. Finally, various sql commands are run to transform the extemely difficult to interpret call events into an end-user approachable table of call-interactions.

The final component is a WebUI to display this data to youe end-users. I will be using an app called dadabik to do this. But it's not free nor open source. So I won't be able to include it all for you to use.
