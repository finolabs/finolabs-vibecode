# afk check hook: one shell tokenizer

Status: proposed; design only, no code. The rule change it needs (CLAUDE.md, tenth scoped exception) waits on the owner's decisions below. It supersedes the parked PR 352.

## Why

The afk check hook (`afk-check-hook.md`) has to see every simple command that bash or zsh will run, with its real program name. It also has to see every file a redirect opens. Today no single layer owns that structure. Each layer rebuilds it from a lossy copy made by the layer before:

| Layer | Reads | Loses |
| --- | --- | --- |
| `unquoted_newlines` | raw text | joins continuations, turns newlines into ` ; `, drops comments by a raw-character test |
| `shlex.split` | that text | quote provenance: `;` and `';'` become the same word |
| `unreadable` | raw text | rescans quotes itself to find forms outside the allowlist |
| `glued_operator` (and PR 352's `aligned`) | a second, punctuation-aware shlex pass | compares two lossy splits to guess where operators were |
| `reparsed`, `outside_allowlist`, `bad_program` | flat argv | rebuild command boundaries |
| `afk.py` `commands_of` and `READINGS` | flat argv | rebuild command boundaries again, three ways |
| `afk.py` `open_texts` | flat argv | drops a text value (`-m`, `--body`) and the word after it, whatever that word is |

PR 352 tried to fix the error Fio reported ("the command could not be read" for `ls /tmp; git status`). It made two corrections to the same invariant, and each opened a new hole that Codex verified (log `codex-sol-review-pr352c-last.txt`, head e491d83f):

- `gh pr create --body; env`: the detached `;` is swallowed as the body text, so `env` is never judged. This is a regression; main denies the glued form.
- `true; 2>&1 env`: the program is read as `2`. `sh>out` hides a shell that reads code from stdin.
- These forms are allowed on main today: `printenv>&2`, `cat<.netrc` and `gh>out auth token`.
- Also on main: in `echo x\ #; env`, the escaped space followed by `#` is read as the start of a comment, so `; env` is dropped.

The checkpoint note (`.finolabs/notes/afk-hook-checkpoint-2026-11-18.md`) stopped the local fixes. Its conclusion is that the hook needs one authority for shell structure.

## Invariant

For every Bash command the hook judges under a live lease:

1. Each simple command that bash or zsh, with default options, would run reaches the judgment as its own argv. Program first, after `NAME=value` prefixes and redirects are removed.
2. Each redirect's target that names a file reaches the floor as a path.
3. Anything the tokenizer cannot place under 1 and 2 gets the split message (deny).

## Design

### A. One tokenizer, in the hook

A single pass over the raw command text, written for this purpose in `scripts/afk_check_hook.py`. It replaces `unquoted_newlines`, both shlex passes, `glued_operator`, `unreadable`'s quote tracking and PR 352's `detached` and `aligned`.

It emits a list of **simple commands**. Each one holds:

- `assignments`: the leading `NAME=value` words;
- `words`: the argv, quotes removed, each word tagged with the quoting of every character (unquoted, single, double, ANSI-C, locale);
- `redirects`: `(fd, operator, target)`. The target is a word, or a fd for `>&2` and `<&0`, or a heredoc;
- `separator`: the operator that ends the command (`;`, `&&`, `||`, `|`, `|&`, `&`, newline, end);
- `context`: the depth of subshells `( )` and groups `{ }`, and any compound keyword in front (`if`, `then`, `while`, `do`, `!` and so on), so `commands_of` no longer has to infer them.

Grammar it reads, as bash and zsh agree on it:

- Words: unquoted, `'...'`, `"..."`, `\x` outside quotes, and backslash-newline joining outside single quotes. `$"..."` is read as `"..."`. `$'...'` with no backslash is read as `'...'`.
- Operators: recognised only in unquoted text, by longest match. Control operators: `;`, `&&`, `||`, `|`, `|&`, `&`, newline. Redirect operators: `<`, `>`, `>>`, `>|`, `<>`, `<&`, `>&`, `&>`, `&>>`, `<<`, `<<-`, `<<<`, each with an optional leading fd number glued to it. A quoted `;` is always a word character.
- Comments: `#` starts a comment only at the start of a word, after unquoted whitespace or an operator. `echo x\ #` is one word, `x #`.
- Heredocs: the delimiter word is read with its quoting. The body runs to the delimiter line. See decision 3 for how the body is judged.
- Reserved words in command position (`if then else elif fi while until do done for in { } ! time`). These are structure, not programs. In `for NAME in words`, the list words are data: the floor reads them as paths, never as a command.

Everything the allowlist in `afk-check-hook.md` already denies keeps the split message. The tokenizer checks those rules per character, with the quoting known, instead of rescanning raw text. The rules are: braces, every variable but `$HOME`, special parameters, arithmetic, command and process substitution, zsh `=name`, `(` inside a word, `~+`/`~-`/`~N`, `case`, `function`, `coproc`, the opaque words and an unanchored glob after a directory change. An unbalanced quote, a heredoc with no closing delimiter and a `$'...'` holding a backslash get the split message, as they do today.

### B. Judge each simple command on its own

The hook passes the list, not one flat argv, to `afk.py` through a new `check` input, `--commands-json`. That input is a JSON list of `{argv, redirects}`, where the redirect targets are already word-expanded strings and fd numbers are dropped. The same `classified` code then:

- runs `commands_of` on each argv separately. A text value (`-m`, `--body`, `--title`) is read inside its own command only. When the flag is the last word, it has no value, and nothing after the separator can be taken as its text. That closes `gh pr create --body; env` by construction.
- floors each redirect target as a path, with the hook's existing expansion of `~` and globs. `cat<.netrc`, `cat x<~/.n?trc` and `gh>out auth token` floor (the program is `gh`; `auth` follows it).
- applies the shell rule to each command's own words and redirects. A shell whose words hold no script operand reads stdin and gets the split message, whatever its redirects are. That covers `sh>out`, `sh <file` and `| sh`.
- answers with the most severe answer over all commands, as the flat argv does today, and writes one record of counters, limits, merge pins and approval use per tool call (decision 2).

`--argv-json` stays unchanged for the agent's own `check` calls on Codex and Antigravity, where no hook tokenizes.

### C. What goes away

`unquoted_newlines`, the second shlex pass, `glued_operator`, `PUNCTUATION`/`REDIRECT`/`OPERATOR` and `operators_in`. PR 352's `TRAILING_OPERATOR`, `punctuated`, `detached` and `aligned` are never merged. `reparsed` and `outside_allowlist` shrink to the per-command checks they still own: wrapper flags, `bad_program` and runtime-fed programs. `commands_of` keeps its wrapper and inline-code reading, but under `--commands-json` it gets one command at a time. Its boundary guessing over flat argv stays only for `--argv-json`.

### D. Unchanged

These stay as they are: the lease gate, the off switch, the input cap, the 12-second alarm, fail-closed once live, the own-lease-command exemption (now checked on a single simple command with no redirects), the floor-by-name rule over every word that is not a text value, the in-memory expansion of paths, never answering `allow`, the fixed messages and the rule that nothing is stored, logged or sent.

## Owner decisions

Settled when Fio answers on the pull request. Each has a recommendation; none is settled yet.

1. **Accept the design: one tokenizer in the hook, judging per command.** Recommended. The alternative is to keep patching PR 352 layer by layer, which the checkpoint rule forbids after two failed corrections.
2. **Counters per tool call or per simple command.** Recommended: one record per tool call, counting the kinds that `commands_of` finds over all its commands, as today's flat argv counts them. That keeps the strict limits' meaning, and one Bash call spends at most one one-time approval. Per command would charge `git add x && git commit -m y` twice.
3. **Heredoc body.** Recommended: the body is data for its command, not commands. It is read in two ways. (a) The floor-by-name and floor-by-path rules scan its words, so a credential name in the body still floors. (b) An unquoted-delimiter body also passes the variable and substitution allowlist, since the shell expands it. A shell or `eval` fed by a heredoc keeps the split message. Today each body line is judged as a command. That denies ordinary heredocs, such as a commit message holding `;` or a Python snippet, and still misses nothing (b) catches. The alternative is to keep line-by-line judging: safer by one notch, with more false denials.
4. **Rule text.** Recommended: rewrite the tenth scoped exception's split clause in `CLAUDE.md` to say "a tokenizer that keeps quoting and emits simple commands with their redirects" in place of the shlex, newline and glued-operator wording. Keep every allowlist item. Add that redirect targets reach the floor. This is the record that lets code land ("no code for it lands before this rule is merged").
5. **Bundle the pre-existing fixes.** Recommended: yes. The tokenizer fixes the main-branch holes (`printenv>&2`, `cat<.netrc`, `gh>out auth token`, `echo x\ #; env`) by construction, and the tests name them. Splitting them out would mean patching the layers this spec removes.

## Open, not the owner's

- **zsh differences** the tokenizer must reject rather than read. `!` history expansion is off in non-interactive shells, so it is not a concern. The open items are zsh's `<<<` with no space, `&|` and `&!`, and `>>|`, which the oracle in "Verification" must cover. Owner: the implementer, unblocked by the oracle runs.
- **Interpreters fed by stdin** (`python3 - <<EOF`, `node <<EOF`). These stay under "Not covered", like a script file's content. Changing that is a separate decision.

## Verification

- **Oracle test (the deterministic root-cause test).** A fixed corpus of commands runs under real `bash --noprofile --norc` and `zsh -f`, with `env -i`, a `PATH` holding only stub programs and a temporary working folder. Each stub records its name and argv, and each redirect target is a file in the temporary folder. For every corpus entry, the tokenizer's simple commands (program and argv) and redirect targets must equal what both shells ran and opened. An entry where the shells differ must get the split message. The corpus starts with every case in "Why", every case in `afk-check-hook.md` "Verification" and PR 352's tests. The oracle runs only stubs, never a real program, and reads nothing outside the temporary folder.
- **Hook tests** in `tests/test_afk_check_hook.py`, run through the real script under a real lease:
  - `ls /tmp; git status`, `ls /tmp ; pwd ""`, `git status 2>&1 | head` and a heredoc commit message holding `;` are silent.
  - `gh pr create --body; env`, `git commit -m; env`, `true; 2>&1 env`, `printenv>&2`, `cat<.netrc`, `gh>out auth token`, `echo x\ #; env` and `printf x | sh>out` deny, with `floor` or the split message as the oracle predicts.
  - The present tests stay green, or a changed expectation names the decision behind it.
- **afk.py tests** for `--commands-json`: one record per call, the most severe answer, redirect targets floored, and `--argv-json` behaviour unchanged.
- **Reviews**: Codex code and security reviews of the implementation pull request, with the oracle corpus in the brief.

## Not covered

Unchanged from `afk-check-hook.md`, apart from the heredoc clause, which decision 3 replaces.
