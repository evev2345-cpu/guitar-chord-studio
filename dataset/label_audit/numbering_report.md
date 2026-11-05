# Legacy fret example numbering audit

The original human JSON was copied to user_fret_example_original.json before modification. No coordinates or physical numbers were changed. fret_num is now explicit and wire_idx remains an equal legacy alias.

Visual evidence: sample_images/fret_example_number_audit.png. Visible inlay cells 5, 7, 9, double-dot 12, 15, 17 and 19 agree with the existing numbering. No global offset was found. Early hand-covered wire positions and some exact endpoints are not independently verified; the audit is partial agent visual review, not a new human annotation.

The web labeler now uses an explicit physical number input. Sorting does not renumber. Deleting a selected number preserves remaining numbers. Undo removes the last-created label rather than the rightmost label. A gap does not become a falsely numbered adjacent fret cell. Import/export preserve physical numbers; the server rejects duplicates and out-of-range numbers.

Pure JavaScript model regression (executed in Node REPL) verified deleting 1 from [0,1,2,3] gives [0,2,3], reinserting 1 restores those same identities, and missing-number cells are excluded. Inline HTML JavaScript compiled successfully. Live GUI interaction was not performed.
