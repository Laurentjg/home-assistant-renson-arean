"""API layer for the OpenMotics gateway on the Brain module.

`models` and `endpoints` are free of Home Assistant and aiohttp imports so they
can be tested against recorded gateway responses; `client` does the I/O.
"""
