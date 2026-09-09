# Configuration

This module is configured through `config/config.yaml`. Gap filling and data-quality evaluation both use tclean, while this document describes their Modelblocks-facing configuration.

The configuration schema is intentionally strict: malformed or unsupported configuration should fail validation rather than silently falling back to defaults.

Useful references are:

- [`config/config.yaml`](./config.yaml): example configuration;
- [`workflow/internal/config.schema.yaml`](../workflow/internal/config.schema.yaml): authoritative configuration schema;
- [`workflow/internal/source_registry.yaml`](../workflow/internal/source_registry.yaml): available demand providers and their metadata;
- [`INTERFACE.yaml`](../INTERFACE.yaml): module input/output interface;
- [`tests/integration/test_config.yaml`](../tests/integration/test_config.yaml): a richer integration configuration;
- [`tests/integration/resources/user/external_profiles`](../tests/integration/user/external_profiles): example of an external profile.
- [`tests/integration/Snakefile`](../tests/integration/Snakefile): example module import.

## Temporal scope

`temporal_scope` defines the regular target time grid used for demand cleaning.

```yaml
temporal_scope:
  start: "2017-01-01"
  end: "2017-01-03"
  frequency: "1h"
```

The grid follows a half-open interval:

```text
[start, end)
```

so `start` is included and `end` is excluded.

The period length must be an integer multiple of `frequency`. The `start` timestamp also anchors the grid phase, so timestamps used by provider data, auxiliary data, and external profiles must align with the configured grid.

Date-only timestamps represent midnight. Date-time strings may be used when the grid needs a non-midnight start or another explicit offset.

## Demand sources

`load_sources` selects the national demand providers and defines their priority.

```yaml
load_sources:
  - entsoe
  - neso
  - entsoe_power_statistics
  - opsd
```

Available identifiers are:

- `entsoe`: ENTSO-E Transparency Platform API. The module declares availability from 2005-01-01 onward; a valid ENTSO-E API token is required when this source is configured;
- `entsoe_power_statistics`: official ENTSO-E Power Statistics historical archive, currently integrated for 2019–2025; no API token is required;
- `neso`: National Energy System Operator historic demand, restricted to Great Britain (`GBR`);
- `opsd`: Open Power System Data, with module-declared coverage from 2005-01-01 up to, but not including, 2019-03-01.

Sources are combined in the listed order. When more than one provider supplies a value for the same country and timestamp, the higher-priority provider is retained.

The authoritative list of provider identifiers and source metadata is [`workflow/internal/source_registry.yaml`](../workflow/internal/source_registry.yaml). Its `temporal_scope` bounds use the same half-open `[start, end)` convention as the model time grid. An omitted bound means no restriction is declared in that direction, and omitted or empty `contexts` means no context restriction is declared.

## Data quality

Data-quality testing is configured separately from gap filling. Tests are diagnostic: they identify suspicious observations, profiles, or source disagreements and record evaluation limitations, but they do not change the processed demand values.

The test definitions use the `tclean.data_quality` configuration contract. The module validates those definitions before the expensive evaluation step and then maps Modelblocks demand data into the named sources expected by tclean. Method-level fields, value specifications, failure semantics, and contextual-reference details are documented in tclean's `docs/data_quality.md`; this section focuses on the module-specific configuration behaviour.

A representative configuration can contain tests such as:

```yaml
data_quality:
  - name: non_negative
    method: range
    minimum:
      value_mode: fixed
      value: 0

  - name: unusual_level
    method: contextual_level
    reference_orders:
      - period: 7D
        radius: 4
      - period: 1Y
        radius: 2
    robust_deviation_threshold: 6

  - name: source_disagreement
    method: source_disagreement
    difference_mode: relative
    threshold:
      value_mode: fixed
      value: 0.1
```

The examples above illustrate the module shape rather than prescribing universally appropriate thresholds. Threshold choice remains a modelling decision and should be adapted to the target data and purpose of the quality check.

### Data-quality sources

The module supplies the following source names to tclean data-quality evaluation:

- `processed_demand`: the combined national demand after the configured gap-filling stage. When `gap_filling.mode` is `"off"`, this is the combined but unfilled demand series;
- each configured provider in `load_sources`, such as `entsoe`, `neso`, `entsoe_power_statistics`, or `opsd`, where that provider has prepared data for the run.

For ordinary tests, omitting `sources` makes `processed_demand` the focal source by default. A test can explicitly select one or more available source names when a provider-specific diagnostic is required.

`source_disagreement` deserves particular attention. In tclean, `sources` selects the **focal** source or sources to test; the other supplied sources remain available as peer evidence. In this module, the usual pattern is therefore to evaluate `processed_demand` against the underlying configured providers. For example:

