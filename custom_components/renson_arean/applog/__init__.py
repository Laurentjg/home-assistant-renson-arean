"""Reading and parsing the app logs (D-14).

`reader` fetches and splits — that never changes. `ssr` interprets, and is the
brittle half that hangs on the app version. Keeping them apart keeps it obvious
where a failure comes from when `rensonheatpumplogic` jumps a version again.
"""
