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
  models.py           PersonProfile, RelationshipFact, InteractionReference,
                      Preference, PreferenceDomain, DeveloperPreferences,
                      PeopleSummary, PeopleLimits
  intelligence.py     PeopleIntelligence (aggregation + record_preference)
```

## Responsibilities

| Capability | Method | Where it comes from |
|---|---|---|
| People identification | `identify_people(text, *, user_id)` | name/alias tokens recorded next to a person's `related_people` memories |
| Relationship facts | `relationships(user_id, *, person_id=None)` | `RELATIONSHIP` memories |
| Interaction history refs | `interactions(user_id, *, person_id=None)` | `INTERACTION` memories (occurred_at, source_event_id) |
| Person profile | `profile(user_id, person_id)` | facts + relationships + interactions about a person |
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

## MVP limitations

- Identification is token-based and only works for names that reached Memory
  (no fuzzy matching, no entity resolution). Identity resolution / merging of
  the `Person` contract is intentionally a later concern.
- Relationship/interaction facts are derived from typed memories only; free-form
  text is not guessed at.
- No ML: preference updates are deterministic writes + conflict resolution.