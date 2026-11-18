# afk check hook: one shell tokenizer

Status: draft; design only, no code. The rule change it needs (CLAUDE.md, tenth scoped exception) waits on the owner's decisions below. It replaces two stopgaps merged on 18/11/2026 while it waits: PR 352 (an operator that ends a word is split off) and PR 357 (`codex exec` at the start of a command is Codex's subcommand, not the shell's `exec`). Revised after the Codex reviews of 421ba5d3, 3ee71ea0, 1749f0c9 and 6ccaf157 (code and security REWORK).

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

PR 352 tried to fix the error the owner reported ("the command could not be read" for `ls /tmp; git status`). It made two corrections to the same invariant, and each opened a new hole that Codex verified (log `codex-sol-review-pr352c-last.txt`, head e491d83f):

- `gh pr create --body; env`: the detached `;` is swallowed as the body text, so `env` is never judged. This is a regression; main denies the glued form.
- `true; 2>&1 env`: the program is read as `2`. `sh>out` hides a shell that reads code from stdin.
- These forms are allowed on main today: `printenv>&2`, `cat<.netrc` and `gh>out auth token`.
- Also on main: in `echo x\ #; env`, the escaped space followed by `#` is read as the start of a comment, so `; env` is dropped.

The checkpoint note (`.finolabs/notes/afk-hook-checkpoint-2026-11-18.md`) stopped the local fixes. Its conclusion is that the hook needs one authority for shell structure.

The afk review of the 18/11 overnight lease counted about 100 hook denials across five repositories, almost all false positives. Most came from the same lossy layers: a `;` or `&&` chain, a quoted `|` inside a grep pattern, a multi-line `python3 -c`, and `codex exec -s` read as the shell `exec`. Those are a second reason to replace the layers, not only to close holes.

## Invariant

For every Bash command the hook judges under a live lease:

1. Each command site that bash or zsh, with default options, could run reaches the judgment as its own entry. An entry holds its assignments, its argv (program first) and its redirects.
2. Each redirect's target that names a file, read or write, reaches both the floor and, in `strict`, the path permission that `check --paths` gives that file.
3. A rule that spans commands is still applied to the call as a whole: a directory change followed by an unanchored glob, a pipe into a shell or into `xargs`, or a heredoc feeding a code reader.
4. Anything the tokenizer cannot place under 1 to 3 gets the split message (deny).

A command site is a place in the text where a command could run, not one execution of it. `false && git status` has two sites and `for x in a b; do git status; done` has one. Every site is judged, whether or not the shell would reach it. A site anywhere inside a loop, its `while` or `until` condition list included, may run any number of times, so a site there that would use a one-time approval, reserve a delegated run or merge is denied.

The intersection is taken over every shell the Bash tool may use on the machine: `/bin/zsh`, `/bin/bash` (3.2 on macOS) and a Homebrew bash when one is installed. The oracle records their versions. A form that any one of them rejects or reads differently gets the split message. `|&`, for example, is a syntax error in bash 3.2.

## Design

### A. One tokenizer, in the hook

A single pass over the raw command text, written for this purpose in `scripts/afk_check_hook.py`. It replaces `unquoted_newlines`, both shlex passes, `glued_operator`, `unreadable`'s quote tracking and PR 352's `detached` and `aligned`.

It emits a list of **command sites**. Each one holds:

- `assignments`: the leading `NAME=value` words, kept verbatim with their quoting. A command with assignments and no program is a site of its own.
- `words`: the argv, quotes removed. Each word is tagged with the quoting of every character (unquoted, single, double, ANSI-C).
- `redirects`: `(fd, operator, target)`. The target is a word, a fd for `>&2` and `<&0`, or a heredoc.
- `separator`: the operator that ends the site.
- `context`: the depth of subshells `( )` and groups `{ }`, the compound construct around the site, and whether it sits in a pipeline after a `|` or `|&`.

The grammar is the **intersection** of bash and zsh with default options, as the oracle confirms it. A form the two shells read differently gets the split message. It is never normalized to one shell's reading.

