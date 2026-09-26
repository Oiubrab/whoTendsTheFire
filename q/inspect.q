/ read-only inspection server for the KX extension.
/ server.py shells out to its own q per request and savedb[]s each time,
/ so this process holds a SNAPSHOT, not live state. Call refresh[] to
/ pull the latest from db/. Do not savedb[] from here -- this process
/ would clobber whatever the web UI has written since it loaded.
\l q/torches.q
loaddb[]
refresh: {[] loaddb[]; `hearths`prophecies`graphs`torches!(count hearths; count prophecies; count graphs; count torches)}
