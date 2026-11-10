---
type: llm
weight: 1
---

Pass if the response only explains the next steps, without claiming to have run a skill, edited files or executed tests. Acknowledging the user's invocation, such as "you just ran /fnl-help", is allowed and is not a claim that the assistant ran a skill. Fail if the response starts doing setup or building, even without claiming completion, or makes any of the prohibited execution claims.