- **Words.** Unquoted text, `'...'`, `"..."`, `\x` outside quotes, and backslash-newline joining outside single quotes. A `$'...'` with no backslash is read as `'...'`. `$"..."` gets the split message, because bash and zsh expand it differently (`<abc>` against `<$abc>` in Codex's probe).
- **Control operators.** These are recognized only in unquoted text, by longest match: `;`, `&&`, `||`, `|`, `|&`, `&` and newline. zsh's `&|` and `&!` get the split message before they could be read as shorter operators.
- **Redirect operators.** These are `<`, `>`, `>>`, `>|`, `<>`, `<&`, `>&`, `&>`, `&>>`, `<<`, `<<-` and `<<<`. zsh's `>!`, `>>!`, `>&|`, `>>|` and `&>|` get the split message before they could be read as shorter operators.
- **fd numbers.** A fd number is a redirect fd only when it is one unquoted digit, starts a word (after whitespace or an operator) and is glued to the operator that follows. In `printf x2>out`, `x2` is an argument and the redirect has no fd. A run of two or more digits glued to a redirect operator (`12>&1`) gets the split message. bash reads it as a fd, but zsh reads `12` as an argument.
- **Comments.** `#` starts a comment only at the start of a word, after unquoted whitespace or an operator. `echo x\ #` is one word, `x #`.
- **Heredocs.** The delimiter word is read with its quoting, and the body runs to the delimiter line. Decision 3 covers how the body is judged.
- **Reserved words.** These count only when unquoted and in command position: `if then elif else fi`, `while until do done`, `{ }` and `!`. `in` counts only in a `for` header.
- **Supported compound forms.** These are `if ... fi`, `while` and `until ... do ... done`, `for NAME in words; do ... done`, `( ... )` and `{ ...; }`. In a `for` header, `NAME` must be a plain name, and the list words are data that the floor reads as paths.
- **Rejected compound forms.** These get the split message: `for ((`, `for NAME; do` with no `in`, zsh short forms (`for x (a b) cmd`, `repeat`, `foreach`), `select`, `case`, `function`, `coproc` and `[[ ]]`. `[[ ]]` is out because zsh pattern operators differ from bash's.

Everything the allowlist in `afk-check-hook.md` denies today keeps the split message. The tokenizer checks those rules per character, with the quoting known, instead of rescanning raw text. The rules are: braces, every variable except `$HOME` (decision 6 can narrow this), special parameters, arithmetic, command and process substitution, zsh `=name`, `(` inside a word, `~+`/`~-`/`~N`, the opaque words, and an unbalanced quote. A heredoc with no closing delimiter, and a `$'...'` holding a backslash, also keep the split message.

### B. Judge each command site, then the call

The hook passes the list to `afk.py` through a new `check` input, `--commands-json`. It is a JSON list of `{assignments, argv, redirects, repeated}`. `repeated` is true for a site anywhere inside a loop, its condition list included, so `classified` can apply the loop rule without the tokenizer's context. Redirect targets are word-expanded strings, with their operator kept (read, write, append or read-write) and the fd dropped. The same `classified` code then does the following:

- **Assignments.** They are kept on their site, exactly as `commands_hit` and `guard_hit` read them on main through `normalize`. `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=remote.origin.push GIT_CONFIG_VALUE_0=HEAD:refs/heads/main git push origin` keeps its `config_env` guard. A sensitive assignment name still floors. An assignment-only site is judged as main judges a bare `NAME=value`.
- **Text values per site.** `commands_of` runs on each site's argv separately. The site boundary is fixed before any text value is extracted, so `-m`, `--body` and `--title` take a value only inside their own site. When the flag is the site's last word, it has no value, and nothing after the separator can be taken as its text. That closes `gh pr create --body; env` by construction. `text_floor`, the screening of body files, the handling of agent briefs and the inspection of an interpreter's inline code all stay behind that boundary.
- **Redirect targets.** In every mode, each target with a path goes to the floor, using the hook's existing expansion of `~` and globs. `cat<.netrc`, `cat x<~/.n?trc` and `gh>out auth token` all floor; the program is `gh`, and `auth` follows it.

  In `strict`, every target also needs the path permission that `check --paths` gives that file, reads included. That covers the hard-protected names that `strict` keeps (`AGENTS.afk.md*` and the constitution path). `git status > AGENTS.afk.md` and `git status < /tmp/input` deny in `strict`, as both do on main today. In `open`, the ninth scoped exception applies unchanged: neither name is protected, and a target needs only the floor.
- **Shells and code readers per site.** A shell site whose words hold no script operand reads stdin and gets the split message, whatever its redirects are. That covers `sh>out` and `sh <file`.
- **Call-wide rules.** These run over the whole list, nested groups and redirect targets included:
  - a directory change (`cd`, `pushd`, `popd`, `chdir`) anywhere in the call, together with an unanchored glob anywhere in the call: `cd ~ && cat .ne?rc` keeps the split message;
  - a pipe into a shell or `xargs`, anywhere in the call, whatever feeds the pipe; a pipe into any program the `afk.py` tables know as a code reader (`INLINE_FLAGS` and `CODE_FLAGS` programs, `tclsh`, `node`, `python*` and the rest) gets the same split message, so `cat <<'EOF' | node` and `cat <<'EOF' | tclsh` stay denied;
  - a heredoc, `<<<` or `<` that feeds a code reader (decision 3), or that feeds a subshell or group, whose body is then judged line by line.
- **Answer and side effects (decision 2).**
  1. Every site is judged first, and nothing is recorded yet. If any site, or a call-wide rule, denies, the call denies with that answer. Nothing is recorded: no counter, no merge pin and no approval use.
  2. When every site is allowed, the call is recorded once, with the kinds that `commands_of` finds over all sites:
     - The action counter goes up once for the call.
     - Each site that reserves a delegated run, such as a ledger start, reserves its own run, so two starts reserve two runs.
     - Each merge site writes its own pin, as one PR, head and repository triple.
     - Each approval is used only by the one site whose exact subject it names. Two sites that need the same one-time approval deny the second.
     - A site inside a loop (condition or body) that needs an approval, a run reservation or a merge denies, as the invariant says. Its count cannot be known before it runs.
     - Run reservations are summed during judgment, before anything is recorded. If the call's total exceeds the remaining capacity of `project_limit` or the lease limit, the call denies with the limit's code. Only a call that passes as a whole persists its reservations.

`--argv-json` stays unchanged for the agent's own `check` calls on Codex and Antigravity, where no hook tokenizes.

### C. What goes away

These go away: `unquoted_newlines`, the second shlex pass, `glued_operator`, `PUNCTUATION`/`REDIRECT`/`OPERATOR` and `operators_in`. So do the stopgaps merged on 18/11/2026: PR 352's `TRAILING_OPERATOR`, `punctuated`, `detached` and `aligned`, and PR 357's `CODEX_EXEC` exemption, which applies only when the raw command starts with the plain words `codex exec`. Their regression tests stay and must pass against the tokenizer.

`reparsed` and `outside_allowlist` shrink to the per-site checks they still own: wrapper flags, `bad_program` and programs fed by run-time data. They are also read correctly for a subcommand, so `codex exec -s` is no longer taken as the shell `exec`. Their call-wide parts move to the call-wide rules in B.

`commands_of` keeps its reading of wrappers and inline code, but under `--commands-json` it gets one site at a time. Its boundary guessing over flat argv stays only for `--argv-json`.

### D. Unchanged

These stay as they are:

- the lease gate, the off switch, the input cap and the 12-second alarm;
- failing closed once the lease is live;
- the own-lease-command exemption, which applies only to a call with exactly one site, no assignments and no redirects, and keeps today's checks of the interpreter, the resolved script path, the subcommand and the arguments; it never exempts a sibling site;
- the floor-by-name rule (decision 7 can narrow it) and the in-memory expansion of paths;
- never answering `allow`, the fixed messages, and nothing being stored, logged or sent.

## Owner decisions

These are settled when Fio answers on the pull request. Each has a recommendation; none is settled yet.

1. **Accept the design: one tokenizer in the hook, judging per site, with call-wide rules.** Recommended. The alternative is to keep patching PR 352 layer by layer, which the checkpoint rule forbids after two failed corrections.
2. **Accounting.** Recommended: judge every site before recording anything, and on any denial record nothing. Otherwise record the call once, as section B sets out:
   - the action counter once per call;
   - one run reservation per run-reserving site;
   - one merge pin per merge site;
   - an approval used by its exact subject only;
   - a denial for any approval, run or merge site inside a loop, condition included;
   - a capacity check of the call's summed reservations before any is persisted.

   Counting every action per site would charge `git add x && git commit -m y` twice. One record for everything would let one approval cover two runs, drop a second merge's pin or under-reserve repeated starts.
3. **Heredoc, `<<<` and `<` input.** Recommended: the body is data only when its receiver is on a closed list of data readers and every program downstream of it, through pipes, is on the same list. A downstream program that is not on the list, an unknown one included, a wrapper, or a subshell or group in the pipeline makes the body judged line by line. A pipe into a known code reader is also denied call-wide (section B). The list is `cat`, `tee`, `wc`, `head`, `tail`, `sort`, `grep`, `git commit -F -`, `git tag -F -` and `gh ... --body-file -`. Data bodies have their words scanned by the floor-by-name and floor-by-path rules. An unquoted-delimiter body, which the shell expands, also goes through the variable and substitution allowlist. For every other receiver, shells and interpreters included (`node`, `python*`, `ruby`, `perl`, `php`, `deno`, `bun`, `osascript`), the body is judged line by line as commands, as main judges it today. So `node <<'EOF'` with `console.log(process.env)` stays denied, and so does `cat <<'EOF' | node`. The alternative is to treat every body as data. It removes more false denials, but it opens the interpreter hole Codex showed, and it would need the owner to accept a weaker floor.
4. **Rule text and records.** Recommended, all in the PR that lands the code:
   - rewrite the tenth scoped exception in `CLAUDE.md` to describe the tokenizer, its command sites with assignments and redirects, the call-wide rules, redirect targets under the floor and the `strict` path permission, the accounting in decision 2 and the heredoc rule in decision 3, keeping every allowlist item;
   - update `afk-check-hook.md` "Behavior", "Not covered" and "Verification" to match;
   - update [PRIVACY.md](../../PRIVACY.md) "afk check hook" to say that redirect targets are read in memory like other paths, and that the command text is still never stored.

   This is the record that lets the code land ("no code for it lands before this rule is merged").
5. **Bundle the fixes for holes that already exist on main.** Recommended: yes. The tokenizer fixes `printenv>&2`, `cat<.netrc`, `gh>out auth token` and `echo x\ #; env` by construction, and the tests name them. Splitting them out would mean patching the layers this spec removes.
6. **A variable assigned earlier in the same call.** Recommended: yes, in a second step after the tokenizer lands. `S=path; cat $S/x` is the most common false denial in the 18/11 review. The tokenizer can substitute a value assigned earlier in the same call only when every one of these holds:
   - The assignment is an unquoted or single-quoted literal with no expansion.
   - It is a site of its own, not a prefix to a command.
   - It stands at the top level: not in a subshell, group, pipeline, loop or conditional.
   - Only `;` or a newline separates it from the use. A `&&`, `||`, `&` or `|` on the way means it may not run.
   - The variable is bound exactly once in the whole call. No other assignment, `for` header, `read`, `export`, `unset`, `local`, `declare`, `typeset`, `getopts`, `select` or redirect binding names it anywhere in the call, before or after the use. So `S=README; for S in auth; do :; done; gh $S token` keeps the split message.
   - The use is `$S` or `${S}` with no operator.

   Any other variable keeps the split message. `(S=README); cat $S` and `false && S=README; cat $S` therefore stay denied: the shell would read the inherited value. The alternative is to keep `$HOME` as the only variable.
7. **The credential base-name rule.** Recommended: keep today's rule, the "floored in every use" names (such as `printenv` and `pass`) on every word, with one narrow exception. An operand of a data reader that executes nothing is exempt. The readers are `cat`, `head`, `tail`, `wc`, `grep`, `ls`, `stat`, `file` and `sort`, and only their file operands are exempt, not their option values. On 18/11 the rule floored `cat .local-ci/<sha>/pass` and cost an e2e proof; that call becomes silent. `python3 /tmp/pass` and `node --require /tmp/pass -e 0` still floor, because neither program is on the list. The floor-by-path rule still applies to every operand, the exempt ones included. Credential commands with subcommands, and the `CREDENTIAL_PAIRS` entries, keep their reading anywhere after the program.

   The alternative, applying the rule only to words that something will execute, was dropped after review: code-loading options such as `--require` and their attached forms make that set open-ended.

## Open, not the owner's

- **zsh forms beyond those listed in A.** The oracle decides each one: a form either matches both shells or gets the split message. Owner: the implementer.
- **Interpreters fed by a script file** (`node x.js`). These stay under "Not covered", as on main.

## Verification

- **Oracle test (the deterministic root-cause test).** It compares the tokenizer with the two shells on command sites and file openings. The run is isolated:
  - Only corpus entries the tokenizer accepts are run. An entry expected to get the split message, the floor or `unsafe` is checked by the tokenizer and the hook only, never by a shell. That keeps `eval`, `source`, absolute program paths and shell option changes out of execution.
  - Each accepted entry runs under real `bash --noprofile --norc` and `zsh -f`, through `sandbox-exec` with a profile that allows file reads and writes only inside a fresh temporary folder (plus the shell binaries and system libraries it needs) and denies network. It runs under `env -i HOME=<tmp>/home PATH=<tmp>/stubs`, with a CPU and wall-clock limit of 5 seconds. Every program name in the entry must resolve to a stub in `<tmp>/stubs`, otherwise the harness refuses it.
  - Command sites: each stub records its name and argv.
    - Shell builtins (`true`, `false`, `echo`, `printf`, `pwd`, `test`, `[`, `cd`, `pushd`, `popd`, `read`, `export` and the rest) run before a `PATH` lookup, so no stub sees them. The execution corpus therefore names only programs that are not builtins in either shell, such as `ok`, `git`, `gh`, `cat` and `grep` stubs.
    - Entries are straight-line: every site runs exactly once, using `ok &&` in place of `true &&`, and loops have one-word lists.
    - Builtins, directory changes, conditional sites and repeated sites are covered by structure tests, where the tokenizer's site list for an entry must equal a hand-written expectation, and by the hook tests below.
  - File openings: each output target is a path in the temporary folder, checked by its existence after the run. Each input target is a named pipe that the harness opens for writing without blocking, so it records whether a reader opened it. `cat <a <b` therefore shows both openings.
  - An entry where bash and zsh differ in sites or openings must get the split message.
  - The corpus starts with every case in "Why", every case in `afk-check-hook.md` "Verification", PR 352's tests and the false denials from the 18/11 review.
- **Hook tests**, in `tests/test_afk_check_hook.py`, run through the real script under a real lease:
  - These are silent: `ls /tmp; git status`, `ls /tmp ; pwd ""`, `git status 2>&1 | head`, `grep -E "a|b" f`, `codex exec -s read-only x`, and a heredoc commit message holding `;` fed to `git commit -F -`.
  - These deny with `floor` or the split message, as the oracle predicts: `gh pr create --body; env`, `git commit -m; env`, `true; 2>&1 env`, `printenv>&2`, `cat<.netrc`, `gh>out auth token`, `echo x\ #; env`, `printf x | sh>out`, `cd ~ && cat .ne?rc`, `node <<'EOF'` with `process.env`, and `$"abc"`.
  - The assignment-guard case denies: `GIT_CONFIG_COUNT=1 ... git push origin`.
  - In `strict`, `git status > AGENTS.afk.md` and `git status < /tmp/input` deny. In `open`, `git status > AGENTS.afk.md` is silent, as the ninth exception says.
  - `printf x 12>&1` gets the split message.
  - With one outstanding approval, `for x in a b; do make task; done` and `while make task; do git status; done` deny. Two ledger starts in one call reserve two runs, and deny when only one run remains. `cat <<'EOF' | node` with `process.env` and `cat <<'EOF' | tclsh` get the split message. A loop site's entry carries `repeated: true`. `S=README; for S in auth; do :; done; gh $S token` keeps the split message under decision 6.
  - Under decision 6, `(S=README); cat $S` and `false && S=README; cat $S` keep the split message. Under decision 7, `cat .local-ci/x/pass` is silent, while `python3 /tmp/pass` and `node --require /tmp/pass -e 0` floor.
  - The present tests stay green, or a changed expectation names the decision behind it.
- **afk.py tests** for `--commands-json`:
  - a denied site records nothing;
  - an allowed call records counters once, writes one pin per merge site, and uses an approval for its exact subject only;
  - redirect targets are floored and, in `strict`, path-checked;
  - `--argv-json` behaves as before.
- **Reviews**: Codex code and security reviews of the implementation pull request, with the oracle corpus in the brief.

## Not covered

Unchanged from `afk-check-hook.md`, apart from the heredoc clause, which decision 3 replaces.