```yaml
- name: source_disagreement
  method: source_disagreement
  sources:
    - processed_demand
  difference_mode: relative
  threshold:
    value_mode: fixed
    value: 0.1
```

Because `processed_demand` is the module default focal source, the explicit `sources` selector can be omitted when that is the intended target. At each country/timestamp, tclean uses the available non-focal provider values as peers; missing provider coverage can therefore make some observations not evaluable without invalidating the configuration itself.

### Countries and ordered tests

The optional tclean `contexts` selector corresponds to the country contexts present in the prepared national-demand frames. It can be used to restrict a test to selected countries.

Data-quality tests are ordered and names must be unique. Earlier failures can affect the eligible reference population of later reference-based tests. Tclean's `include_failed_periods_from` option can explicitly retain failures from named **preceding** tests when that is appropriate. Forward references are invalid.

This ordering is especially relevant for derived thresholds and the contextual methods, where obviously invalid observations identified by an earlier test would otherwise contaminate later reference evidence.

### Contextual tests and reference periods

`contextual_level` and `contextual_profile` compare the focal demand with analogous historical observations or profiles defined by `reference_orders`. Fixed periods such as `7D` and calendar-aware periods such as `1Y` have distinct semantics; `1Y` is a calendar shift rather than a shorthand for `365D`.

For the full reference-lattice, robust-deviation, predictive-probability, and profile-normalisation semantics, refer to tclean's data-quality documentation rather than duplicating those rules here.

### Runtime

Simple pointwise tests are generally quick. Reference-heavy tests can take longer because they construct and evaluate historical comparison sets, and `source_disagreement` must also align peer-provider observations. On long histories covering many countries, `contextual_level`, `contextual_profile`, and cross-source evaluation can take **a few minutes**. This is expected and is substantially different from an hours-long or stalled workflow.

### Data-quality outputs

The evaluation produces two structured tables:

- `load_data_quality_failures.parquet`: contiguous periods where a configured test failed;
- `load_data_quality_issues.parquet`: warnings and `not_evaluable` periods where valid configuration could not be fully evaluated from the available evidence.

The workflow also produces a PDF data-quality diagnostic for visual inspection of failures on `processed_demand` as part of the normal module workflow.

## Gap filling

Gap handling is configured below `gap_filling`.

```yaml
gap_filling:
  mode: basic
```

Three modes are available:

- `"off"`: no gap filling. Quotation marks are required because YAML may interpret an unquoted `off` as the boolean value `false`;
- `basic`: apply deterministic basic rules in configured order;
- `advanced`: run basic cleaning first and then apply configured advanced rules that are active for the current target countries and time grid.

## Basic gap filling

Basic rules are listed under `gap_filling.basic.rules`.

```yaml
gap_filling:
  mode: basic

  basic:
    rules:
      - name: interpolate_short_gaps
        method: linear_interpolation
        max_gap: 3h

      - name: average_adjacent_weeks
        method: average_periods
        max_gap: 326h
        source_offsets:
          - -7d
          - 7d

      - name: copy_previous_week
        method: copy_periods
        max_gap: 168h
        source_offset: -168h
        require_complete_source: true

      - name: copy_following_week
        method: copy_periods
        max_gap: 168h
        source_offset: 168h
        require_complete_source: true
```

Rules are applied sequentially. Values filled by an earlier rule are therefore available to later rules.

Each rule requires a unique, descriptive `name`. Rule names are retained in cleaning provenance and diagnostic outputs.

### `linear_interpolation`

Interpolates across missing periods up to `max_gap`.

```yaml
- name: interpolate_short_gaps
  method: linear_interpolation
  max_gap: 3h
```

### `average_periods`

Uses the mean of corresponding values from one or more offset periods.

```yaml
- name: average_adjacent_weeks
  method: average_periods
  max_gap: 326h
  source_offsets:
    - -7d
    - 7d
```

In this example, corresponding values one week before and one week after the gap are averaged.

### `copy_periods`

Copies corresponding values from a configured offset period.

```yaml
- name: copy_previous_week
  method: copy_periods
  max_gap: 168h
  source_offset: -168h
  require_complete_source: true
```

A negative `source_offset` uses an earlier period; a positive offset uses a later period.

`require_complete_source: true` requires the source period needed for the copy to be complete before that rule can fill the target gap.

## Advanced gap filling

Advanced mode separates two concepts:

1. **sources** describe how an advanced profile is obtained;
2. **rules** describe the target country, period, scope, and source to apply.

This keeps reusable source definitions separate from their application.

The overall structure is:

```yaml
gap_filling:
  mode: advanced

  basic:
    rules: [...]

  advanced:
    auxiliary_data:
      basic_cleaning:
        enabled: true

    sources:
      example_source:
        method: construct_from_sources
        periods: [...]

    rules:
      - name: example_rule
        country: ALB
        start: "2017-01-01"
        end: "2017-01-03"
        scope: overwrite
        source: example_source
```

