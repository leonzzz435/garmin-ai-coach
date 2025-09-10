import logging
import os
import subprocess
import sys
import tempfile
import textwrap

logger = logging.getLogger(__name__)

PY_TEMPLATE = r"""
import builtins
import types
import sys

# Allow all imports - no restrictions

# ---- User code
{user_code}

# ---- Extract HTML
import plotly.io as pio
if "fig" not in globals():
    raise RuntimeError("No variable named 'fig' was defined.")
_html = pio.to_html(fig, include_plotlyjs="cdn", full_html=False)
print(_html)
"""


def run_plot_code_get_html(code: str, timeout_s: int = 6):

    user_code = textwrap.dedent(code).strip()
    program = PY_TEMPLATE.format(user_code=user_code)

    with tempfile.TemporaryDirectory() as tmp:
        runner = os.path.join(tmp, "runner.py")
        with open(runner, "w", encoding="utf-8") as f:
            f.write(program)

        try:
            proc = subprocess.run(
                [sys.executable, runner],
                check=False,
                input=b"",
                capture_output=True,
                timeout=timeout_s,
                cwd=tmp,
                env={"PYTHONWARNINGS": "ignore"},  # keep it quiet
            )

            if proc.returncode != 0:
                error_output = proc.stderr.decode("utf-8", "ignore") or proc.stdout.decode(
                    "utf-8", "ignore"
                )
                logger.error(
                    f"Subprocess execution failed with return code {proc.returncode}: {error_output}"
                )
                return {"ok": False, "error": error_output}

            html_output = proc.stdout.decode("utf-8")
            if not html_output.strip():
                return {"ok": False, "error": "No HTML output generated"}

            return {"ok": True, "html": html_output}

        except subprocess.TimeoutExpired:
            logger.error(f"Code execution timed out after {timeout_s} seconds")
            return {"ok": False, "error": f"Code execution timed out after {timeout_s} seconds"}

        except Exception as e:
            logger.error(f"Subprocess execution failed: {e}")
            return {"ok": False, "error": f"Execution failed: {str(e)}"}


class ProductionSecureExecutor:

    def __init__(self, timeout_s: int = 6):
        self.timeout_s = timeout_s
        logger.info(f"Initialized ProductionSecureExecutor with {timeout_s}s timeout")

    def execute_plotting_code(self, code: str) -> tuple[bool, str, str]:
        logger.info("Executing plotting code in secure subprocess")

        result = run_plot_code_get_html(code, self.timeout_s)

        if result["ok"]:
            logger.info("Plotting code executed successfully")
            return True, result["html"], ""
        else:
            logger.warning(f"Plotting code failed: {result['error']}")
            return False, "", result["error"]
