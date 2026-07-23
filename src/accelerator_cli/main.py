"""Command-line entry point for the vendor-neutral accelerator experience."""
from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from . import commands, lifecycle_commands
from .architecture_advisor import (
    AGENT_TYPES,
    APPLICATION_SHELLS,
    DEPLOYMENT_TARGETS,
    IMPLEMENTATION_PATTERNS,
    ORCHESTRATION_PATTERNS,
)
from .intake import commands as intake_commands
from .operations import record_operation
from .output import render_human
from .protocol import CommandResult
from .repository import RepositoryContext


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="accel",
        description=(
            "Continue an Azure Agentic AI Solution Accelerator engagement "
            "without depending on a specific coding-agent vendor."
        ),
    )
    parser.add_argument("--json", action="store_true", help="emit the versioned JSON contract")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON output")
    parser.add_argument("--verbose", action="store_true", help="include lifecycle detail")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start", help="inspect the repository and show the first valid action")
    sub.add_parser("status", help="show lifecycle status and blockers")
    sub.add_parser("next", help="show the next valid action")
    sub.add_parser("review", help="review current repository changes")

    validate = sub.add_parser("validate", help="run or preview repository validation")
    validate.add_argument("--execute", action="store_true", help="run the commands")
    validate.add_argument("--full", action="store_true", help="include ruff and pyright")

    intake = sub.add_parser("intake", help="manage the local private evidence ledger")
    intake_sub = intake.add_subparsers(dest="intake_command", required=True)
    intake_add = intake_sub.add_parser("add", help="extract and register source documents")
    intake_add.add_argument("paths", nargs="+")
    intake_sub.add_parser("list", help="list registered sources")
    intake_review = intake_sub.add_parser("review", help="review source metadata or text")
    intake_review.add_argument("source_id")
    intake_review.add_argument(
        "--include-text",
        action="store_true",
        help="include local source excerpts in command output",
    )
    intake_review.add_argument(
        "--limit",
        type=int,
        default=50,
        help="maximum chunks to return (1-500)",
    )
    intake_review.add_argument(
        "--offset",
        type=int,
        default=0,
        help="zero-based chunk offset for pagination",
    )
    intake_disclose = intake_sub.add_parser(
        "disclose",
        help="record whether a source may be used in model-assisted workflows",
    )
    intake_disclose.add_argument("source_id")
    intake_disclose.add_argument(
        "disclosure_status",
        choices=("local_only", "approved_for_model", "rejected"),
    )
    intake_disclose.add_argument("--apply", action="store_true")
    intake_requirement = intake_sub.add_parser(
        "requirement",
        help="record and review structured requirements with evidence links",
    )
    requirement_sub = intake_requirement.add_subparsers(
        dest="requirement_command",
        required=True,
    )
    requirement_add = requirement_sub.add_parser("add")
    requirement_add.add_argument("--statement", required=True)
    requirement_add.add_argument("--category", required=True)
    requirement_add.add_argument("--confidence", type=float)
    requirement_add.add_argument(
        "--evidence",
        action="append",
        default=[],
        metavar="SOURCE_ID:CHUNK_ID",
    )
    requirement_add.add_argument("--apply", action="store_true")
    requirement_sub.add_parser("list")
    requirement_decide = requirement_sub.add_parser("decide")
    requirement_decide.add_argument("requirement_id")
    requirement_decide.add_argument(
        "status",
        choices=("proposed", "approved", "rejected", "deferred"),
    )
    requirement_decide.add_argument("--by")
    requirement_decide.add_argument("--note")
    requirement_decide.add_argument("--apply", action="store_true")
    requirement_link = requirement_sub.add_parser("link")
    requirement_link.add_argument("requirement_id")
    requirement_link.add_argument(
        "--type",
        required=True,
        choices=(
            "implementation",
            "quality_eval",
            "redteam",
            "telemetry",
            "ux",
            "decision",
        ),
    )
    requirement_link.add_argument("--target", required=True)
    requirement_link.add_argument("--apply", action="store_true")
    requirement_export = requirement_sub.add_parser("export")
    requirement_export.add_argument("--apply", action="store_true")

    sub.add_parser("discover", help="inspect discovery readiness and required inputs")
    design = sub.add_parser(
        "design",
        help="recommend, review, or approve the Foundry architecture",
    )
    design.add_argument("--agent-type", choices=AGENT_TYPES)
    design.add_argument(
        "--implementation-pattern",
        choices=IMPLEMENTATION_PATTERNS,
    )
    design.add_argument(
        "--orchestration-pattern",
        choices=ORCHESTRATION_PATTERNS,
    )
    design.add_argument("--application-shell", choices=APPLICATION_SHELLS)
    design.add_argument("--deployment-target", choices=DEPLOYMENT_TARGETS)
    design.add_argument("--approved-by")
    design.add_argument("--override-reason")
    design.add_argument("--apply", action="store_true")

    scaffold = sub.add_parser("scaffold", help="preview or create a scenario")
    scaffold.add_argument("--scenario-id", required=True)
    scaffold.add_argument("--no-retrieval", action="store_true")
    scaffold.add_argument("--preserve-evals", action="store_true")
    scaffold.add_argument("--dry-run", action="store_true")
    scaffold.add_argument("--apply", action="store_true")

    environment = sub.add_parser("environment", help="inspect deployment environments")
    environment_sub = environment.add_subparsers(
        dest="environment_command",
        required=True,
    )
    environment_sub.add_parser("list")

    deploy = sub.add_parser("deploy", help="preflight or deploy an environment")
    deploy.add_argument("--env", required=True)
    deploy.add_argument("--region", required=True)
    deploy.add_argument("--target", choices=DEPLOYMENT_TARGETS)
    deploy.add_argument("--acknowledge-preview", action="store_true")
    deploy.add_argument("--dry-run", action="store_true")
    deploy.add_argument("--execute", action="store_true")
    deploy.add_argument("--apply", action="store_true")

    evaluate = sub.add_parser("evaluate", help="run deployed acceptance suites")
    evaluate.add_argument("--api-url", required=True)
    evaluate.add_argument("--execute", action="store_true")
    evaluate.add_argument(
        "--foundry",
        action="store_true",
        help="also run optional Foundry-native relevance and groundedness evaluators",
    )

    uat = sub.add_parser("uat", help="generate or sign UAT artifacts")
    uat_sub = uat.add_subparsers(dest="uat_command", required=True)
    uat_sub.add_parser("report")
    uat_signoff = uat_sub.add_parser("signoff")
    uat_signoff.add_argument("--sponsor", required=True)
    uat_signoff.add_argument("--approver", required=True)
    uat_signoff.add_argument("--apply", action="store_true")

    handover = sub.add_parser("handover", help="generate handover artifacts")
    handover_sub = handover.add_subparsers(dest="handover_command", required=True)
    handover_generate = handover_sub.add_parser("generate")
    handover_generate.add_argument("--env", required=True)
    handover_generate.add_argument("--dry-run", action="store_true")
    handover_generate.add_argument("--apply", action="store_true")
    handover_approve = handover_sub.add_parser("approve")
    handover_approve.add_argument("--approver", required=True)
    handover_approve.add_argument("--apply", action="store_true")

    operate = sub.add_parser("operate", help="day-2 operational workflows")
    operate_sub = operate.add_subparsers(dest="operate_command", required=True)
    operate_sub.add_parser("status")

    migrate = sub.add_parser("migrate", help="initialize additive CLI state")
    migrate.add_argument("--apply", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(_normalize_global_options(parser, raw_argv))
    command = args.command or "status"
    command_key = _command_key(args)
    try:
        context = RepositoryContext.discover()
        result = _dispatch(command, args, context)
    except Exception as exc:  # noqa: BLE001 - CLI boundary converts to a typed failure
        result = _failure_result(str(exc))
    else:
        try:
            record_operation(context, command_key, result)
        except OSError as exc:
            print(
                f"warning: command completed but the local operation journal "
                f"could not be updated: {exc}",
                file=sys.stderr,
            )

    if args.json:
        print(result.to_json(pretty=args.pretty))
    else:
        print(render_human(result, verbose=args.verbose), end="")
    return result.exit_code


def _normalize_global_options(
    parser: argparse.ArgumentParser,
    argv: list[str],
) -> list[str]:
    """Allow output flags before or after any subcommand.

    ``argparse`` normally requires parent-parser options to appear before a
    subparser. Coding agents and humans naturally write both
    ``accel --json status`` and ``accel status --json``.
    """
    global_flags = {"--json", "--pretty", "--verbose"}
    value_options = _value_options(parser)
    selected: list[str] = []
    remaining: list[str] = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--":
            remaining.extend(argv[index:])
            break
        if (
            argument in value_options
            and index + 1 < len(argv)
            and argv[index + 1] in global_flags
        ):
            remaining.append(f"{argument}={argv[index + 1]}")
            index += 2
            continue
        if argument in global_flags:
            selected.append(argument)
        else:
            remaining.append(argument)
        index += 1
    return [*selected, *remaining]


def _value_options(parser: argparse.ArgumentParser) -> set[str]:
    options: set[str] = set()
    for action in parser._actions:
        if action.option_strings and action.nargs != 0:
            options.update(action.option_strings)
        if isinstance(action, argparse._SubParsersAction):
            for child in action.choices.values():
                options.update(_value_options(child))
    return options


def _command_key(args: argparse.Namespace) -> str:
    """Return a value-free journal key that cannot leak customer input."""
    parts = [str(args.command or "status")]
    for attribute in (
        "intake_command",
        "requirement_command",
        "environment_command",
        "uat_command",
        "handover_command",
        "operate_command",
    ):
        value = getattr(args, attribute, None)
        if value:
            parts.append(str(value))
    return ".".join(parts)


def _dispatch(
    command: str,
    args: argparse.Namespace,
    context: RepositoryContext,
) -> CommandResult:
    if command == "scaffold" and args.dry_run and args.apply:
        raise ValueError("--dry-run cannot be combined with --apply")
    if command == "deploy":
        if args.dry_run and (args.execute or args.apply):
            raise ValueError("--dry-run cannot be combined with --execute or --apply")
        if args.apply and not args.execute:
            raise ValueError("--apply requires --execute for deployments")
    if (
        command == "handover"
        and args.handover_command == "generate"
        and args.dry_run
        and args.apply
    ):
        raise ValueError("--dry-run cannot be combined with --apply")
    dispatch: dict[str, Callable[[], CommandResult]] = {
        "start": lambda: commands.next_step(context),
        "status": lambda: commands.status(context),
        "next": lambda: commands.next_step(context),
        "review": lambda: commands.review(context),
        "validate": lambda: commands.validate(
            context,
            execute=bool(args.execute),
            full=bool(args.full),
        ),
        "intake": lambda: _dispatch_intake(args, context),
        "discover": lambda: lifecycle_commands.discover(context),
        "design": lambda: lifecycle_commands.design(
            context,
            agent_type=args.agent_type,
            implementation_pattern=args.implementation_pattern,
            orchestration_pattern=args.orchestration_pattern,
            application_shell=args.application_shell,
            deployment_target=args.deployment_target,
            approved_by=args.approved_by,
            override_reason=args.override_reason,
            apply=bool(args.apply),
        ),
        "scaffold": lambda: lifecycle_commands.scaffold(
            context,
            scenario_id=args.scenario_id,
            no_retrieval=bool(args.no_retrieval),
            preserve_evals=bool(args.preserve_evals),
            apply=bool(args.apply),
        ),
        "environment": lambda: lifecycle_commands.environment_list(context),
        "deploy": lambda: lifecycle_commands.deploy(
            context,
            env=args.env,
            region=args.region,
            target=args.target,
            acknowledge_preview=bool(args.acknowledge_preview),
            execute=bool(args.execute),
            apply=bool(args.apply),
        ),
        "evaluate": lambda: lifecycle_commands.evaluate(
            context,
            api_url=args.api_url,
            execute=bool(args.execute),
            foundry=bool(args.foundry),
        ),
        "uat": lambda: _dispatch_uat(args, context),
        "handover": lambda: _dispatch_handover(args, context),
        "operate": lambda: lifecycle_commands.operate_status(context),
        "migrate": lambda: lifecycle_commands.migrate(
            context,
            apply=bool(args.apply),
        ),
    }
    return dispatch[command]()


def _dispatch_intake(
    args: argparse.Namespace,
    context: RepositoryContext,
) -> CommandResult:
    if args.intake_command == "add":
        return intake_commands.add(context, list(args.paths))
    if args.intake_command == "list":
        return intake_commands.list_sources(context)
    if args.intake_command == "review":
        return intake_commands.review(
            context,
            args.source_id,
            include_text=bool(args.include_text),
            limit=args.limit,
            offset=args.offset,
        )
    if args.intake_command == "disclose":
        return intake_commands.disclose(
            context,
            args.source_id,
            args.disclosure_status,
            apply=bool(args.apply),
        )
    if args.intake_command == "requirement":
        if args.requirement_command == "add":
            return intake_commands.requirement_add(
                context,
                statement=args.statement,
                category=args.category,
                confidence=args.confidence,
                evidence=list(args.evidence),
                apply=bool(args.apply),
            )
        if args.requirement_command == "list":
            return intake_commands.requirement_list(context)
        if args.requirement_command == "decide":
            return intake_commands.requirement_decide(
                context,
                requirement_id=args.requirement_id,
                status=args.status,
                approved_by=args.by,
                note=args.note,
                apply=bool(args.apply),
            )
        if args.requirement_command == "link":
            return intake_commands.requirement_link(
                context,
                requirement_id=args.requirement_id,
                link_type=args.type,
                target=args.target,
                apply=bool(args.apply),
            )
        if args.requirement_command == "export":
            return intake_commands.requirement_export(
                context,
                apply=bool(args.apply),
            )
    raise ValueError(f"Unsupported intake command: {args.intake_command}")


def _dispatch_uat(
    args: argparse.Namespace,
    context: RepositoryContext,
) -> CommandResult:
    if args.uat_command == "report":
        return lifecycle_commands.uat_report(context)
    if args.uat_command == "signoff":
        return lifecycle_commands.uat_signoff(
            context,
            sponsor=args.sponsor,
            approver=args.approver,
            apply=bool(args.apply),
        )
    raise ValueError(f"Unsupported UAT command: {args.uat_command}")


def _dispatch_handover(
    args: argparse.Namespace,
    context: RepositoryContext,
) -> CommandResult:
    if args.handover_command == "generate":
        return lifecycle_commands.handover_generate(
            context,
            env=args.env,
            apply=bool(args.apply),
        )
    if args.handover_command == "approve":
        return lifecycle_commands.handover_approve(
            context,
            approver=args.approver,
            apply=bool(args.apply),
        )
    raise ValueError(f"Unsupported handover command: {args.handover_command}")


def _failure_result(message: str) -> CommandResult:
    from .protocol import Issue, ResultStatus, Stage

    return CommandResult(
        stage=Stage.QUALIFY,
        status=ResultStatus.FAILED,
        summary="The accelerator CLI could not complete the command.",
        blocking_issues=(Issue("cli-failure", message),),
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
