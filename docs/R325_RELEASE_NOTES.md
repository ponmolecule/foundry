# r325 — explicit settlement holding fields
Built on r324. UI only; engine and saved settlement schema unchanged.
Each holding weight now has a labeled current/prior/earlier-period field. Add earlier period supports arbitrary saved kernels. Opening history is individually labeled; new history stays blank until entered, never silently invented. Inputs preserve signed history and existing weights. Source/measure rows use bounded stacked labels and responsive columns; settlement names align left.
Validation: settlement authoring helper, new weight/history regression checks, inline JavaScript syntax, Python settlement engine tests and whitespace checks. No rendered browser verification available.
