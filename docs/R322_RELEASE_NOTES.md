# r322 — wider header version window

Direct continuation of r321 (e104984). Version editor width increases 170 → 255px (1.5×); displayed version chip maximum increases 190 → 285px (1.5×). The bank/version group maximum increases by 95px to accommodate the expanded chip. Save/Saved follows that group in the flex row, so it moves right with the added width; no absolute positioning or duplicated margin offset is introduced. The editor adds 85px; the chip can add 95px when its text needs the space. Existing bank-label truncation remains.

Includes all r321 setup protections and r320 disclosure controls. No engine changes. Validation: setup Node helper checks, inline script syntax and whitespace checks. Fresh-bundle clone verified. No browser executable available: actual pixel positions have not been visually measured.
