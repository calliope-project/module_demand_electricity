# Replacement unit-test suite

This suite is intentionally scoped to **module_demand_electricity responsibilities** after the T-Clean extraction.

It does not re-test generic T-Clean behavior such as gap filling, gap reports, advanced-rule application, external-profile parsing, source construction, generic auxiliary requirements, or provenance algorithms. Those belong in T-Clean.

Covered here:
- Modelblocks execution-plan/batch metadata and JSON loading
- Modelblocks-to-T-Clean configuration translation at the adapter boundary
- module configuration schema
- module/provider schemas
- architecture/environment boundaries

The old cleaning-focused unit tests can be removed rather than ported.


## Current migration signal

`test_default_config_matches_schema` is intentionally retained. If it fails, the
repository's shipped `config/config.yaml` is out of sync with the current
`workflow/internal/config.schema.yaml`; fix the configuration rather than
weakening or removing this test.
