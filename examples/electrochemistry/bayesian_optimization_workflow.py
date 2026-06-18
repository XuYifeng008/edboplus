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
DEFAULT_OBJECTIVES = ["yield_percent", "selectivity_percent", "charge_F_per_mol"]
DEFAULT_OBJECTIVE_MODE = ["max", "max", "min"]
DEFAULT_BATCH_SIZE = 8
DISPLAY_COLUMNS = [
    "catalyst",
    "catalyst_loading_mol_pct",
    "electrolyte",
    "electrolyte_equiv",
    "benzyl_alcohol_equiv",
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
        "fluorenone_mmol": [1.0],
        "catalyst": ["4-hydroxy-TEMPO", "TEMPO", "4-acetamido-TEMPO"],
        "catalyst_loading_mol_pct": [5, 10, 15],
        "electrolyte": [
            "n-Bu4NClO4",
            "n-Bu4NOAc",
            "n-Bu4NBF4",
            "Et4NClO4",
            "Et4NOAc",
            "Et4NBF4",
        ],
        "electrolyte_equiv": [0.05, 0.10, 0.20],
        "PPh3_equiv": [1.0],
        "benzyl_alcohol_equiv": [1.0, 1.5, 2.0],
        "solvent_ratio": [
            "MeCN:EtOAc=2:8",
            "MeCN:EtOAc=3:7",
            "MeCN:EtOAc=4:6",
            "MeCN:EtOAc=5:5",
            "MeCN:EtOAc=6:4",
            "MeCN:EtOAc=7:3",
        ],
        "solvent_total_mL": [10.0],
    }


def virtual_electrochemistry_result(row: pd.Series, rng: np.random.Generator) -> pd.Series:
    """Generate reproducible demo results; replace these with real measurements."""
    catalyst_bonus = {
        "4-hydroxy-TEMPO": 6,
        "TEMPO": 0,
        "4-acetamido-TEMPO": 10,
    }[row["catalyst"]]
    electrolyte_bonus = {
        "n-Bu4NClO4": 2,
        "n-Bu4NOAc": -2,
        "n-Bu4NBF4": 8,
        "Et4NClO4": 0,
        "Et4NOAc": -4,
        "Et4NBF4": 4,
    }[row["electrolyte"]]
    solvent_score = {
        "MeCN:EtOAc=2:8": -8,
        "MeCN:EtOAc=3:7": -3,
        "MeCN:EtOAc=4:6": 3,
        "MeCN:EtOAc=5:5": 8,
        "MeCN:EtOAc=6:4": 6,
        "MeCN:EtOAc=7:3": 0,
    }[row["solvent_ratio"]]

    loading_penalty = -1.4 * abs(row["catalyst_loading_mol_pct"] - 10)
    electrolyte_penalty = -45 * abs(row["electrolyte_equiv"] - 0.10)
    alcohol_penalty = -8 * abs(row["benzyl_alcohol_equiv"] - 1.5)

    yield_percent = 48 + catalyst_bonus + electrolyte_bonus + solvent_score
    yield_percent += loading_penalty + electrolyte_penalty + alcohol_penalty
    yield_percent += rng.normal(0, 2.0)
    yield_percent = float(np.clip(yield_percent, 0, 100))

    selectivity_percent = 62 + 0.45 * catalyst_bonus + 0.35 * electrolyte_bonus
    selectivity_percent += 0.6 * solvent_score - 3 * max(row["benzyl_alcohol_equiv"] - 1.5, 0)
    selectivity_percent += rng.normal(0, 1.5)
    selectivity_percent = float(np.clip(selectivity_percent, 0, 100))

    charge_F_per_mol = 2.6 - 0.015 * yield_percent + 0.25 * (row["electrolyte_equiv"] == 0.05)
    charge_F_per_mol += 0.18 * (row["solvent_ratio"] in ["MeCN:EtOAc=2:8", "MeCN:EtOAc=3:7"])
    charge_F_per_mol += rng.normal(0, 0.05)
    charge_F_per_mol = float(np.clip(charge_F_per_mol, 0.8, 3.5))

    return pd.Series(
        {
            "yield_percent": round(yield_percent, 1),
            "selectivity_percent": round(selectivity_percent, 1),
            "charge_F_per_mol": round(charge_F_per_mol, 2),
        }
    )


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


def choose_action() -> str:
    menu = {
        "1": ("scope", "Generate the electrochemistry condition space CSV"),
        "2": ("init", "Recommend the first batch of experiments"),
        "3": ("simulate", "Fill priority rows with virtual demo results"),
        "4": ("next", "Recommend the next batch from observed results"),
        "5": ("predictions", "Show the prediction CSV"),
        "6": ("all", "Run the complete demo workflow"),
    }
    print("Choose a workflow step:")
    for key, (_, description) in menu.items():
        print(f"  {key}. {description}")

    choice = input("Enter 1-6: ").strip()
    if choice not in menu:
        raise ValueError("Invalid choice.")
    return menu[choice][0]


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

    action = args.action or choose_action()

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
        parser.error(f"Unsupported action: {action}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
