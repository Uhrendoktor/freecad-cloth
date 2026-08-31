"""FreeCAD task panel for editing sewing operations.

The panel exposes persistent seam orientation/alignment plus normalized curved
correspondence ranges. All semantic values remain on the document Seam object;
the task panel is only the interactive frontend.
"""

def _gui_modules():
    import FreeCAD as App
    import FreeCADGui as Gui
    try: from PySide import QtCore, QtWidgets
    except ImportError: from PySide2 import QtCore, QtWidgets
    return App, Gui, QtCore, QtWidgets

def seam_reference_status(seam):
    if seam is None: return "Missing seam"
    return str(getattr(seam, "Status", "Valid")) or "Valid"

def validate_seam_for_accept(seam):
    status=seam_reference_status(seam)
    if status != "Valid":
        seam_id=str(getattr(seam,"SeamId","")) or "<unnamed>"
        raise ValueError("cannot accept sewing operation with invalid seam reference %s: %s"%(seam_id,status))
    return True

def correspondence_report(seam, length_a, length_b, tolerance=0.05):
    from freecad_cloth.sewing.SewingCorrespondence import analyze_correspondence
    if seam is None: return None
    return analyze_correspondence(float(length_a),float(length_b),float(getattr(seam,"StartA",0.0)),float(getattr(seam,"EndA",1.0)),float(getattr(seam,"StartB",0.0)),float(getattr(seam,"EndB",1.0)),bool(getattr(seam,"ReversedB",False)),float(tolerance))

def repair_correspondence_settings(seam, report):
    """Apply only non-destructive semantic repairs to a seam.

    Reversal is repaired by restoring forward correspondence. Invalid ranges
    are reset to the complete referenced edges. Physical length mismatch is
    deliberately not hidden: the caller must edit the pattern or seam ranges.
    """
    if seam is None or report is None:
        raise ValueError("a seam correspondence report is required")
    if report.status == "reversed":
        seam.ReversedB = False
        return "reversed correspondence repaired"
    if report.status == "invalid_range":
        seam.StartA, seam.EndA = 0.0, 1.0
        seam.StartB, seam.EndB = 0.0, 1.0
        return "invalid ranges reset to full seam edges"
    if report.status == "length_mismatch":
        raise ValueError("length mismatch requires editing the pattern or seam ranges; it was not hidden by changing tolerance")
    return "seam correspondence is already valid"

