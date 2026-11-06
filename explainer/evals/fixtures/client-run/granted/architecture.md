# Shipment tracking pipeline

The pipeline takes carrier events from three inputs: an EDI feed, a REST webhook, and a nightly CSV upload from small carriers.

Each event lands in a queue. A normaliser maps the carrier's status code onto one of eleven tracking statuses, keyed by the shipment number and the event time.

A duplicate event, one with the same shipment number, status and event time, is dropped. A late event that is older than the current status is stored in the history but does not change the status the customer sees.

The median time from a carrier event to the customer's tracking page is 40 seconds; the 95th percentile is 4 minutes, driven by the nightly CSV.
