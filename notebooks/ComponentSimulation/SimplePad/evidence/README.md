# SimplePad teaching observations

These are public synthetic, owner-derived observations from the four canonical
SimplePad workflows, not measured device properties. `run_set.json` binds the
native receipts and exact runtime identities; `results.csv` contains scalar
quantities. Raw sealed run folders are retained by their custodian and are not
published here. Manual re-analysis requires obtaining those exact artifacts.

| Branch | Observed quantity | Result reading |
| --- | --- | --- |
| Palace Electrostatic | C11 = 95.36383731153 fF | Completed; strict Resolve and Report rendered |
| Q3D capacitance | C11 = 87.00027087746 fF | Completed; strict Resolve and Report rendered |
| Palace Eigenmode | Mode 1 = 5.137790889095 GHz; port p = 0.9939261336199 | Completed; strict Resolve and Report rendered |
| HFSS Eigenmode | Mode 1 = 4.87905956548 GHz | Native solve and strict returned-result Resolve completed; original EPR remains partial |

Capacitance is for the sole pad Signal/Terminal referenced to physical Ground,
not a floating-net Schur complement. Palace uses natural ZeroCharge exterior;
Q3D uses an open Region. The figures do not establish backend equivalence.
The Eigenmode model has an explicitly selected linear 10 nH branch, C=0; its
mode frequency is not a nonlinear qubit f01 or a frequency adequacy target.

`capacitance.png` shows actual returned capacitance and Palace ES AMR history.
`palace_em.png` shows the completed Palace EM frequency/indicator history.
Final Palace ES/EM indicators are 0.03940/0.03971 versus configured input 0.02.
Q3D stopped at pass 5 with native delta 0.707743% versus input 1%; HFSS stopped
at pass 10 with delta 1.4862% and native convergence false. Execution completion
does not mean numerical adequacy or solver agreement.

`surface_epr.csv` retains the eight native Palace surface rows, including
sidewall and top/bottom identity. Native bulk electric-energy and inductive-port
quantities are separate from surface participation. LiteratureCentral MA/MS/SA
loss inputs and 2 nm thickness are synthetic modeling conventions, not measured
process values. Derived loss numbers do not establish physical device Q/T1.

## Separate HFSS EPR restoration observation

The original HFSS native run used SCGSim 1.0.1. Its returned EPR record stays
partial because the native AdaptivePass frequency unit was empty. It has not
been rewritten or relabeled. `hfss_epr.png` and `hfss_epr.csv` instead show a
separately sealed, existing-solution analysis using the internally supplied
1.0.2rc1 candidate wheel identified in the manifest. That wheel is not claimed
as a publicly released dependency.

The candidate queried real and imaginary native frequency with explicit
SIValue=True, preserving the original raw value/empty unit and matching Pass
coordinates. Its actual collector/combiner produced ten complete EPR rows;
public detached Resolve, plot_epr_result and show_epr rendered. It performed
zero additional Analyze calls and did not change geometry, fields, settings,
the original receipt or sealed results. Mode 1/pass 10 is shown.

Requested 0 um and unmasked surface rows are alternative views, not additive
loss contributions. The CSV selects unmasked rows; the returned Figure retains
both labeled views. HFSS sidewalls remain uncomputed. Native convergence is
still false; the restoration demonstrates available analysis functionality,
not physical accuracy, measured lifetime or Human acceptance.

Public Figure width, height and margins were adjusted solely for readable
labels. Trace values and semantic labels retained exact identity
`ea53e7dbb1bc273f8b7c5f10606314a172f8e8b8eafa74d5c6d2de7e69867f2d`.
All evidence remains CONVERGING; no protected-main promotion or Pages
publication is implied by this develop checkpoint.
