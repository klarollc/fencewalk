# Provenance — reference-case fixture

This fixture is an invention. Marigold Community Food Bank, its town, its
people, its domains and every fact recorded here were made up for Fencewalk;
there is no real-world counterpart and nothing here is derived from a real
engagement.

Earlier public versions of this fixture were different: they were a scrubbed
derivative of a real engagement, with names and identifiers substituted.
That content was retired and replaced wholesale with this fictional case for
that reason.

A test, `tests/test_fixture_reference_case.py`, checks two things: that the
fixture's README states the case is fictional and invented for Fencewalk,
with this file present carrying its retirement note; and that no file in
this directory contains any of the retired fixture's own markers. The scrub
of personal identifiers is not a test: it is a release-gate grep run at
review.
