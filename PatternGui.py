"""FreeCAD GUI helpers for the Cloth Pattern workbench."""
def _gui_modules():
    import FreeCAD as App,FreeCADGui as Gui
    try:from PySide import QtWidgets,QtGui,QtCore
    except ImportError:from PySide2 import QtWidgets,QtGui,QtCore
    return App,Gui,QtWidgets,QtGui,QtCore
class PatternPieceTaskPanel:
    def __init__(self,obj=None):
        App,Gui,QtWidgets,_,_=_gui_modules();self.App,self.Gui,self.obj=App,Gui,obj;self.form=QtWidgets.QWidget();layout=QtWidgets.QFormLayout(self.form);self.name=QtWidgets.QLineEdit();self.width=QtWidgets.QDoubleSpinBox();self.width.setRange(.1,100000);self.width.setDecimals(2);self.width.setSuffix(" mm");self.height=QtWidgets.QDoubleSpinBox();self.height.setRange(.1,100000);self.height.setDecimals(2);self.height.setSuffix(" mm");self.allowance=QtWidgets.QDoubleSpinBox();self.allowance.setRange(0,1000);self.allowance.setDecimals(2);self.allowance.setSuffix(" mm");self.grain=QtWidgets.QDoubleSpinBox();self.grain.setRange(-360,360);self.grain.setDecimals(1);self.grain.setSuffix(" deg")
        for label,w in (("Piece name",self.name),("Width",self.width),("Height",self.height),("Seam allowance",self.allowance),("Grainline angle",self.grain)):layout.addRow(label,w)
        if obj:self.name.setText(obj.Label);self.width.setValue(float(obj.Width));self.height.setValue(float(obj.Height));self.allowance.setValue(float(obj.SeamAllowance));self.grain.setValue(float(obj.GrainlineAngle))
    def _apply(self):
        if self.obj is None:
            from PatternCommands import create_pattern_piece_from_parameters;self.obj=create_pattern_piece_from_parameters(self.name.text().strip() or "PatternPiece",self.width.value(),self.height.value(),self.allowance.value(),self.grain.value())
        else:self.obj.Width=self.width.value();self.obj.Height=self.height.value();self.obj.SeamAllowance=self.allowance.value();self.obj.GrainlineAngle=self.grain.value();self.obj.Label=self.name.text().strip() or self.obj.Label;self.App.ActiveDocument.recompute()
        self.Gui.activeDocument().activeView().viewTop();self.Gui.activeDocument().activeView().fitAll()
    def accept(self):self._apply();return True
    def reject(self):return True
    def getStandardButtons(self):return 0x00000400|0x00800000
class PatternDraftingTaskPanel:
    """Sketch-like 2D canvas with selectable boundary points and persisted edits."""
    def __init__(self,obj):
        App,Gui,QtWidgets,QtGui,QtCore=_gui_modules();self.App,self.Gui,self.obj=App,Gui,obj
        from PatternDrafting import default_points,parse_points,move_point,seam_allowance_preview
        try:self.points=list(parse_points(obj.DraftingBoundary))
        except (ValueError,AttributeError):self.points=list(default_points(obj.Width,obj.Height))
        self.move_point,self.seam_allowance_preview,self.selected=move_point,seam_allowance_preview,0;self.form=QtWidgets.QWidget();outer=QtWidgets.QVBoxLayout(self.form);self.canvas=QtWidgets.QGraphicsView();self.scene=QtWidgets.QGraphicsScene(self.canvas);self.canvas.setScene(self.scene);self.canvas.setMinimumSize(500,360);outer.addWidget(self.canvas);self.scene.selectionChanged.connect(self._selection_changed);controls=QtWidgets.QHBoxLayout()
        for text,dx,dy in (("←",-5,0),("→",5,0),("↑",0,5),("↓",0,-5)):
            button=QtWidgets.QPushButton(text);button.clicked.connect(lambda _=False,x=dx,y=dy:self.nudge(x,y));controls.addWidget(button)
        self.point_label=QtWidgets.QLabel("Point 0");controls.addWidget(self.point_label);outer.addLayout(controls);outer.addWidget(QtWidgets.QLabel("Click a boundary point, then nudge it. Semantic segments, notches and seam allowance remain on the piece."));self._redraw(QtGui,QtCore)
    def _selection_changed(self):
        selected=self.scene.selectedItems()
        if selected:
            index=selected[0].data(0)
            if index is not None:self.selected=int(index);self.point_label.setText("Point %d"%self.selected)
    def _redraw(self,QtGui,QtCore):
        self.scene.clear();pts=self.points
        if not pts:return
        xs=[p[0] for p in pts];ys=[p[1] for p in pts];margin=30.;scale=min(430./max(1.,max(xs)-min(xs)),280./max(1.,max(ys)-min(ys)))
        def cv(p):return QtCore.QPointF((p[0]-min(xs))*scale+margin,(max(ys)-p[1])*scale+margin)
        poly=[cv(p) for p in pts]+[cv(pts[0])];self.scene.addPolygon(QtGui.QPolygonF(poly),QtGui.QPen(QtGui.QColor("#204a87"),2));allowance=float(getattr(self.obj,"SeamAllowance",0))
        if allowance:
            preview=self.seam_allowance_preview(pts,allowance);ap=[cv(p) for p in preview]+[cv(preview[0])];self.scene.addPolygon(QtGui.QPolygonF(ap),QtGui.QPen(QtGui.QColor("#888888"),1,QtCore.Qt.DashLine))
        for i,p in enumerate(pts):
            q=cv(p);item=self.scene.addEllipse(q.x()-6,q.y()-6,12,12,QtGui.QPen(),QtGui.QBrush(QtGui.QColor("#c0392b")));item.setFlag(item.ItemIsSelectable,True);item.setData(0,i)
        for i in range(4):a,b=cv(pts[i]),cv(pts[(i+1)%4]);mid=(a+b)/2;self.scene.addText("S%d"%i).setPos(mid.x(),mid.y())
        self.canvas.fitInView(self.scene.itemsBoundingRect().adjusted(-20,-20,20,20),QtCore.Qt.KeepAspectRatio)
    def nudge(self,dx,dy):
        self.points=list(self.move_point(self.points,self.selected,self.points[self.selected][0]+dx,self.points[self.selected][1]+dy));from PatternDrafting import serialize_points,bounds;self.obj.DraftingBoundary=serialize_points(self.points);x0,y0,x1,y1=bounds(self.points);self.obj.Width=max(.001,x1-x0);self.obj.Height=max(.001,y1-y0);self.App.ActiveDocument.recompute();_,_,_,QtGui,QtCore=_gui_modules();self._redraw(QtGui,QtCore)
    def accept(self):return True
    def reject(self):return True
    def getStandardButtons(self):return 0x00000400|0x00800000
def show_pattern_piece_task(obj=None):
    _App,Gui,_QtWidgets,_,_=_gui_modules();panel=PatternPieceTaskPanel(obj);Gui.Control.showDialog(panel);return panel
def show_pattern_drafting_task(obj=None):
    App,Gui,_,_,_=_gui_modules();
    if obj is None:obj=next((o for o in App.ActiveDocument.Objects if getattr(o,"PatternType","")=="PatternPiece"),None)
    if obj is None:raise ValueError("create a pattern piece before opening the drafting canvas")
    panel=PatternDraftingTaskPanel(obj);Gui.Control.showDialog(panel);return panel
def show_pattern_view():
    _App,Gui,_QtWidgets,_,_=_gui_modules();
    if Gui.activeDocument():Gui.activeDocument().activeView().viewTop();Gui.activeDocument().activeView().fitAll()
