# Basel rc5 App v2 Scientific Runtime Bundle

Bundle version: `basel_rc5_app_v1`

This generated bundle contains portable scikit-learn Pipeline surrogates for the fixed Basel rc5 scientific context.

Use `manifest.json` as the authoritative inventory. Runtime loading requires only Python, numpy, scikit-learn, and joblib.

The surrogate mapping is conditional on the fixed rc5 context:

`Y = f(grass_irrfrac, paved_albedo | fixed Basel rc5 context)`

Dynamic SuewsSiteContext outputs are intentionally separate and must not replace rc5 training-context quantities.
