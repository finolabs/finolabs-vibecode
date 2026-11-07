# Companion skills

Recommend missing matches with commands; install nothing. Optional (advisory, agent judgment).

| Skill/source | When | Adds |
| --- | --- | --- |
| `agybird` ([finolabs](https://github.com/finolabs/agybird), MIT) | Claude Code/Codex delegates to Antigravity | Dispatch modes/quota/status; `/fnl-setup add delegation` test grants; never installed in Antigravity |
| `vietnamizer` ([finolabs](https://github.com/finolabs/vietnamizer), MIT) | Vietnamese documents/posts for people | Preserves meaning/voice; excludes agent text/logs/code |
| `typesafe-ai` (TypeSafe) | User chooses external judge in roles | Optional cookbooks; not required for judge calls. `judge.py` owns calls and guards; user key/budget required; fallback: host |
| `diagram-design` ([author](https://github.com/cathrynlavery/diagram-design), MIT) | Architecture/flow/data diagrams | HTML/SVG/PNG, brand profile; Google Fonts requests, no author telemetry |

agybird/vietnamizer: Claude Code `claude plugin marketplace add finolabs/plugins`, then `claude plugin install <skill>@finolabs`; Codex `codex plugin marketplace add finolabs/plugins`, then `codex plugin add <skill>@finolabs`. Others (vietnamizer): `npx skills add finolabs/vietnamizer --skill vietnamizer -a <agent>`.

Diagram-design: Claude Code `/plugin marketplace add cathrynlavery/diagram-design`, then `/plugin install diagram-design@diagram-design`; other hosts `npx skills add cathrynlavery/diagram-design -a <agent>`. Only official source.
