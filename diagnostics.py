"""Print hardware, runtime and local model information."""

from lumalock.core.diagnostics import diagnostics

if __name__ == "__main__":
    print(diagnostics())
