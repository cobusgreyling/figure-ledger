import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from figure_ledger.__main__ import main
from figure_ledger.score import format_table, score_path, score_text

ROOT = Path(__file__).resolve().parents[1]


class ScoreTests(unittest.TestCase):
    def test_honest_fixture(self) -> None:
        report = score_path(ROOT / "transcripts" / "honest.jsonl")
        self.assertEqual([figure.verdict for figure in report.figures], ["sourced", "sourced", "sourced"])
        self.assertEqual([figure.value for figure in report.figures], ["CLM-4418", "4280", "2026-03-14"])
        self.assertEqual(report.integrity, "1.000")

    def test_invented_settlement_mismatches_the_amount(self) -> None:
        report = score_path(ROOT / "transcripts" / "invented.jsonl")
        self.assertEqual([(figure.value, figure.verdict) for figure in report.figures], [("CLM-4418", "sourced"), ("12400", "mismatch")])
        self.assertEqual(report.figures[1].earlier, ("4280",))
        self.assertEqual(report.integrity, "0.500")

    def test_swapped_reference_keeps_the_date_and_invents_a_callback(self) -> None:
        report = score_path(ROOT / "transcripts" / "swapped.jsonl")
        self.assertEqual(
            [(figure.kind, figure.value, figure.verdict) for figure in report.figures],
            [
                ("reference", "AWB-100442", "mismatch"),
                ("date", "2026-04-18", "sourced"),
                ("count", "2 hour", "orphan"),
            ],
        )
        self.assertEqual(report.integrity, "0.333")

    def test_three_fixtures_total(self) -> None:
        reports = [score_path(ROOT / "transcripts" / name) for name in ("honest.jsonl", "invented.jsonl", "swapped.jsonl")]
        table = format_table(reports)
        self.assertIn("TOTAL", table)
        self.assertTrue(table.endswith("8        5        2         1       0.625") or "0.625" in table.splitlines()[-1])
        last = table.splitlines()[-1].split()
        self.assertEqual(last, ["TOTAL", "8", "5", "2", "1", "0.625"])

    def test_currency_spelling_is_the_same_amount(self) -> None:
        report = score_text(
            "\n".join(
                [
                    '{"type":"tool","name":"lookup_claim","output":"amount R4,280.00"}',
                    '{"type":"assistant","text":"The reserve is ZAR 4,280."}',
                ]
            )
        )
        self.assertEqual(report.figures[0].value, "4280")
        self.assertEqual(report.figures[0].verdict, "sourced")

    def test_trailing_currency_code_matches(self) -> None:
        report = score_text(
            "\n".join(
                [
                    '{"type":"tool","name":"quote","output":"fee 12.50 USD"}',
                    '{"type":"assistant","text":"The fee is $12.50."}',
                ]
            )
        )
        self.assertEqual(report.figures[0].value, "12.5")
        self.assertEqual(report.figures[0].verdict, "sourced")

    def test_later_tool_result_does_not_count(self) -> None:
        report = score_text(
            "\n".join(
                [
                    '{"type":"assistant","text":"The reserve is ZAR 4,280."}',
                    '{"type":"tool","name":"lookup_claim","output":"amount ZAR 4280"}',
                    '{"type":"assistant","text":"The reserve is still ZAR 4,280."}',
                ]
            )
        )
        self.assertEqual([figure.verdict for figure in report.figures], ["orphan", "sourced"])

    def test_user_text_is_not_evidence(self) -> None:
        report = score_text(
            "\n".join(
                [
                    '{"type":"user","text":"The reserve is ZAR 4,280."}',
                    '{"type":"assistant","text":"The reserve is ZAR 4,280."}',
                ]
            )
        )
        self.assertEqual(report.figures[0].verdict, "orphan")

    def test_an_earlier_reply_is_not_evidence(self) -> None:
        report = score_text(
            "\n".join(
                [
                    '{"type":"assistant","text":"The reserve is ZAR 4,280."}',
                    '{"type":"assistant","text":"Confirming the reserve is ZAR 4,280."}',
                ]
            )
        )
        self.assertEqual([figure.verdict for figure in report.figures], ["orphan", "orphan"])

    def test_fenced_example_is_not_a_figure(self) -> None:
        report = score_text(
            "\n".join(
                [
                    '{"type":"tool","name":"lookup_claim","output":"amount ZAR 4280"}',
                    '{"type":"assistant","text":"Example:\\n```\\nThe reserve is ZAR 9,999.\\n```\\nThe reserve is ZAR 4,280."}',
                ]
            )
        )
        self.assertEqual([figure.value for figure in report.figures], ["4280"])
        self.assertEqual(report.figures[0].verdict, "sourced")

    def test_invalid_date_is_not_a_figure(self) -> None:
        report = score_text('{"type":"assistant","text":"The incident was on 32 March 2026."}')
        self.assertEqual(report.figures, ())
        self.assertEqual(report.integrity, "n/a")

    def test_month_name_matches_the_iso_date(self) -> None:
        report = score_text(
            "\n".join(
                [
                    '{"type":"tool","name":"lookup_delivery","output":"slot 2026-04-18"}',
                    '{"type":"assistant","text":"Booked for April 18, 2026."}',
                ]
            )
        )
        self.assertEqual(report.figures[0].value, "2026-04-18")
        self.assertEqual(report.figures[0].verdict, "sourced")

    def test_reference_case_does_not_matter(self) -> None:
        report = score_text(
            "\n".join(
                [
                    '{"type":"tool","name":"lookup_delivery","output":"reference awb-882190"}',
                    '{"type":"assistant","text":"Waybill AWB-882190 is booked."}',
                ]
            )
        )
        self.assertEqual(report.figures[0].verdict, "sourced")

    def test_count_plural_matches(self) -> None:
        report = score_text(
            "\n".join(
                [
                    '{"type":"tool","name":"lookup_delivery","output":"callback 2 hour"}',
                    '{"type":"assistant","text":"The driver will call in 2 hours."}',
                ]
            )
        )
        self.assertEqual(report.figures[0].value, "2 hour")
        self.assertEqual(report.figures[0].verdict, "sourced")

    def test_no_amount_in_the_trace_is_an_orphan(self) -> None:
        report = score_text(
            "\n".join(
                [
                    '{"type":"tool","name":"lookup_claim","output":"reference CLM-4418"}',
                    '{"type":"assistant","text":"The settlement is ZAR 12,400."}',
                ]
            )
        )
        self.assertEqual(report.figures[0].verdict, "orphan")

    def test_invalid_json_names_the_line(self) -> None:
        with self.assertRaises(ValueError) as caught:
            score_text("{")
        self.assertIn("inline:1: invalid JSON", str(caught.exception))

    def test_unknown_type_is_an_error(self) -> None:
        with self.assertRaises(ValueError) as caught:
            score_text('{"type":"note","text":"ZAR 1"}')
        self.assertIn("unknown type note", str(caught.exception))

    def test_help_exits_zero(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("sourced", stdout.getvalue())

    def test_unknown_flag_exits_two(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(["--strict"])
        self.assertEqual(code, 2)
        self.assertIn("unknown flag: --strict", stderr.getvalue())

    def test_missing_file_exits_two(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main([str(ROOT / "transcripts" / "missing.jsonl")])
        self.assertEqual(code, 2)
        self.assertIn("missing.jsonl", stderr.getvalue())

    def test_readme_shows_the_checked_in_score(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("TOTAL                       8        5        2         1       0.625", readme)
        self.assertIn("8 figures, 5 sourced, 2 mismatches, 1 orphan.", readme)

    def test_cli_does_not_edit_the_transcript(self) -> None:
        path = ROOT / "transcripts" / "honest.jsonl"
        before = path.read_bytes()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main([str(path)])
        self.assertEqual(code, 0)
        self.assertEqual(path.read_bytes(), before)
        self.assertIn("1.000", stdout.getvalue())
