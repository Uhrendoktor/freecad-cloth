# Avatar geometry source

The production mannequin uses the pinned MakeHuman HM08 base OBJ. HM08 stores the visible body vertices in indices `0..13379`; helper geometry follows that range. The provider therefore keeps exactly the canonical body vertex range and drops faces that reference helper vertices.

This boundary is sourced from the MPFB2 HM08 mesh metadata and is intentionally separate from fitting and pose logic. The default mannequin is height-normalized only; body measurements and pose are subsequent transforms.