class SewingTaskPanel:
    _TRANSACTION_NAME="Edit Sewing Operation"
    def __init__(self,obj):
        App,Gui,QtCore,QtWidgets=_gui_modules(); self.App=App; self.Gui=Gui; self.QtCore=QtCore; self.obj=obj; self.seam=getattr(obj,"Seam",None); self._transaction_active=False
        self.form=QtWidgets.QWidget(); layout=QtWidgets.QFormLayout(self.form)
        seam_id=str(getattr(self.seam,"SeamId","")) if self.seam else ""; piece_a=getattr(self.seam,"PieceA",None) if self.seam else None; piece_b=getattr(self.seam,"PieceB",None) if self.seam else None
        self.seam_info=QtWidgets.QLabel("%s: %s ↔ %s"%(seam_id or "Unassigned seam",piece_a or "?",piece_b or "?")); self.seam_info.setWordWrap(True); layout.addRow("Seam",self.seam_info)
        self.alignment=QtWidgets.QComboBox(); self.alignment.addItems(["endpoints","uniform"]); current_alignment=str(getattr(self.seam,"Alignment",getattr(obj,"Alignment","endpoints"))); self.alignment.setCurrentIndex(max(0,self.alignment.findText(current_alignment))); layout.addRow("Alignment",self.alignment)
        self.reversed_b=QtWidgets.QCheckBox("Reverse B correspondence"); self.reversed_b.setChecked(bool(getattr(self.seam,"ReversedB",getattr(obj,"ReversedB",False)))); layout.addRow("Orientation",self.reversed_b)
        self.start_a=self._range_spin(float(getattr(self.seam,"StartA",0.0))); self.end_a=self._range_spin(float(getattr(self.seam,"EndA",1.0))); self.start_b=self._range_spin(float(getattr(self.seam,"StartB",0.0))); self.end_b=self._range_spin(float(getattr(self.seam,"EndB",1.0)))
        layout.addRow("A range start",self.start_a); layout.addRow("A range end",self.end_a); layout.addRow("B range start",self.start_b); layout.addRow("B range end",self.end_b)
        self.tolerance=QtWidgets.QDoubleSpinBox(); self.tolerance.setRange(0,1000); self.tolerance.setDecimals(2); self.tolerance.setSuffix(" mm"); self.tolerance.setValue(float(obj.Tolerance)); layout.addRow("Validation tolerance",self.tolerance)
        self.stitches=QtWidgets.QSpinBox(); self.stitches.setRange(2,10000); self.stitches.setValue(max(2,int(obj.Stitches))); layout.addRow("Stitch samples",self.stitches)
        self.status=QtWidgets.QLabel(); self.status.setWordWrap(True); self.lengths=QtWidgets.QLabel(); self.lengths.setWordWrap(True); self.correspondence=QtWidgets.QLabel(); self.correspondence.setWordWrap(True); layout.addRow("Status",self.status); layout.addRow("Seam lengths",self.lengths); layout.addRow("Correspondence",self.correspondence)
        self.reverse_button=QtWidgets.QPushButton("Reverse B"); self.reverse_button.setToolTip("Toggle the direction of seam B correspondence"); self.reverse_button.clicked.connect(self.reverse_b); layout.addRow("Orientation",self.reverse_button)
        self.reset_ranges_button=QtWidgets.QPushButton("Reset ranges"); self.reset_ranges_button.setToolTip("Reset both seam ranges to the complete referenced edges"); self.reset_ranges_button.clicked.connect(self.reset_ranges); layout.addRow("Ranges",self.reset_ranges_button)
        self.repair_button=QtWidgets.QPushButton("Repair correspondence"); self.repair_button.setToolTip("Repair reversible/invalid-range correspondence without hiding physical length mismatch"); self.repair_button.clicked.connect(self.repair); layout.addRow("Repair",self.repair_button)
        self._original={"Tolerance":float(obj.Tolerance),"Stitches":int(obj.Stitches),"Alignment":str(getattr(self.seam,"Alignment","endpoints")) if self.seam else "endpoints","ReversedB":bool(getattr(self.seam,"ReversedB",False)) if self.seam else False,"StartA":float(getattr(self.seam,"StartA",0.0)) if self.seam else 0.0,"EndA":float(getattr(self.seam,"EndA",1.0)) if self.seam else 1.0,"StartB":float(getattr(self.seam,"StartB",0.0)) if self.seam else 0.0,"EndB":float(getattr(self.seam,"EndB",1.0)) if self.seam else 1.0}
        self._begin_transaction(); self._refresh()
    def _range_spin(self,value):
        _App,_Gui,_QtCore,QtWidgets=_gui_modules(); box=QtWidgets.QDoubleSpinBox(); box.setRange(0.0,1.0); box.setDecimals(4); box.setSingleStep(0.01); box.setValue(max(0.0,min(1.0,value))); return box
    def _begin_transaction(self):
        doc=self.App.ActiveDocument; opener=getattr(doc,"openTransaction",None) if doc is not None else None
        if callable(opener): opener(self._TRANSACTION_NAME); self._transaction_active=True
    def _commit_transaction(self):
        if not self._transaction_active: return
        doc=self.App.ActiveDocument; committer=getattr(doc,"commitTransaction",None) if doc is not None else None
        if callable(committer): committer()
        self._transaction_active=False
    def _abort_transaction(self):
        if not self._transaction_active: return False
        doc=self.App.ActiveDocument; aborter=getattr(doc,"abortTransaction",None) if doc is not None else None
        if callable(aborter): aborter(); self._transaction_active=False; return True
        self._transaction_active=False; return False
    def _refresh(self):
        self.status.setText(str(self.obj.Status)); self.lengths.setText("%.2f / %.2f mm (Δ %.2f)"%(float(self.obj.LengthA),float(self.obj.LengthB),float(self.obj.LengthDifference)))
        report=correspondence_report(self.seam,self.obj.LengthA,self.obj.LengthB,max(0.0,float(self.obj.Tolerance))/max(1.0,float(self.obj.LengthA)))
        if report is None: self.correspondence.setText("No seam correspondence"); return
        self.correspondence.setText("%s — %s (ratio %.4f)"%(report.status,report.message,report.length_ratio))
        self.reverse_button.setText("Unreverse B" if bool(getattr(self.seam,"ReversedB",False)) else "Reverse B")
        self.reset_ranges_button.setEnabled(any(abs(float(getattr(self.seam,name,default))-default)>1e-9 for name,default in (("StartA",0.0),("EndA",1.0),("StartB",0.0),("EndB",1.0))))
    def update(self): self._refresh()
    def _apply_seam_settings(self):
        if self.seam is None: return
        self.seam.Alignment=str(self.alignment.currentText()); self.seam.ReversedB=bool(self.reversed_b.isChecked()); self.seam.StartA=self.start_a.value(); self.seam.EndA=self.end_a.value(); self.seam.StartB=self.start_b.value(); self.seam.EndB=self.end_b.value()
    def reverse_b(self):
        validate_seam_for_accept(self.seam)
        self.seam.ReversedB=not bool(getattr(self.seam,"ReversedB",False))
        self.reversed_b.setChecked(bool(self.seam.ReversedB))
        self.App.ActiveDocument.recompute(); self._refresh()
        return bool(self.seam.ReversedB)
    def reset_ranges(self):
        validate_seam_for_accept(self.seam)
        for widget in (self.start_a,self.end_a,self.start_b,self.end_b):
            widget.setValue(0.0 if widget in (self.start_a,self.start_b) else 1.0)
        self._apply_seam_settings(); self.App.ActiveDocument.recompute(); self._refresh(); return True
    def repair(self):
        validate_seam_for_accept(self.seam)
        report=correspondence_report(self.seam,self.obj.LengthA,self.obj.LengthB,max(0.0,float(self.obj.Tolerance))/max(1.0,float(self.obj.LengthA)))
        message=repair_correspondence_settings(self.seam, report)
        self.reversed_b.setChecked(bool(getattr(self.seam,"ReversedB",False)))
        for widget,name,default in ((self.start_a,"StartA",0.0),(self.end_a,"EndA",1.0),(self.start_b,"StartB",0.0),(self.end_b,"EndB",1.0)):
            widget.setValue(float(getattr(self.seam,name,default)))
        self.App.ActiveDocument.recompute(); self._refresh(); return message
    def accept(self):
        validate_seam_for_accept(self.seam); self._apply_seam_settings(); self.obj.Tolerance=self.tolerance.value(); self.obj.Stitches=self.stitches.value(); self.App.ActiveDocument.recompute(); validate_seam_for_accept(self.seam)
        report=correspondence_report(self.seam,self.obj.LengthA,self.obj.LengthB,max(0.0,float(self.obj.Tolerance))/max(1.0,float(self.obj.LengthA)))
        if report is None or not report.valid: raise ValueError("cannot accept seam correspondence: %s"%(report.message if report else "missing seam"))
        self._commit_transaction(); self._refresh(); return True
    def reject(self):
        aborted=self._abort_transaction()
        if not aborted:
            if self.seam is not None:
                for name in ("Alignment","ReversedB","StartA","EndA","StartB","EndB"): setattr(self.seam,name,self._original[name])
            self.obj.Tolerance=self._original["Tolerance"]; self.obj.Stitches=self._original["Stitches"]
        self.App.ActiveDocument.recompute(); self._refresh(); return True
    def getStandardButtons(self):
        _App,_Gui,_QtCore,QtWidgets=_gui_modules(); buttons=QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel; return int(getattr(buttons,"value",buttons))

def show_sewing_task(obj):
    _App,Gui,_QtCore,_QtWidgets=_gui_modules(); panel=SewingTaskPanel(obj); Gui.Control.showDialog(panel); return panel
