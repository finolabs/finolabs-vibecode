"""Setup restructure oracle: size limits, the consent inventory, prerequisites and entry forms."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/fnl-setup"
REFS = SKILL / "references"
FEATURES = sorted((REFS / "features").glob("*.md"))
MARKDOWN = [SKILL / "SKILL.md", *sorted(REFS.rglob("*.md"))]

# (inventory row, consent sentence, home file under references/ or SKILL.md). Each sentence appears exactly once
# in the whole skill, in its home. Core step 4 (knowledge-base write-back) has no row: it asks nothing new.
INVENTORY = [
    (1, "Keep this data root, or move it to a folder you name?", "core.md"),
    (1, "Copy the existing data to that folder?", "core.md"),
    (2, "How should I hand work to other AI helpers: manual, suggest, or auto; and should the coding guideline start automatically: on or off?", "mode.md"),
    (3, "Arm auto delegation, where the coordinator hands independent tasks to other agents without asking each time?", "mode.md"),
    (3, "Turn the auto gate on?", "mode.md"),
    (4, "Write this agent inventory section?", "scan.md"),
    (5, "Fill the host config from the `fnl-delegate` template?", "features/delegation.md"),
    (5, "Grant Antigravity this exact test command as a remembered allow-rule?", "features/delegation.md"),
    (6, "When the coordinator is about to delegate, and a reading is older than 15 minutes", "features/quota.md"),
    (6, "Do you confirm these exact executable paths?", "features/quota.md"),
    (7, "Which judge should answer semantic questions: Jev, a small model of your host, or none?", "features/roles.md"),
    (8, "May Check send lines of your instruction files to the judge", "features/roles.md"),
    (9, "Assign these review roles?", "features/roles.md"),
    (9, "Set up review posting for this family?", "features/roles.md"),
    (10, "Record usage metadata, and keep it for how many days?", "features/metrics.md"),
    (11, "Write the Antigravity metrics hook?", "features/metrics.md"),
    (12, "Show project progress on the dashboard?", "features/metrics.md"),
    (13, "Would you like Running now to count processes named claude, codex and agy", "features/metrics.md"),
    (14, "Would you like help setting a native compaction threshold?", "features/compaction.md"),
    (14, "Which token value?", "features/compaction.md"),
    (14, "Apply this compaction plan?", "features/compaction.md"),
    (15, "Would you like a local hook to stop the start of a new turn", "features/compaction.md"),
    (15, "Apply this compaction stop preview?", "features/compaction.md"),
    (16, "Add `.finolabs/` to `.git/info/exclude`?", "core.md"),
    (17, "Write this `## Agent skills` block?", "core.md"),
    (18, "Does this repository use Spec Kit, work records or none?", "core.md"),
    (19, "Save this ledger line?", "features/project.md"),
    (19, "Save this task file line?", "features/project.md"),
    (20, "Set this project label?", "features/project.md"),
    (21, "Write this instruction file?", "instructions/procedure.md"),
]
PREREQUISITES = {
    "delegation": "the agent scan", "quota": "the agent scan", "roles": "the agent scan",
    "metrics": "the plugin's hooks installed", "project": "metrics consent",
    "compaction": "nothing for the native threshold", "review-tools": "nothing",
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
        self.assertEqual(len(FEATURES), 7)
        for path in FEATURES:
            text = path.read_text()
            self.assertLessEqual(len(text.splitlines()), 80, path.name)
            self.assertLessEqual(len(text.encode()), 8000, path.name)

    def test_no_line_is_over_600_characters(self):
        for path in [SKILL / "SKILL.md", *FEATURES]:
            for number, line in enumerate(path.read_text().splitlines(), 1):
                self.assertLessEqual(len(line), 600, "%s:%d" % (path.name, number))
        self.assertLessEqual(len(frontmatter()["description"]), 600)

    def test_bare_run_static_budget(self):
        # SKILL.md plus the references the core path names: core, interview rules, work-tracking look-first.
        names = ["core.md", "interview.md", "work-tracking.md"]
        total = len((SKILL / "SKILL.md").read_bytes()) + sum(len((REFS / n).read_bytes()) for n in names)
        self.assertLessEqual(total, 15000)
        # The scan and mode procedures the core path runs are bounded on their own.
        for name in ("scan.md", "mode.md"):
            self.assertLessEqual(len((REFS / name).read_bytes()), 4000, name)


class ConsentInventoryTests(unittest.TestCase):
    def test_every_consent_sentence_appears_once_in_its_home(self):
        texts = {path: path.read_text() for path in MARKDOWN}
        for row, sentence, home in INVENTORY:
            hits = [path for path, text in texts.items() for _ in range(text.count(sentence))]
            self.assertEqual(hits, [REFS / home], "row %d: %r" % (row, sentence))

    def test_inventory_covers_every_row(self):
        self.assertEqual({row for row, _, _ in INVENTORY}, set(range(1, 22)))

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
        sentence = skill.split("In every mode these keep their own question:", 1)[1].split(". In quick mode", 1)[0]
        for words in ("moving the data root and its copy", "arming `auto` and the auto gate", "filling host config",
                      "each Antigravity test-command grant", "roles and review posting",
                      "the Antigravity hook write", "each instruction-file write"):
            self.assertIn(words, sentence)
        self.assertIn("beginner and quick included, with no default", skill)

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
                      (SKILL / "SKILL.md").read_text())
        self.assertIn("declining it ends them without recording any", (REFS / "features/metrics.md").read_text())
        self.assertIn("leaves this feature pending", (REFS / "features/project.md").read_text())

    def test_declined_is_recorded_distinctly_and_add_asks_again(self):
        skill = (SKILL / "SKILL.md").read_text()
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
        for words in ("Codex: `$fnl-setup <word>`", "| none |", "A plain sentence", "never answers a consent question",
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
        for path in [SKILL / "SKILL.md", REFS / "core.md", REFS / "check.md", *FEATURES]:
            text = path.read_text()
            self.assertNotRegex(text, r"(?i)machine scope|scope: machine|machine,? project|machine step|machine consent", path.name)
            for old in ("fnl-setup-instructions", "fnl-scan-agents", "fnl-set-mode"):
                self.assertNotIn(old, text, path.name)

    def test_check_reports_features_with_the_three_words(self):
        check = (REFS / "check.md").read_text()
        self.assertIn("exactly one of `configured`, `missing` or `unverified`", check)
        for word in ("roles", "judge", "review posting"):
            self.assertIn(word, check)


if __name__ == "__main__":
    unittest.main()
