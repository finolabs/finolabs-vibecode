"""Setup restructure oracle: size limits, the consent inventory, prerequisites and entry forms."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/setup"
REFS = SKILL / "references"
FEATURES = sorted((REFS / "features").glob("*.md"))
MARKDOWN = [SKILL / "SKILL.md", *sorted(REFS.rglob("*.md"))]

# (inventory row, consent sentence, home file under references/ or SKILL.md). Each sentence appears exactly once
# in the whole skill, in its home. Core step 4 (knowledge-base write-back) has no row: it asks nothing new.
INVENTORY = [
    (1, "Move this plugin’s saved settings and records to another folder?", "core.md"),
    (1, "Copy the saved settings and records to the folder shown?", "core.md"),
    (2, "When should other AI helpers join, and should the coding guide start with each session?", "mode.md"),
    (3, "Let the lead AI hand independent tasks to other AI helpers without asking each time?", "mode.md"),
    (3, "Require a handoff decision before the first file edit in a repository?", "mode.md"),
    (4, "Save this list of AI helpers and models for future tasks?", "scan.md"),
    (5, "Save how this computer starts and shares work with other AI helpers?", "features/delegation.md"),
    (5, "Let Antigravity run this exact test command again in this repository without asking?", "features/delegation.md"),
    (6, "Let this plugin check your AI usage limits before sharing work with helpers?", "features/quota.md"),
    (6, "Use the programs at the locations shown to check your AI usage limits?", "features/quota.md"),
    (7, "Who should help check whether task evidence meets a requirement?", "features/roles.md"),
    (8, "Let your AI provider review your saved instructions during setup checks?", "features/roles.md"),
    (9, "Save which AI helpers review code, check safety and watch project progress?", "features/roles.md"),
    (9, "Set up this AI helper to post its own review comments on this repository’s pull requests?", "features/roles.md"),
    (10, "Let this plugin keep a private record of how its skills and helpers are used on this computer?", "features/metrics.md"),
    (11, "Let Antigravity record plugin usage for your private dashboard?", "features/metrics.md"),
    (12, "Show progress from task lists and work records on your private dashboard?", "features/metrics.md"),
    (13, "Show how many Claude, Codex and Antigravity programs are running under your account?", "features/metrics.md"),
    (14, "Choose when Claude Code or Codex shortens a long conversation to make room?", "features/compaction.md"),
    (14, "How many tokens should the conversation reach before it is shortened?", "features/compaction.md"),
    (14, "Save the shown limit for shortening future conversations?", "features/compaction.md"),
    (15, "Set up Antigravity to ask for a fresh session when a saved conversation grows too large?", "features/compaction.md"),
    (15, "Save the shown Antigravity session stop and its size limit?", "features/compaction.md"),
    (16, "Hide this plugin’s local working files from Git’s untracked-file list?", "core.md"),
    (17, "Save these plugin rules for AI sessions in this repository?", "core.md"),
    (18, "How does this repository keep its building plan and task progress?", "core.md"),
    (19, "Link this repository’s dashboard progress to the task records named here?", "features/project.md"),
    (19, "Use this checkbox file to count this repository’s tasks on the dashboard?", "features/project.md"),
    (20, "Show this name for the repository on your private dashboard?", "features/project.md"),
    (21, "Save these instructions for future AI sessions in the scope shown?", "instructions/procedure.md"),
    (22, "Which kinds of work would you like optional helpers for?", "features/companions.md"),
    (23, "Show how you can install this optional helper yourself?", "features/companions.md"),
    (24, "Show how you can install or update this optional review helper yourself?", "features/companions.md"),
]
# Approvals found outside the numbered design inventory. Same home/shape contract.
EXTRA_APPROVALS = [
    ('May the agents choose new tasks from your task list?', REFS / "features" / "afk.md"),
    ('May the agents push their branches and open pull requests?', REFS / "features" / "afk.md"),
    ('May the agents merge pull requests while a lease is live?', REFS / "features" / "afk.md"),
    ('Save the shown away-session settings?', REFS / "features" / "afk.md"),
    ('Save these away settings for this repository?', REFS / "features" / "afk.md"),
    ('Keep the table as shown?', REFS / "afk-decisions.md"),
    ('Let the agents decide this kind of work while you are away?', REFS / "afk-decisions.md"),
    ('Let excerpts of your past decisions go to the judge or another AI provider when agents decide for you?',
     REFS / "afk-decisions.md"),
    ("Start with only the essential setup questions?", SKILL / "SKILL.md"),
    ("Save only the notes shown about this setup?", REFS / "core.md"),
    ("Save the shown helper preferences and coding-guide setting?", REFS / "mode.md"),
    ("Show how the plugin would plan a one-line documentation correction?", REFS / "check.md"),
    ("Explore <the plain-language goal of this feature>?", REFS / "menu.md"),
    ("Draft instructions for how AI helpers should work with you?", REFS / "menu.md"),
    ("Show how much conversation space Claude Code or Antigravity is using?", REFS / "features" / "compaction.md"),
    ("Save the shown command to display and record conversation-space usage?", REFS / "context-reading.md"),
    ("Let <agent family> receive any named runtime settings when it starts?", REFS / "features" / "delegation.md"),
    ("Let <agent family> receive the value of <VARIABLE_NAME> when it starts?", REFS / "features" / "delegation.md"),
    ("Let TypeSafe check task evidence using your service account and approved budget?", REFS / "features" / "roles.md"),
    ("Save this list of checks for this repository?", REFS / "features" / "checks.md"),
]
PREREQUISITES = {
    "delegation": "the agent scan", "quota": "the agent scan", "roles": "the agent scan",
    "metrics": "the plugin's hooks installed", "project": "metrics consent",
    "afk": "nothing", "compaction": "nothing for the native threshold", "companions": "nothing",
    "checks": "a git repository",
}


def frontmatter():
    text = (SKILL / "SKILL.md").read_text()
    head = text.split("---\n")[1]
    return dict(line.split(": ", 1) for line in head.splitlines())


class SizeLimitTests(unittest.TestCase):
    def test_skill_and_features_stay_inside_the_limits(self):
        skill = (SKILL / "SKILL.md").read_text()
        self.assertLessEqual(len(skill.splitlines()), 70)
        self.assertLessEqual(len(skill.encode()), 10000)
        self.assertEqual(len(FEATURES), 9)
        for path in FEATURES:
            text = path.read_text()
            self.assertLessEqual(len(text.splitlines()), 80, path.name)
            self.assertLessEqual(len(text.encode()), 8000, path.name)

    def test_no_line_is_over_600_characters(self):
        for path in [SKILL / "SKILL.md", *FEATURES]:
            for number, line in enumerate(path.read_text().splitlines(), 1):
                self.assertLessEqual(len(line), 600, "%s:%d" % (path.name, number))
        self.assertLessEqual(len(frontmatter()["description"]), 600)

    def test_delegation_asks_project_limit_and_optional_family_caps_with_validator(self):
        text = (REFS / 'features/delegation.md').read_text()
        for sentence in ('How many agent runs may work at the same time in this repository?',
                         'Any per-family caps for claude, codex or antigravity in this repository?',
                         'free text', 'such as 3', '1 to 32', 'share quota pools', 'default of 3',
                         'settings --set parallel=<n>', '--set parallel-caps=<list>',
                         'parallel_slots.py check-config', 'advisory (agent judgment)'):
            self.assertIn(sentence, text)
        self.assertNotIn('5 or fewer', text)
        self.assertNotIn('on this computer?', text)

    def test_bare_run_static_budget(self):
        # Follow the literal references from the bare entry, including conditional beginner
        # and closing material. Companion tables load only in the post-core feature,
        # along with the other command/feature dispatch targets; they are not core loads.
        skill = (SKILL / "SKILL.md").read_text()
        # Before Menu, table rows dispatch explicit commands; prose runs for bare setup.
        entry = "\n".join(line for line in skill.split("## Menu\n", 1)[0].splitlines()
                          if not line.startswith("|"))
        def references(text, base):
            names = re.findall(r"references/[\w/.-]+\.md", text)
            paths = [SKILL / name for name in names]
            paths += [base / name for name in re.findall(r"\]\(([^)#]+\.md)(?:#[^)]*)?\)", text)]
            # Relative code pointers (e.g. instructions/procedure.md) also load text.
            paths += [base / name for name in re.findall(r"`((?:[\w.-]+/)+[\w.-]+\.md)`", text)
                      if not name.startswith("references/")]
            return paths

        pending = references(entry, SKILL)
        loaded = {SKILL / "SKILL.md"}
        while pending:
            path = pending.pop().resolve()
            if path in loaded:
                continue
            self.assertTrue(path.is_relative_to(SKILL), str(path))
            loaded.add(path)
            text = path.read_text()
            pending += references(text, path.parent)
        for name in ("core.md", "scan.md", "mode.md", "work-tracking.md", "interview.md", "plain-language.md"):
            self.assertIn(REFS / name, loaded)
        total = sum(len(p.read_bytes()) for p in loaded)
        self.assertLessEqual(total, 15000, {str(p.relative_to(SKILL)): p.stat().st_size for p in loaded})


class ConsentInventoryTests(unittest.TestCase):
    def test_inventory_questions_have_local_explanations(self):
        # Preferences retain their native choices; approvals also name both outcomes.
        preferences = {2, 7, 18, 22}
        for row, sentence, home in INVENTORY:
            with self.subTest(row=row, sentence=sentence):
                if row in preferences or sentence == 'How many tokens should the conversation reach before it is shortened?':
                    continue  # Preferences and free text do not approve a write or grant.
                following = (REFS / home).read_text().split(sentence, 1)[1]
                # The block must immediately follow this question, in order; a later
                # question's explanation cannot accidentally satisfy this one.
                block = re.match(r'^[^\n]*\nYes: [^\n]+\nNo: [^\n]+\nUndo: [^\n]+(?:\nChoices: [^\n]+)?', following)
                self.assertIsNotNone(block)
                explanation = block.group()
                self.assertIn('Choices:', explanation)
                self.assertRegex(explanation, r'"Yes, [^"\n]+" / "No, [^"\n]+"')
                choices = explanation.split('Choices:', 1)[1].lower()
                for word in ('recommend', 'default', 'preselect'):
                    self.assertNotIn(word, choices)  # approval labels stay neutral

        texts = {path: path.read_text() for path in MARKDOWN}
        for sentence, home in EXTRA_APPROVALS:
            with self.subTest(sentence=sentence):
                hits = [path for path, text in texts.items() for _ in range(text.count(sentence))]
                self.assertEqual(hits, [home])
                following = texts[home].split(sentence, 1)[1]
                self.assertRegex(following, r'^[^\n]*\nYes: [^\n]+\nNo: [^\n]+\nUndo: [^\n]+\nChoices: "Yes, [^"\n]+" / "No, [^"\n]+"')
                extra_choices = following.split('Choices:', 1)[1].split('\n', 1)[0].lower()
                for word in ('recommend', 'default', 'preselect'):
                    self.assertNotIn(word, extra_choices)

    def test_setup_offers_afk_and_no_longer_add_autopilot(self):
        for path in (SKILL / "SKILL.md", REFS / "menu.md", REFS / "features" / "afk.md"):
            text = path.read_text()
            self.assertNotIn("add autopilot", text, path.name)
            self.assertNotIn("autopilot_setup.py", text, path.name)
        feature = (REFS / "features" / "afk.md").read_text()
        self.assertIn("/setup add afk", feature)
        self.assertIn("Only the `## afk` section changes", feature)

    def test_afk_settings_are_separate_and_merge_is_last(self):
        text = (REFS / "features/afk.md").read_text().split("## Project scope")[0]
        questions = re.findall(r'Ask(?: Merge last among the settings)?: "([^"\n]+)"', text)
        # Each permission has its own question; the five limits are accepted together or set in one round.
        self.assertEqual(len(questions), 6)
        self.assertEqual(len(set(questions)), 6)
        self.assertEqual(questions[-1], "May the agents merge pull requests while a lease is live?")
        self.assertIn('"Yes, use these limits" / "No, set each limit"', text)
        # The scope is settled before any rule is asked.
        self.assertLess(text.index("Set away rules for your account (every repository) or only for this repository?"),
                        text.index('Ask: "Which AI apps may run while you are away?"'))
        for key in ("Hosts", "Task choice", "Push and pull requests", "Merge", "Trusted authors",
                    "Lease hours", "Max runs", "Max runtime minutes", "Max actions per hour", "Quota floor percent"):
            self.assertIn(key, text)
        self.assertIn("This is your own decision", text)
        self.assertIn("There is no default for Merge", text)

    def test_afk_project_scope_asks_five_keys_previews_and_writes_after_a_yes(self):
        text = (REFS / "features/afk.md").read_text()
        self.assertIn("## Project scope", text)
        user, project = text.split("## Project scope")
        self.assertIn("inside a repository", project)
        questions = re.findall(r'Ask: "([^"\n]+)"', project)
        self.assertEqual(len(questions), 5, questions)
        for key in ("task-choice", "push-and-pull-requests", "merge", "trusted-authors", "roots"):
            self.assertIn("`%s`" % key, project)
        # Only the keys the user ticks as different are asked; every other key inherits.
        self.assertIn("Should this repository use different away rules than your account?", project)
        self.assertIn("Which rules should differ in this repository?", project)
        self.assertIn("Use my user setting", project)
        self.assertIn("default answer", project)
        self.assertIn("settings --set 'autopilot=", project)
        self.assertIn("--dry-run", project)
        self.assertIn('"Save these away settings for this repository?"', project)
        self.assertLess(project.index("--dry-run"), project.index("Save these away settings for this repository?"))
        for word in ("Hosts", "Lease hours", "user scope only"):
            self.assertIn(word, project)

    def test_afk_stop_table_marks_fixed_rows_and_risks(self):
        feature = (REFS / "features/afk.md").read_text()
        text = (REFS / "afk-decisions.md").read_text()
        self.assertIn("(../afk-decisions.md)", feature)
        self.assertLess(feature.index("afk-decisions.md"), feature.index("Ask Merge last among the settings"))
        rows = re.findall(r"^\| (?!Category)[^|]+\((?P<key>[A-Za-z ]+)\) \| (?P<start>[^|]+) \|(?P<risk>[^|]*)\|$", text, re.M)
        self.assertEqual([key for key, _, _ in rows], [
            "Production", "Real users and customer data", "Unrecoverable deletion", "Messages outside the repository",
            "Tags and releases", "Publishing", "Shared settings", "Recoverable deletion", "Repository comments"])
        for key, start, risk in rows:
            with self.subTest(key=key):
                if key in ("Production", "Real users and customer data"):
                    self.assertEqual(start, "stop, fixed")
                else:
                    self.assertIn(start, ("stop", "decide"))
                    self.assertTrue(risk.strip())  # each move states what could go wrong
        self.assertIn("No move has a default", text)
        self.assertIn("--non-production-target", text)
        self.assertIn("Ask separately, never combined with another question", text)

    def test_every_consent_sentence_appears_once_in_its_home(self):
        texts = {path: path.read_text() for path in MARKDOWN}
        for row, sentence, home in INVENTORY:
            hits = [path for path, text in texts.items() for _ in range(text.count(sentence))]
            self.assertEqual(hits, [REFS / home], "row %d: %r" % (row, sentence))

    def test_inventory_covers_every_row(self):
        self.assertEqual({row for row, _, _ in INVENTORY}, set(range(1, 25)))

    def test_core_read_back_holds_inert_facts_only(self):
        core = (REFS / "core.md").read_text()
        for part in re.findall(r"\*\*Read-back[^\n]*", core):
            for row, sentence, _ in INVENTORY:
                self.assertNotIn(sentence, part, "row %d is in a read-back" % row)
        self.assertIn("Nothing that grants something is in it", core)
        skill = (SKILL / "SKILL.md").read_text()
        for row, sentence, _ in INVENTORY:
            self.assertNotIn(sentence, skill)
        self.assertIn("inert facts only", skill)

    def test_quick_and_beginner_still_ask_the_own_question_rows(self):
        skill = (SKILL / "SKILL.md").read_text()
        sentence = skill.split("In every mode these keep their own question:", 1)[1].split(". In Quick mode", 1)[0]
        for words in ("moving the data root and its copy", "arming `auto` and the auto gate", "filling host config",
                      "each Antigravity test-command grant", "roles and review posting",
                      "the Antigravity hook write", "each instruction-file write"):
            self.assertIn(words, sentence)
        self.assertIn("beginner and Quick included, with no default", skill)

    def test_knowledge_base_step_follows_the_users_access_and_asks_nothing_new(self):
        core = (REFS / "core.md").read_text()
        step = core.split("4. **Knowledge base.**", 1)[1].split("5. **Read-back.**", 1)[0]
        for words in ("through the access those instructions approve", "asks nothing new", "no consent row",
                      "report any write that failed"):
            self.assertIn(words, step)


class PrerequisiteTests(unittest.TestCase):
    def test_each_feature_names_its_prerequisite_first(self):
        for path in FEATURES:
            lines = [line for line in path.read_text().splitlines() if line.strip()]
            self.assertTrue(lines[1].startswith("Needs: "), path.name)
            self.assertIn(PREREQUISITES[path.stem], lines[1], path.name)

    def test_declining_a_prerequisite_ends_the_dependent_without_recording_consent(self):
        for name in ("delegation", "quota", "roles"):
            self.assertIn("declining it ends", (REFS / "features" / (name + ".md")).read_text())
        self.assertIn("declining it ends the dependent feature and never records consent as given",
                      (REFS / "menu.md").read_text())
        self.assertIn("declining it ends them without recording any", (REFS / "features/metrics.md").read_text())
        self.assertIn("leaves this feature pending", (REFS / "features/project.md").read_text())

    def test_declined_is_recorded_distinctly_and_add_asks_again(self):
        skill = (REFS / "menu.md").read_text()
        for words in ("setup_features.py decline <feature> --yes", "a bare run does not offer it again",
                      "that record is not a consent", "`add <feature>` always asks again"):
            self.assertIn(words, skill)

    def test_judge_defaults_to_host_when_roles_is_never_run(self):
        self.assertIn("If `roles` is never run the judge is `host`", (REFS / "features/roles.md").read_text())


class EntryAndVocabularyTests(unittest.TestCase):
    def test_user_invoked_flag_description_and_codex_policy(self):
        meta = frontmatter()
        self.assertEqual(meta["disable-model-invocation"], "true")
        description = meta["description"].lower()
        for group in ("host configuration", "instruction files"):
            self.assertIn(group, description)
        self.assertNotIn("(", meta["argument-hint"].replace('"', "")[:0])
        for word in ("add <feature>", "instructions", "check", "scan", "mode"):
            self.assertIn(word, meta["argument-hint"])
        policy = (SKILL / "agents/openai.yaml").read_text()
        self.assertEqual(policy, "policy:\n  allow_implicit_invocation: false\n")

    def test_three_entry_forms_and_sentence_rules(self):
        skill = (SKILL / "SKILL.md").read_text()
        for words in ("Codex: `$setup <word>`", "| none |", "A plain sentence", "never answers a consent question",
                      "one clarifying question", "never several features at once", "is unverified",
                      "`add <feature>`", "`instructions`", "`check`", "`scan` / `mode [args]`"):
            self.assertIn(words, skill)

    def test_removed_skills_are_gone_and_scripts_moved(self):
        for name in ("fnl-setup-instructions", "fnl-scan-agents", "fnl-set-mode"):
            self.assertFalse((ROOT / "skills" / name).exists(), name)
        for name in ("agent_scan.py", "instructions_write.py", "setup_features.py", "mode.py"):
            self.assertTrue((SKILL / "scripts" / name).is_file(), name)
        self.assertEqual((ROOT / "scripts/instructions_write.py").read_bytes(),
                         (SKILL / "scripts/instructions_write.py").read_bytes())

    def test_vocabulary_is_user_scope_and_project_scope(self):
        for path in [*MARKDOWN, ROOT / "README.md", ROOT / "skills/delegate/references/host-template.md"]:
            text = path.read_text()
            self.assertNotRegex(text, r"(?i)machine scope|scope: machine|machine,? project|machine step|machine consent", path.name)
            self.assertNotRegex(text, r"setup`? (?:\(section [A-G]\)|section [A-G]|Check)|the remembered grants of section A", path.name)
            for old in ("fnl-setup-instructions", "fnl-scan-agents", "fnl-set-mode"):
                self.assertNotIn(old, text, path.name)

    def test_readme_discloses_host_invocation_limit(self):
        text = (ROOT / "README.md").read_text()
        self.assertIn("Codex and Antigravity have no verified equivalent", text)
        self.assertIn("disable-model-invocation: true", text)

    def test_check_reports_features_with_the_three_words(self):
        check = (REFS / "check.md").read_text()
        self.assertIn("exactly one of `configured`, `missing` or `unverified`", check)
        for word in ("roles", "judge", "review posting"):
            self.assertIn(word, check)


class ParityBuildTests(unittest.TestCase):
    def test_parity_builder_packages_the_surviving_setup_skill(self):
        # Execute a copied builder in a synthetic checkout; never rewrite real eval plugins.
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            checkout = base / "checkout"
            (checkout / "scripts").mkdir(parents=True)
            shutil.copy2(ROOT / "scripts/build-parity-plugins.sh", checkout / "scripts")
            shutil.copytree(SKILL, checkout / "skills/setup")
            upstream = base / "upstream"
            grilling = upstream / "skills/productivity/grilling"
            grilling.mkdir(parents=True)
            (grilling / "SKILL.md").write_text("# Grilling fixture\n")
            result = subprocess.run(["bash", str(checkout / "scripts/build-parity-plugins.sh"), str(upstream)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            for path, with_grilling in (("parity-interview-ours/plugins/ours", False),
                                        ("parity-interview-with-grilling/plugins/with-grilling", True)):
                plugin = checkout / "evals" / path
                self.assertEqual((plugin / "skills/setup/SKILL.md").read_bytes(), (SKILL / "SKILL.md").read_bytes())
                self.assertEqual((plugin / "skills/setup/scripts/instructions_write.py").read_bytes(),
                                 (SKILL / "scripts/instructions_write.py").read_bytes())
                self.assertEqual((plugin / "skills/grilling/SKILL.md").is_file(), with_grilling)
                self.assertFalse((plugin / "skills/fnl-setup-instructions").exists())


if __name__ == "__main__":
    unittest.main()
