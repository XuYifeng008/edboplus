"""Command-line EDBO+ workflow for the electrochemistry example.

Run without arguments to choose a step from a simple menu, or pass one of:

    python examples/electrochemistry/bayesian_optimization_workflow.py all
    python examples/electrochemistry/bayesian_optimization_workflow.py scope
    python examples/electrochemistry/bayesian_optimization_workflow.py init
    python examples/electrochemistry/bayesian_optimization_workflow.py simulate
    python examples/electrochemistry/bayesian_optimization_workflow.py next
    python examples/electrochemistry/bayesian_optimization_workflow.py predictions
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = next(
    (path for path in [SCRIPT_DIR, *SCRIPT_DIR.parents] if (path / "edbo").exists()),
    SCRIPT_DIR,
)
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


DEFAULT_SCOPE_FILE = "electrochemistry_scope.csv"
DEFAULT_ROUND0_FILE = "electrochemistry_round0.csv"
DEFAULT_OBJECTIVES = ["yield_percent"]
DEFAULT_OBJECTIVE_MODE = ["max"]
DEFAULT_BATCH_SIZE = 8
DISPLAY_COLUMNS = [
    "benzyl_alcohol_equiv",
    "catalyst",
    "catalyst_equiv",
    "electrode",
    "temperature_C",
    "current_mA",
    "solvent_ratio",
]


def edbo_plus() -> object:
    try:
        from edbo.plus.optimizer_botorch import EDBOplus
    except ModuleNotFoundError as error:
        missing = error.name or str(error)
        raise ModuleNotFoundError(
            f"Missing dependency '{missing}'. Install the EDBO+ environment before running optimization steps."
        ) from error

    return EDBOplus()


def reaction_components() -> dict[str, list[object]]:
    """Return the default electrochemistry search space."""
    return {
        "benzyl_alcohol_equiv": [1.5, 2.0, 2.5],
        "catalyst": ["TEMPO", "TEMPOL"],
        "catalyst_equiv": [0.15, 0.2, 0.25],
        "electrode": ["Al", "Zn", "Sn", "Ag"],
        "temperature_C": [25, 40, 50, 60],
        "current_mA": [25, 40, 55, 70, 85],
        "solvent_ratio": [0.2, 0.3, 0.4, 0.5],
    }


def virtual_electrochemistry_result(row: pd.Series, rng: np.random.Generator) -> pd.Series:
    """Generate reproducible demo results; replace these with real measurements."""
    catalyst_bonus = {
        "TEMPO": 0,
        "TEMPOL": 6,
    }[row["catalyst"]]
    electrode_bonus = {
        "Al": 2,
        "Zn": 0,
        "Sn": 5,
        "Ag": 8,
    }[row["electrode"]]

    alcohol_penalty = -8 * abs(row["benzyl_alcohol_equiv"] - 2.0)
    catalyst_penalty = -40 * abs(row["catalyst_equiv"] - 0.2)
    temperature_penalty = -0.3 * abs(row["temperature_C"] - 50)
    current_penalty = -0.15 * abs(row["current_mA"] - 55)
    solvent_penalty = -30 * abs(row["solvent_ratio"] - 0.4)

    yield_percent = 52 + catalyst_bonus + electrode_bonus
    yield_percent += (
        alcohol_penalty
        + catalyst_penalty
        + temperature_penalty
        + current_penalty
        + solvent_penalty
    )
    yield_percent += rng.normal(0, 2.0)
    yield_percent = float(np.clip(yield_percent, 0, 100))

    return pd.Series({"yield_percent": round(yield_percent, 1)})


def csv_path(workdir: Path, filename: str) -> Path:
    return workdir / filename


def print_table(df: pd.DataFrame, columns: Sequence[str], rows: int = 12) -> None:
    available_columns = [column for column in columns if column in df.columns]
    if not available_columns:
        print(df.head(rows).to_string(index=False))
        return
    print(df[available_columns].head(rows).to_string(index=False))


def create_scope(workdir: Path, filename: str, overwrite: bool) -> pd.DataFrame:
    path = csv_path(workdir, filename)
    if path.exists() and not overwrite:
        print(f"Scope already exists: {path}")
        print("Use --overwrite to regenerate it.")
        return pd.read_csv(path)

    df_scope = edbo_plus().generate_reaction_scope(
        components=reaction_components(),
        directory=str(workdir),
        filename=filename,
        check_overwrite=False,
    )
    print(f"Saved scope to {path}")
    return df_scope


def run_recommendation(
    workdir: Path,
    filename: str,
    objectives: list[str],
    objective_mode: list[str],
    batch_size: int,
    seed: int,
    init_sampling_method: str,
) -> pd.DataFrame:
    path = csv_path(workdir, filename)
    if not path.exists():
        raise FileNotFoundError(f"Cannot find input CSV: {path}")

    suggestions = edbo_plus().run(
        directory=str(workdir),
        filename=filename,
        objectives=objectives,
        objective_mode=objective_mode,
        batch=batch_size,
        columns_features="all",
        init_sampling_method=init_sampling_method,
        seed=seed,
    )
    priority = suggestions.query("priority == 1") if "priority" in suggestions.columns else suggestions
    print(f"\nRecommended experiments from {path}:")
    print_table(priority, [*DISPLAY_COLUMNS, *objectives])
    return suggestions


def simulate_priority_results(
    workdir: Path,
    input_file: str,
    output_file: str,
    objectives: list[str],
    seed: int,
    overwrite: bool,
) -> pd.DataFrame:
    input_path = csv_path(workdir, input_file)
    output_path = csv_path(workdir, output_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Cannot find initialized CSV: {input_path}")
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"{output_path} already exists. Use --overwrite to replace it.")

    df = pd.read_csv(input_path)
    if "priority" not in df.columns:
        raise ValueError("Input CSV has no priority column. Run the init step first.")

    priority_mask = df["priority"] == 1
    if not priority_mask.any():
        raise ValueError("No rows have priority == 1.")

    rng = np.random.default_rng(seed)
    simulated_results = df.loc[priority_mask].apply(
        lambda row: virtual_electrochemistry_result(row, rng),
        axis=1,
    )
    df.loc[priority_mask, objectives] = simulated_results[objectives]
    df.to_csv(output_path, index=False)

    print(f"Saved simulated round results to {output_path}")
    print_table(df.loc[priority_mask], [*DISPLAY_COLUMNS, *objectives])
    return df


def show_predictions(workdir: Path, filename: str, objectives: list[str], rows: int) -> pd.DataFrame:
    path = csv_path(workdir, filename)
    if not path.exists():
        raise FileNotFoundError(f"Cannot find prediction CSV: {path}")

    df = pd.read_csv(path)
    prediction_columns = []
    for objective in objectives:
        prediction_columns.extend(
            [
                f"{objective}_predicted_mean",
                f"{objective}_predicted_std_dev",
                f"{objective}_expected_improvement",
            ]
        )

    print(f"Predictions from {path}:")
    print_table(df, [*DISPLAY_COLUMNS, *objectives, *prediction_columns], rows=rows)
    return df


def run_demo_workflow(args: argparse.Namespace) -> None:
    create_scope(args.workdir, args.scope_file, overwrite=args.overwrite)
    run_recommendation(
        args.workdir,
        args.scope_file,
        args.objectives,
        args.objective_mode,
        args.batch_size,
        args.seed,
        args.init_sampling_method,
    )
    simulate_priority_results(
        args.workdir,
        args.scope_file,
        args.round0_file,
        args.objectives,
        args.simulation_seed,
        overwrite=args.overwrite,
    )
    run_recommendation(
        args.workdir,
        args.round0_file,
        args.objectives,
        args.objective_mode,
        args.batch_size,
        args.seed + 1,
        args.init_sampling_method,
    )
    show_predictions(args.workdir, f"pred_{args.round0_file}", args.objectives, args.rows)


def choose_action() -> str | None:
    menu = {
        "1": ("scope", "Generate the electrochemistry condition space CSV"),
        "2": ("init", "Recommend the first batch of experiments"),
        "3": ("simulate", "Fill priority rows with virtual demo results"),
        "4": ("next", "Recommend the next batch from observed results"),
        "5": ("predictions", "Show the prediction CSV"),
        "6": ("all", "Run the complete demo workflow"),
        "0": (None, "Quit"),
    }
    print("\nChoose a workflow step:")
    for key, (_, description) in menu.items():
        print(f"  {key}. {description}")

    choice = input("Enter 0-6: ").strip()
    if choice not in menu:
        print("Invalid choice. Enter a number from 0 to 6.")
        return choose_action()
    return menu[choice][0]


def run_action(action: str, args: argparse.Namespace) -> None:
    if action == "scope":
        create_scope(args.workdir, args.scope_file, args.overwrite)
    elif action == "init":
        if not csv_path(args.workdir, args.scope_file).exists():
            create_scope(args.workdir, args.scope_file, overwrite=False)
        run_recommendation(
            args.workdir,
            args.scope_file,
            args.objectives,
            args.objective_mode,
            args.batch_size,
            args.seed,
            args.init_sampling_method,
        )
    elif action == "simulate":
        simulate_priority_results(
            args.workdir,
            args.input_file or args.scope_file,
            args.output_file or args.round0_file,
            args.objectives,
            args.simulation_seed,
            args.overwrite,
        )
    elif action == "next":
        run_recommendation(
            args.workdir,
            args.input_file or args.round0_file,
            args.objectives,
            args.objective_mode,
            args.batch_size,
            args.seed + 1,
            args.init_sampling_method,
        )
    elif action == "predictions":
        show_predictions(
            args.workdir,
            args.input_file or f"pred_{args.round0_file}",
            args.objectives,
            args.rows,
        )
    elif action == "all":
        run_demo_workflow(args)
    else:
        raise ValueError(f"Unsupported action: {action}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the electrochemistry EDBO+ workflow from the command line.",
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=["scope", "init", "simulate", "next", "predictions", "all"],
        help="Workflow step to run. Omit this to choose from an interactive menu.",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=SCRIPT_DIR,
        help="Directory where CSV files are read and written.",
    )
    parser.add_argument("--scope-file", default=DEFAULT_SCOPE_FILE)
    parser.add_argument("--round0-file", default=DEFAULT_ROUND0_FILE)
    parser.add_argument(
        "--input-file",
        default=None,
        help="Input CSV for simulate/next. Defaults to scope CSV for simulate and round0 CSV for next.",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="Output CSV for simulate. Defaults to electrochemistry_round0.csv.",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--simulation-seed", type=int, default=42)
    parser.add_argument("--init-sampling-method", choices=["cvt", "lhs", "random"], default="cvt")
    parser.add_argument("--objectives", nargs="+", default=DEFAULT_OBJECTIVES)
    parser.add_argument("--objective-mode", nargs="+", default=DEFAULT_OBJECTIVE_MODE)
    parser.add_argument("--rows", type=int, default=12)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite generated CSV outputs.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.workdir = args.workdir.resolve()
    args.workdir.mkdir(parents=True, exist_ok=True)

    if len(args.objectives) != len(args.objective_mode):
        parser.error("--objectives and --objective-mode must have the same length.")

    if args.action:
        run_action(args.action, args)
        return 0

    while True:
        action = choose_action()
        if action is None:
            print("Bye.")
            return 0
        try:
            run_action(action, args)
        except Exception as error:
            print(f"Step failed: {error}")
        print()


if __name__ == "__main__":
    raise SystemExit(main())
