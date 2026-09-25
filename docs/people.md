# People Intelligence (Phase 5)

Brain-owned people / relationship / preference knowledge. Identity comes from
the unified Phase 0 `Person` contract (`PersonId`); the Intelligence derives
everything else from Memory Engine records. No second database, no LLM —
deterministic and traceable.

Module: `core/people/`

```
core/people/
  exceptions.py       PeopleError / PeopleValidationError
  ports.py            PeopleMemory (read) + PeopleMemoryWriter (write) protocols
  identification.py   token-based name/alias matching
  models.py           PersonProfile, PersonTimeline, PersonTimelineEntry,
                      PersonSourceTrace, PersonFactDurability,
                      RelationshipFact, InteractionReference, Preference,
                      PreferenceDomain, DeveloperPreferences, PeopleSummary,
                      PeopleLimits
  intelligence.py     PeopleIntelligence (aggregation + record_preference)
```

## Responsibilities

| Capability | Method | Where it comes from |
|---|---|---|
| People identification | `identify_people(text, *, user_id)` | name/alias tokens recorded next to a person's `related_people` memories |
| Relationship facts | `relationships(user_id, *, person_id=None)` | `RELATIONSHIP` memories |
| Interaction history refs | `interactions(user_id, *, person_id=None)` | `INTERACTION` memories (occurred_at, source_event_id) |
| Person profile | `profile(user_id, person_id)` | current active facts + relationships + interactions about a person |
| Person timeline | `timeline(user_id, person_id, *, limit=None)` | chronological active + historical memories, source evidence, durability |
| Known people | `people_summary(user_id)` | everyone referenced across the user's memories, ranked by mentions |
| User preferences | `preferences(user_id)` | all `PREFERENCE` memories |
| Developer preferences | `developer_preferences(user_id)` | `PREFERENCE` memories bucketed by `PreferenceDomain` |
| Persist a preference | `record_preference(user_id, *, name, value, domain?, ...)` | Memory Engine candidate → classify → score → conflict resolution |

`MemoryService` satisfies both ports unchanged, so People Intelligence never
bypasses the Memory Engine (same rule as the Context Engine).

## Deterministic domain detection

Each preference is classified into a `PreferenceDomain`
(`language`, `coding_style`, `testing`, `explanation_detail`, `commit_style`,
`deployment`) — or stays a general (non-developer) preference. Resolution order:

1. explicit `metadata["domain"]` (a `PreferenceDomain` value), else
2. a keyword table over `name + content` (language → testing →
   explanation_detail → commit_style → deployment → coding_style), else
3. `None` → general user preference.

## Preference lifecycle (`record_preference`)

New preferences are stored through the Memory Engine:

- written with `metadata["kind"]="preference"`,
- `metadata["preference"] = "<domain>:<name>"` doubles as the conflict key, so
  re-recording the same preference **supersedes** the previous record instead of
  stacking dead facts (distinct domains never collide), and
- `metadata["preference_name"]` keeps the clean name for reading.

## Integration with the Context Engine

`ContextEngine.build_context` already assembles `developer_preferences`
(`MemoryId` pointers) and `relevant_people` (`PersonId` list) from the same
memories People Intelligence reads — both views agree by construction, and both
are directly usable by Phase 6 Reasoning.

## Reading a preference / a person is always
- bounded (`PeopleLimits`: facts, relationships, interactions, per-domain
  preferences, scan size),
- user-scoped (strict isolation: user A never sees user B's people or
  preferences), and
- traceable back to the `memory_id`s that produced the answer.

## Timeline and provenance

`timeline()` reads `MemoryStatusFilter.ANY`, so superseded, archived and expired
person memories remain inspectable. Results are oldest-first and bounded by
`PeopleLimits.max_timeline_entries` (default/maximum `200`); `total_entries` is
the number of memory rows examined, `truncated` means the requested output cap
was applied, and `scan_truncated` means the internal scan cap may hide older
rows. `person_known` distinguishes a person with no history from a person id
that has never appeared in this user's memory.

Each `PersonTimelineEntry` carries:

- `memory_id`, `memory_type`, lifecycle `status`, statement and validity dates;
- `confidence` and `importance` copied from the memory;
- `durability`: `durable`, `temporary` or `unspecified`;
- `provenance.source`, source event id, correlation id, related event ids and
  bounded evidence metadata. If an oversized source id, correlation id or
  statement is shortened, the corresponding `*_truncated` flag is true and the
  bounded original remains in evidence where possible.

Durability is deliberately deterministic and conservative. Explicit
`metadata["durability"]`, `temporary` or `durable` wins; interactions/observations
are temporary; relationships and explicitly structured employment/location/role
topics are durable; insufficient evidence remains `unspecified`. Core never
turns an unsupported natural-language inference into a permanent fact.

The existing profile remains the current/active view. The timeline is the
historical, inspectable view. Both derive from the same Memory Engine records;
neither owns a second database.


## Naming people and resolving identity

A person only becomes nameable when a name reaches a memory next to their
`person_id`. Two rules cover the whole path:

- **naming** — when a connector names the event subject
  (`subject.person_name` next to a resolved `subject.person_id`), ingestion
  records `metadata["person_name"]` on the memory. `people_summary` then shows
  the name, `profile` labels the person, and `identify_people` can find them in
  ordinary text. A name without a person id is never stored as one.
- **resolution** — `PeopleIntelligence.resolve_person(user_id, name)` returns a
  stable `PersonResolution`:

  | situation | result |
  |---|---|
  | exact normalized name/alias match | existing `person_id`, `created=false` |
  | name already used by two people | `person_id=None`, `ambiguous=true`, both ids in `candidates` |
  | unknown name | deterministic `per_<slug>_<hash8>` id, one identity memory, `created=true` |

Guarantees:

- **no merging, ever** — an ambiguous name reports the candidates and writes
  nothing; the caller decides. Token overlap is a *mention*
  (`identify_people`), never an identity.
- **deterministic** — the id is a digest of `(user_id, normalized name)`, so the
  same name always converges on the same person, and ids are scoped per owner by
  construction. `person.created` fires once, when the identity is first recorded.
- **traceable** — the identity memory carries `kind="person_identity"`, a
  `person_key` conflict key (so a re-record supersedes instead of duplicating),
  `durability="durable"` and `source.provider="people"`. It never counts as a
  mention.
- `BrainService.ingest` calls it for you: a named subject without a
  `person_id` is resolved before ingestion, so the produced memory is linked to
  a real person. An ambiguous name leaves the event ingested but unattached.

Bounds: name ≤ `max_person_name_length` (200), at most `max_person_aliases`
(8) aliases per resolution; invalid input raises `PeopleValidationError`, and a
read-only People Intelligence (no writer) refuses to resolve at all.

Not implemented on purpose: fuzzy or phonetic matching, cross-name merging,
transliteration, and updating the aliases of an already-resolved person (a new
name for a known person is a separate decision, not a silent rewrite).


## MVP limitations

- Identification is token-based and only works for names that reached Memory
  (no fuzzy matching, no entity resolution). Ambiguous names are reported, not
  merged. This slice never merges ambiguous people.
- Relationship/interaction facts are derived from typed memories only; free-form
  text is not guessed at.
- No ML: preference updates are deterministic writes + conflict resolution.