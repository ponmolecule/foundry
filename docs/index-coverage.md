# Foundry Index coverage inventory

r391. Read with `scripts/check_index_coverage.py`. The reference is curated from the current console controls and linked specification documents; grouping an area is not a substitute for reviewing its semantics.

| Subject | Topics | Representative UI / specification evidence |
|---|---:|---|
| Engagement setup | 3 | Start/Reset, engagementSetupApply, Configuration capital/pre-opening |
| Customer acquisition | 9 | CAC_METHODS, _cacMeta, _accountAdoptionHtml |
| Workforce | 4 | _workforceCapacityEditor, nieWorkforceCountMode, role Start/End controls |
| Compensation | 5 | nieWorkforceCompBasis, _workforcePiecewiseTermOptions; docs/annual-compensation-pools.md |
| Lending | 11 | lending balance/pricing/credit controls; docs/lending_contracts.md |
| Deposits | 4 | depositBalanceHtml, depositLocalAmountHtml, deposit pricing controls |
| Fee products & exposures | 7 | fee-stream Basis, Activity, Pricing, Timing, Costs editors |
| Operating expenses | 7 | card-nie; docs/OPEX_ARCHITECTURE.md |
| Rates & curves | 3 | Rates workspace; docs/rates-authoring-state.md |
| Assets & liabilities | 7 | fixed assets/Other assets/Other liabilities editors; docs/FIXED_ASSETS_SPEC.md, expense-linked-liabilities.md |
| Capital & funding | 4 | card-cap, cblrElected, funding controls, Capital & Ratios |
| Income taxes | 5 | card-tax, TAX_BLOCK_TYPES, externalTaxHtml; docs/R332_TAX_RULES.md, R335_TAX_BLOCKS.md |
| Shared authoring controls | 12 | _faSeriesEditor, formulaBaseHtml, fee coefficient/unit contracts |
| Results & analysis | 9 | TAB_DEFS, statement/product/peer/stress renderers |
| Files, saving & governance | 6 | engMenuSave, export/import handlers, Governance/QA/history |
| Bank Design Lab | 6 | renderLab and six lab mode functions |

## Topic inventory

### Engagement setup

- **Engagement dates, horizon & cadence** — Start/Reset; Configuration → engagement setup
- **Opening assumptions & pre-opening costs** — Configuration → opening / capital / asset assumptions
- **Start/Reset, templates & Guide Me** — Start/Reset; Product → Guide Me

### Customer acquisition

- **Customer acquisition methods** — Configuration → Customer acquisition → feed → channel
- **Active accounts vs gross new customers** — Configuration → Customer acquisition; Product → stream → Activity
- **Driver source vs linked stream** — Product → stream → Activity → Driver source
- **Beginning, ending & average** — Linked count/balance controls → Measure
- **Attrition & acquisition timing** — Configuration → Customer acquisition → feed
- **Feeds, channels & customer quantities** — Configuration → Customer acquisition
- **Linked workforce & productivity ramps** — Configuration → Customer acquisition → FTEs × productivity
- **Average AUC per new customer** — Configuration → Customer acquisition → channel → Average AUC / new customer
- **Account adoption · optional subscriber sources** — Configuration → Customer acquisition → feed → + Account adoption

### Workforce

- **Workforce roles & populations** — Configuration → Operating expense → Detailed → Workforce
- **Workforce count methods & paths** — Configuration → Operating expense → Detailed → Workforce → role → Count method
- **Customer-capacity staffing** — Configuration → Operating expense → Detailed → Workforce → Count method → Customer capacity
- **Hiring, activation & end dates** — Configuration → Operating expense → Detailed → Workforce → role → Start / End

### Compensation

- **Compensation · /FTE versus Total** — Configuration → Operating expense → Detailed → Workforce → role → Compensation
- **Salary escalation & compensation paths** — Configuration → Operating expense → Detailed → Workforce → defaults / role → Advanced trajectories
- **Benefits & payroll load** — Configuration → Operating expense → Detailed → Workforce → Benefits & payroll default / role Benefits / payroll %
- **Metric-driven compensation pools** — Configuration → Operating expense → Detailed → Workforce → + Compensation pool
- **Annual award minimum from selected base pay** — Configuration → Operating expense → Detailed → Workforce → Compensation pool → selected-pay minimum

### Lending

- **Balance authoring · lending** — Product → select a lending product → Balance authoring
- **Production & repayment method** — Product → lending → Production & repayment method
- **Repayment curves by age** — Product → lending → funded volume / repayment profile
- **Credit losses, allowance & provision** — Product → lending → Credit & allowance
- **Loan yield, fixed/floating pricing & interest** — Product → lending → Pricing / exposure
- **Funded flow, exposure term & capacity** — Product → lending → Funded volume / exposure
- **Deferred origination fees & costs** — Product → lending → Deferred origination fees & costs
- **Loan sales, fair value & retained servicing** — Product → lending → sales / measurement / servicing
- **Allowance method choices** — Product → lending → Credit & allowance → Allowance method
- **Maturity, runoff & prepayment boundaries** — Product → lending → repayment / timing
- **Credit regime · CECL presentation** — Configuration → Credit regime — CECL presentation

### Deposits

- **Balance method · deposits** — Product → select a deposit → Category balance → Balance method
- **Balance per customer** — Product → deposit → Category balance → Balance per customer
- **Deposit pricing** — Product → deposit → Pricing
- **Retention & sweep pools** — Product → deposit → Shared retention & sweep pool

### Fee products & exposures