### Active and inactive rules

Advanced rules may remain in a reusable configuration even when they do not apply to a particular run.

A rule is **active** when:

- its target country is part of the demand being processed; and
- its target interval overlaps the configured target time grid.

A rule outside the current countries or time grid is **inactive** and does not trigger auxiliary-data acquisition or profile construction.

Activity is determined from target scope, not from whether a matching gap happens to remain after basic cleaning. In particular, a `fill_gaps` rule can be active even when there is ultimately nothing for it to fill.

All configured rules must still be valid according to the schema. Inactivity does not make invalid configuration acceptable.

### Rule scopes

Two scopes are supported:

- `fill_gaps`: replace missing target values only;
- `overwrite`: replace target values throughout the rule period.

### Advanced periods

Advanced target and source periods follow the same half-open convention as the model grid:

```text
[start, end)
```

Source periods used to construct a target profile must have the temporal length required by the target construction.

## Advanced source: `construct_from_sources`

A `construct_from_sources` source builds a profile from one or more configured country-period profiles.

```yaml
advanced:
  sources:
    alb_from_gbr_alb_winter:
      method: construct_from_sources
      periods:
        - country: GBR
          start: "2024-01-01"
          end: "2024-02-01"
          weight: 1

      scaling:
        method: match_total
        periods:
          - country: ALB
            start: "2024-01-01"
            end: "2024-02-01"
            weight: 1
```

Each `periods` entry identifies:

- `country`;
- `start`;
- `end`;
- `weight`.

Weights are relative contributions and must be finite and positive.

Multiple source periods can be combined. Their relative weights determine their contribution to the constructed profile.

### Scaling constructed profiles

A constructed profile may optionally be rescaled.

The currently configured scaling strategy is:

```yaml
scaling:
  method: match_total
  periods:
    - country: ALB
      start: "2024-01-01"
      end: "2024-02-01"
      weight: 1
```

`match_total` uses the configured scaling periods to align the overall energy level of the constructed profile with a more representative reference.

Scaling periods can require auxiliary demand data outside the main target grid; the workflow includes them when compiling acquisition requirements.

## Advanced source: `external_profile`

An `external_profile` source reads a user-supplied CSV. By default, external profiles are resolved from `resources/user/external_profiles/`. This location can be re-wired through the `external_profiles` pathvar when importing the module.

```yaml
advanced:
  sources:
    alb_external:
      method: external_profile
      file: alb_external.csv
```

The target country, period, and application scope belong to the **rule**, not to the source:

```yaml
advanced:
  rules:
    - name: use_alb_external_profile
      country: ALB
      start: "2022-01-01 00:00"
      end: "2022-01-08 00:00"
      scope: overwrite
      source: alb_external
```

External profile CSVs use the generic T-Clean column contract:

```csv
timestamp,value
2022-01-01T00:00:00Z,723.0
2022-01-01T01:00:00Z,716.0
```

The profile must use valid, unique timestamps aligned with the target grid, and numeric non-missing values. Sparse profiles are permitted where supported by the configured rule/application behavior.

## Explicitly leaving values missing

Advanced configuration can explicitly retain unresolved values rather than fabricate a profile. This is useful when missing data is known and accepted.

Consult the authoritative configuration schema for the exact `leave_missing` source/rule form supported by the current module version.

## Auxiliary data

Advanced constructed profiles can require demand observations from countries or periods outside the main target grid.

Auxiliary behavior is configured under:

```yaml
advanced:
  auxiliary_data:
    basic_cleaning:
      enabled: true
```

When enabled, the configured basic cleaning rules are also applied to auxiliary demand before it is used in advanced profile construction.

The module determines auxiliary acquisition requirements only for **active** advanced rules. Provider acquisition and preparation remain Modelblocks responsibilities; generic planning and cleaning behavior is delegated to T-Clean.

## End-to-end tested example

For a complete configuration used by the integration workflow, see
[`tests/integration/test_config.yaml`](../tests/integration/test_config.yaml).

This configuration is exercised by the integration test suite and therefore
serves as the canonical end-to-end example. The examples above are intentionally
focused on individual configuration features.

## Validation

Configuration is checked in two layers:

1. the YAML schema checks structure, permitted values, required fields, and basic types;
2. semantic validation checks constraints that depend on relationships between fields, such as time-grid alignment, unique rule/source names, valid source references, compatible advanced periods, valid ordered data-quality tests, data-quality source selectors, and references to preceding quality-test names.

Invalid configuration should be corrected at source rather than handled through silent fallbacks.

For the complete accepted configuration contract, refer to [`workflow/internal/config.schema.yaml`](../workflow/internal/config.schema.yaml).
