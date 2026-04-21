"""Crew version tracking.

Every EvaluationResult stores this version string.
Bump this when agents.yaml, tasks.yaml, or output_models.py change
in a way that would alter evaluation output.

Versioning format: MAJOR.MINOR.PATCH
  MAJOR → breaking change in output schema
  MINOR → new agent added / prompt significantly revised
  PATCH → minor prompt wording fix
"""

CREW_VERSION = "1.0.0"
