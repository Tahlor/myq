# Historical local MyQ API evidence

This is a lead for Track B2, **not** proof that the owner's current integrated Wi-Fi opener behaves the same way.

In January 2020, McAfee Advanced Threat Research (now Trellix) published reverse-engineering work on the older Chamberlain **myQ Smart Garage Hub**. Their device:

- listened locally on TCP port 80;
- redirected a browser request toward `start.html`;
- had a local setup/system HTTP API recovered from firmware analysis;
- included a `/sys/mode` API path used during their testing;
- exposed no other listening ports in their scan.

Reference: https://www.trellix.com/blogs/research/we-be-jammin-bypassing-chamberlain-myq-garage-doors/

## Why this matters to our software-only project

It disproves the broad assumption that MyQ devices have *never* had a local API. Before investing in DNS/TLS/MQTT redirection, test the confirmed current opener for a surviving or evolved local HTTP setup surface.

For the current opener, after positively identifying its LAN IP:

1. probe TCP 80 and 443 explicitly;
2. if 80 answers, issue only read-only `GET /`, `GET /start.html`, `HEAD`, and `OPTIONS` first;
3. record redirects, response headers, server banner and discovered links/paths;
4. do **not** issue historical mutating `/sys/*` calls merely to see what happens;
5. compare any paths/resources with current APK setup/provisioning strings.

The 2020 target was a retrofit Hub with a Marvell RTOS Wi-Fi module. An integrated 2026 Chamberlain/LiftMaster opener may use completely different firmware, so absence of port 80 is a normal result rather than evidence that discovery failed.
