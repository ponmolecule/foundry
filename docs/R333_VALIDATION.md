# r333 validation

Compared with r332 b1753b0: 119 modules, 101 passing, the same 18 baseline failing modules. No new failures. Full failure list is retained in R332_VALIDATION.md.

Five complete public results are byte-identical with nothing stripped; all three pinned result identities pass. A synthetic existing external-tax engagement also has byte-identical full public output.

Targeted engine tests cover use of the configured 27% rate, changing the existing rate to 19%, monthly/quarterly rate invariance, invalid rates, scalar audit units, absence of new operands in unmodified external rules, and continued compatibility with an existing input named tax_rate. UI tests cover visible rate value, preservation of entered sources, mode switching and inline-script syntax. git diff --check passes. No browser rendering is claimed.

The engine operand validates a finite decimal in [0,1]; the pre-existing whole-configuration tax-rate range validation remains unchanged and continues to apply.
