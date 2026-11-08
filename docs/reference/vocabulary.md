# RuleBooks vocabulary

**Draft 0.2 · Editorial reference, not an executable BGSM specification**

This vocabulary gives readers and contributors shared terms for describing game rules, the conditions under which they apply, and what happens when play departs from them. Use the terms alongside the names a source uses. Preserve a game's own label, such as *illegal move*, while using *infraction* for comparisons across games.

The [product model](../product/data-and-versioning.md) governs data boundaries and versions. Governance and enforcement terms support optional rule definitions and interpretation examples; they do not introduce records for actual players, incidents, matches or tournaments. Worked examples illustrate terminology and are not collected game entries or semantic work items.

The [legal and quality crosswalk](vocabulary-analogs.md) records where these terms correspond to established usage in other fields.

## Game identity and representation

| Term | Meaning |
|---|---|
| **Game family** | A discovery grouping for related games or publisher editions; not an executable rules identity. |
| **Publisher edition** | An externally issued edition of a game. Distinct publisher editions have distinct game identities; the publisher's label is not a RuleBooks revision number. |
| **Rulebook edition** | RuleBooks' selected rules and scope for a particular game, such as a named mechanics or procedural profile. |
| **RuleBooks revision** | An immutable revision of our own content record. A correction advances this revision without changing the publisher's edition. |
| **Formalization** | A versioned representation of specified rules under exact BGSM, language and library versions, with explicit coverage. |
| **BGSM** | The Board Game Semantic Model: shared concepts and semantic laws owned by RuleBooks and evolved from concrete game requirements. |
| **Semantic gap** | An evidenced limitation discovered while reviewing actual rules or attempting their representation. An anticipated difficulty alone is not a gap record. |
| **Semantic observation** | The information a formal game makes available to a specified participant or perspective. Distinct from an evidence report about what someone saw. |

## What a provision governs

| Term | Meaning |
|---|---|
| **Provision** | A citable statement that defines, requires, permits, prohibits, recommends, or otherwise governs something. A source clause can contain several provisions. |
| **Game rule** | A provision about the game itself, such as setup, state, available actions, transitions, or outcomes. |
| **Play procedure** | A provision about how participants perform, communicate, record, or commit to actions during play. |
| **Event rule** | A provision about organizing or administering play, such as eligibility, pairings, reporting, or late arrival. |
| **Mechanic** | A recurring pattern in how games work. Piece transformation is a mechanic. A specific game's promotion rule gives it concrete behavior. |
| **Table norm** | A shared expectation about behavior. Its authority comes from the group’s practice or expectations. |
| **House rule** | A provision adopted locally that adds to or changes a ruleset for that table, group, or venue. Record the agreement and its scope when known. |

A topic can run through several kinds of provisions. Table talk might be an explicit action in a deduction game, a prohibited form of assistance at a tournament, or a practice governed by table norms. Classify each provision by what it governs and connect them through the shared topic.

## Authority and applicability

| Term | Meaning |
|---|---|
| **Authority** | The person, group, or body empowered to establish, adopt, or apply a provision in a given context. |
| **Delegated authority** | A power that a governing provision assigns to a role, such as deciding whether a physical card is acceptable at an event. Record the provision that grants it, its scope, and any limits or appeal route. |
| **Source** | The document or other evidence that records a provision. Record its edition and the location of the relevant passage. |
| **Scope** | The game, variant, medium, event, role, or circumstances in which a provision applies. |
| **Effective period** | When the provision governs. Track this separately from when a source was published or RuleBooks recorded it. |
| **Force** | How a provision governs. It may define a game condition, require or prohibit conduct, grant permission, recommend a practice, or delegate a decision. |
| **Default** | A provision or value that applies when no authorized alternative has been selected. |
| **Exception** | A stated condition that changes how an otherwise applicable provision applies. |
| **Authorized deviation** | A departure approved under the applicable procedure for a stated purpose and scope. |
| **Override** | A provision or decision that replaces or changes another provision within a defined scope. |
| **Precedence** | The rule for deciding which provision governs when applicable provisions conflict. |
| **Interpretation** | An explanation of what a provision means. Record whose interpretation it is and what evidence supports it. |
| **Determination** | An authorized decision about a fact or status, such as whether a card is marked or a deck meets eligibility requirements. A ruling can rely on one or more determinations. |
| **Ruling** | A decision applying the governing provisions to a particular situation. |
| **Finality** | The point at which a decision settles an issue under a specified review procedure. Record what it settles and whether it applies to a game, match, event, or wider scope. |

## Governance roles

| Role | What it can decide |
|---|---|
| **Rulemaking authority** | Adopts or amends provisions that govern play within a defined scope. |
| **Format authority** | Sets or updates eligibility requirements for a format, such as which components can be used and in what quantities. |
| **Event organizer** | Selects the applicable format and sets event parameters or local rules where the governing provisions permit it. |
| **Adjudicator** | Interprets provisions, makes determinations, and issues rulings or remedies within the powers assigned to the role. |

One body can fill several roles. Record the role that authorizes each decision. A published revision provides a fixed reference. The rules governing an event may draw on several revisions with different effective dates. A rule can also delegate a decision during play. If that decision affects the game state or result, a formal model can take the authorized ruling as an input and specify its effect.

