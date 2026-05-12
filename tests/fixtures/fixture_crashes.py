# A wct test that raises an unhandled exception (distinct from a failing check).
# Used as input to meta-tests verifying that the runner catches crashes and
# reports them as 'errored' without taking down the whole run.
raise RuntimeError("fixture intentionally crashed")
