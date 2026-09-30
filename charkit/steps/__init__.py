"""Measurement steps, one file per measuring module (charkit/steps/<module>.py holds the steps of the checks
charkit/<module>.py measures): each a module-level MEASUREMENT_STEPS literal that charkit.registry.steps() reads with ast.
Nothing imports these files, so adding a step never changes a build's code keys (the stages, the hull's stamp). How to
add one: docs/CHARKIT.md, "Registering a QA part or a measurement step"."""
