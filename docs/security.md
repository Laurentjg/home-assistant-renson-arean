# Storing your gateway password

**Your password is stored in plain text — not hashed, not encrypted.** This is worth understanding before you install anything, and it is true of every Home Assistant integration that needs a password.

It cannot be otherwise here: the OpenMotics gateway trades your real password for a one-hour token, so the integration must be able to present that password again at every renewal. A hash is useless for that. And Home Assistant stores integration settings as plain JSON in `.storage/core.config_entries`; there is no encrypted store.

**In practice: your gateway password is readable in your Home Assistant backups.**

What the integration does do: the token is kept in memory and never written to disk, credentials never appear in a log line (not even at debug level — the password travels in the URL, so naive logging would leak it outright), and downloadable diagnostics are redacted.

What you can do:

- Create a **separate gateway user for Home Assistant**, not your main or installer account. Revoking it then affects nothing else.
- Keep Home Assistant backups encrypted, and preferably not on a shared network drive.

---

[← Back to the README](../README.md)