## Deviations and enforcement

| Term | Meaning |
|---|---|
| **Deviation** | Something that happens outside the expected course of play. It may be a player's action, an equipment failure, or an irregular state. Whether it breaches a provision is a separate finding. |
| **Infraction** | A breach of an applicable provision. Record the conduct and the rule it breaches. Preserve source terms such as *foul*, *violation*, or *illegal move* where they carry a specific meaning. |
| **Mistake** | An inadvertent action or omission. A mistake can be legal, like a poor tactical choice, or it can cause an infraction. |
| **Tactical infraction** | A deliberate breach chosen because its expected cost is worth a perceived advantage. Record intent separately from whether the act breached the rule. |
| **Cheating** | Conduct such as deception, prohibited assistance, or manipulation to obtain an improper advantage. Use the governing definition where one exists. Record allegations and findings separately. |
| **Action rejection** | A system or official prevents an attempted action from taking effect. The governing procedure determines whether the attempt itself has a consequence. |
| **Evidence observation** | An account of what someone saw or what a system recorded in a cited example; distinct from a formal game's participant-visible information. |
| **Finding** | A determination by the authorized decision-maker about what happened or whether a rule was breached. |
| **Call** | An official's recognition of an incident for enforcement under the applicable procedure. |
| **Claim** | A participant's request for a ruling or remedy. The governing procedure may specify who can make it, what evidence is needed, and when the opportunity expires. |
| **Claim window** | The time or interval in play during which a claim can be raised. |
| **Appeal** | A request for authorized review of a ruling already made. |
| **Remedy** | An authorized response that corrects an irregularity or resolves its effect on play. Examples include restoring a position, replaying an action, or deciding that play stands. |
| **Penalty** | A consequence imposed for an infraction, such as loss of time, possession, points, or the game. A response can include both a remedy and a penalty. |
| **Sanction** | An imposed disciplinary or restrictive action. It can include a penalty, warning, suspension, or exclusion. |
| **Disposition** | What ultimately happens to the incident and the game record. Examples include an action standing, a position being restored, or a result being changed. |

When documenting an interpretation example, distinguish the **act**, the **finding**, and the **disposition**. A move may have been illegal, gone unobserved, and remained in the game record after the opportunity for correction closed. If intent is unknown, record it as unknown. A strategy can benefit from an infraction while the provision still prohibits it. This distinction describes rule behavior and supporting examples; it does not require a live incident database.

## Worked examples

**Card legality in Magic.** A deck’s eligibility depends on the format’s card pool and the restrictions effective for that event. In one dated announcement, Wizards banned *The Fantasticar* in Legacy and restricted it in Vintage. Whether a particular physical copy is acceptable is a separate event determination. Oracle provides official card wording, and the Tournament Rules let the Head Judge overrule it if an error is discovered. A floor judge’s ruling can be appealed, and the Head Judge or a designated Appeals Judge can issue the final ruling under that tournament procedure. Keep the format change, the applicable card text, and the event ruling separately citable. [Wizards’ August 10, 2026 announcement](https://magic.wizards.com/en/news/announcements/banned-and-restricted-august-10-2026) · [Magic Tournament Rules, §§1.7, 2.9, 3.3–3.6](https://media.wizards.com/ContentResources/WPN/MTG_MTR_2026_Feb27_EN.pdf)

**An illegal move stands in rapid chess.** Under the FIDE rapid profile in Appendix A.5, an arbiter or opponent can act on the specified illegal-move violations before the opponent makes their next move. If the opponent replies without a claim or intervention, play continues. Later correction requires agreement between the players without arbiter intervention. The disposition is that play stands. The original move is still classified as illegal. [FIDE Laws of Chess, Appendix A.5.2](https://handbook.fide.com/chapter/E012023)

**A foul can be a tactical choice.** In basketball, a player might deliberately commit a foul to stop play, anticipating that the resulting possession or free-throw situation is preferable to letting play continue. Record the act as a foul under the applicable rule, the intent as tactical where supported, and the consequence under that game's penalty conditions. NBA rules assign different consequences depending on the foul and the game situation. A designer can compare those incentives without treating the tactic as permission. [NBA Rule 2, Duties of the Officials](https://official.nba.com/rule-no-2-duties-of-the-officials/) · [NBA Rule 12, Fouls and Penalties](https://official.nba.com/rule-no-12-fouls-and-penalties/)

**Kingmaking can be a pattern of play.** A player whose own chance of winning has disappeared may still determine which opponent wins through a legal action. A group might discourage that choice as a table norm or adopt a specific house rule to constrain it. Record the observed behavior, any applicable provision, and any ruling separately.

## Using and revising the vocabulary

When cataloging a provision, identify **what it governs**, **where it applies**, and **what force it has**. For an infraction or irregularity, also record how it becomes actionable, who decides, and what dispositions are available. Use source terminology for the local label and this vocabulary for comparisons across games.

Treat this vocabulary as a versioned editorial reference. When a definition changes, keep its earlier wording and record the reason for the revision. When a source example falls between categories, record the example and the uncertainty so it can inform the next revision.