- **Basis (calculation) · fee streams** — Product → fee product → stream → Basis (calculation)
- **Turns vs amount per source unit** — Product → transaction stream → Activity → Derived (× source)
- **Per-account & per-unit costs** — Product → stream → Costs
- **Revenue, contra-revenue & operating cost** — Product → stream → Income presentation / Costs
- **Fee pricing behaviors** — Product → stream → Pricing
- **Off-balance-sheet exposures & commitments** — Product → Off-balance-sheet
- **Stream starts, ends & ramps** — Product → stream → Timing

### Operating expenses

- **Operating expense · Simple versus Detailed** — Configuration → Operating expense
- **Expense categories & recurring paths** — Configuration → Operating expense → Detailed → Expense categories
- **Expense recognition & cash settlement** — Configuration → Operating expense → Detailed → Expense categories → recurring expense timing
- **Prepaid & accrued operating expenses** — Configuration → Operating expense; Balance Sheet
- **Tiered / banded expense components** — Configuration → Operating expense → Detailed → Expense categories → + Tiered bands
- **Cost pools, recovery & markup** — Configuration → Operating expense → Detailed → Expense categories → + Cost pool; Product → eligible cost base
- **Assessments & other NIE** — Configuration → Operating expense → Detailed → Assessments & other NIE

### Rates & curves

- **EFFR, SOFR & Prime** — Rates & Curves workspace
- **Rate schedules, interpolation & overrides** — Rates & Curves → selected index → schedule
- **Load, Preview & Apply rate changes** — Rates & Curves workspace

### Assets & liabilities

- **Cash, liquidity & securities allocation** — Configuration → cash / securities / balance-sheet policy
- **Fixed assets · Formula / level vs Asset schedule** — Configuration → Fixed assets
- **Other assets & accounts receivable** — Configuration → Other assets
- **Other liabilities & expense-linked payables** — Configuration → Other liabilities → liability component
- **Named balance components & residual cash** — Configuration → balance components / other balance-sheet components
- **Other income** — Configuration → Other income
- **Securities books & investment treatment** — Configuration → Securities

### Capital & funding

- **Initial capital & staged capital raises** — Configuration → Capital / capital raises
- **Funding shortfalls & scheduled borrowings** — Configuration → funding / borrowings; Balance Sheet
- **Capital ratios, risk weights & CBLR** — Configuration → capital / global assumptions; Capital & Ratios
- **Dividends · current modeling boundary** — Balance Sheet → retained earnings; Assumption Book → methodology

### Income taxes

- **Income taxes · calculated vs externally determined** — Configuration → Income taxes → Tax determination
- **External tax sources, rules & outputs** — Configuration → Income taxes → Externally determined
- **Loss carryforwards & deferred tax balances** — Configuration → Income taxes; Balance Sheet
- **Tax provision, payment & settlement balances** — Configuration → Income taxes → settlement / outputs
- **Reusable external-tax blocks** — Configuration → Income taxes → externally determined tax blocks

### Shared authoring controls

- **Formula · add / subtract base** — Configuration → Operating expense → Detailed → Expense categories → + Formula
- **Factor display & time basis** — Configuration → Operating expense → Formula → Apply / Factor
- **Flat, Growth & Explicit schedules** — Series controls across Configuration and Product
- **Annual rate vs schedule cadence** — Annual rate controls; Series schedule cadence
- **Inflation & cost multipliers** — Product → stream → Costs → Cost multiplier path
- **Current vs cumulative gross acquisition share** — Formula → Linked Series → Customer acquisition → channel share
- **Money units · $000s vs unit prices** — Monetary input labels; output series unit labels
- **Enter, Link & Derived** — Compatible source controls across Foundry
- **Per-period overrides & bulk entry** — Product → Per-month overrides / field schedule controls
- **Source eligibility, units & circularity** — Browse / search source catalogs
- **Reusable amounts & weighted assumptions** — Lending → Average lending per customer → Shared assumption × factors
- **Share of source vs flow % of source** — Product → stream → Activity → derived coefficient

### Results & analysis

- **Stream quantity vs financial output** — Product → stream → compact preview / results
- **Principal vs carrying balance** — Product → lending results; Product Detail
- **Balance Sheet & Income Statement** — Balance Sheet; Income Statement
- **Product & Product Detail results** — Product; Product Detail
- **Capital & performance ratios** — Capital & Ratios
- **Stress scenarios & overlays** — Stress Testing; global stress assumptions
- **Peer Cohort & vintage comparisons** — Peer Cohort
- **Executive Summary, Examiner Book & Assumption Book** — Executive Summary; Examiner Book; Assumption Book
- **DFAST Severe scenario** — Stress Testing → DFAST Severe

### Files, saving & governance

- **Save & new versions** — Save button; engagement menu → Save as a new version
- **Recovery copies & history** — Governance → Change history → Open copy; recovery notice
- **Incomplete inputs & latest-run figures** — Input banner; Save status; result captions
- **Configuration JSON & inputs workbook imports** — Start/Reset → upload; engagement import controls
- **Exports & calculation audit workbooks** — Export menu; inputs workbook export controls
- **Governance & QA, history & reproducibility** — Governance

### Bank Design Lab

- **Goal Seek · Bank Design Lab** — Bank Design Lab → Goal Seek
- **Scenario · Bank Design Lab** — Bank Design Lab → Scenario
- **Sensitivity · Bank Design Lab** — Bank Design Lab → Sensitivity
- **Trade-off · Bank Design Lab** — Bank Design Lab → Trade-off
- **Optimizer · Bank Design Lab** — Bank Design Lab → Optimizer
- **Efficient Frontier · Bank Design Lab** — Bank Design Lab → Efficient Frontier

